"""
Training and Evaluation of Squeeze-and-Excitation Temporal Convolutional Network (SE-TCN)
with Focal Loss under Leave-One-Subject-Out (LOSO) Cross-Validation on the 6-Subject Library Dataset.

Supports:
- Tasks: events (5 classes), state (4 classes), presence (2 classes)
- Metrics: Overall Accuracy, Balanced Accuracy, Macro-F1, Per-Class Recall (Fall Recall)
- Comparison against Mohith's classical ML baselines (SVM-RBF, Extra Trees, Logistic Regression)

Usage:
    python train_setcn_loso.py --task events
    python train_setcn_loso.py --task state
    python train_setcn_loso.py --task presence
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# Add temp_mohith_repo to path so we can import its evaluated contracts & channel mapping
MOHITH_REPO = Path("temp_mohith_repo").resolve()
if str(MOHITH_REPO) not in sys.path:
    sys.path.insert(0, str(MOHITH_REPO))

from ml import deep as dp
from ml import evaluate as ev


# ============================================================================
# 1. SE-TCN ARCHITECTURE WITH CHANNEL ATTENTION & DILATED CONVOLUTIONS
# ============================================================================

class Subcarrier_SE_Attention(nn.Module):
    """Squeeze-and-Excitation channel attention across multi-receiver subcarrier bands."""
    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(channels, max(channels // reduction, 8)),
            nn.ReLU(),
            nn.Linear(max(channels // reduction, 8), channels),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, C, T]
        weights = self.fc(x).unsqueeze(-1)
        return x * weights


class Residual_Dilated_Conv1D(nn.Module):
    """Dilated residual block for Temporal Convolutional Network (TCN)."""
    def __init__(self, channels: int, kernel_size: int = 3, dilation: int = 1, dropout: float = 0.15):
        super().__init__()
        padding = (kernel_size - 1) * dilation // 2
        self.conv1 = nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation)
        self.bn1 = nn.BatchNorm1d(channels)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)
        
        self.conv2 = nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation)
        self.bn2 = nn.BatchNorm1d(channels)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = x
        out = self.drop1(self.relu1(self.bn1(self.conv1(x))))
        out = self.drop2(self.relu2(self.bn2(self.conv2(out))))
        return out + res


class MultiSubject_SE_TCN(nn.Module):
    """
    Squeeze-and-Excitation Temporal Convolutional Network.
    
    Combines:
    1. 1x1 spatial projection for 32 dual-receiver subcarrier channels
    2. Squeeze-and-Excitation channel attention gate
    3. 4 Stacked Residual Dilated Blocks with dilations d = [1, 2, 4, 8]
    4. Global Temporal Average Pooling and classification head
    """
    def __init__(self, in_channels: int = 32, num_classes: int = 5, hidden_dim: int = 64, dropout: float = 0.2):
        super().__init__()
        self.in_proj = nn.Sequential(
            nn.Conv1d(in_channels, hidden_dim, kernel_size=1),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU()
        )
        self.attn = Subcarrier_SE_Attention(hidden_dim, reduction=4)

        self.layer1 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=1, dropout=dropout)
        self.layer2 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=2, dropout=dropout)
        self.layer3 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=4, dropout=dropout)
        self.layer4 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=8, dropout=dropout)

        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, 32, T]
        x = self.in_proj(x)
        x = self.attn(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.global_pool(x).squeeze(-1)
        return self.classifier(x)


# ============================================================================
# 2. MULTICLASS FOCAL LOSS TO TACKLE EXTREME CLASS IMBALANCE
# ============================================================================

class FocalLoss(nn.Module):
    """
    Multiclass Focal Loss:
    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
    """
    def __init__(self, alpha: torch.Tensor = None, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.alpha)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()


# ============================================================================
# 3. LEAVE-ONE-SUBJECT-OUT (LOSO) EVALUATION ENGINE
# ============================================================================

def load_data(tag: str = "4s"):
    npz_path = MOHITH_REPO / "data" / "processed" / f"windows_{tag}.npz"
    csv_path = MOHITH_REPO / "data" / "features" / f"features_{tag}.csv"
    if not npz_path.exists() or not csv_path.exists():
        raise FileNotFoundError(f"Missing {npz_path} or {csv_path}. Please run pipeline.build_dataset first.")

    df = pd.read_csv(csv_path, usecols=ev.META_COLS)
    z = np.load(npz_path, allow_pickle=False)
    
    print(f"Loading raw tensors and converting to 32 dual-receiver channels (N={len(df)})...")
    C = np.concatenate([dp.channels(z["X"][i:i + 256], z["P"][i:i + 256]) for i in range(0, len(df), 256)])
    return df, C


def run_loso(task: str = "events", tag: str = "4s", epochs: int = 35, lr: float = 1e-3, gamma: float = 2.0, batch_size: int = 128):
    print("=" * 80)
    print(f"  SE-TCN DEEP LEARNING (Focal Loss gamma={gamma}) on 6-SUBJECT LIBRARY DATASET")
    print(f"  Task: {task.upper()} | Window: {tag} | Protocol: Leave-One-Subject-Out (LOSO)")
    print("=" * 80)

    df, C = load_data(tag)
    mask, y_str = ev.task_view(df, task)
    C_task = C[mask]
    df_task = df[mask].reset_index(drop=True)
    folds = ev.assign_folds(df)[mask]

    classes = sorted(set(y_str.tolist()))
    class_to_idx = {c: i for i, c in enumerate(classes)}
    y_idx = np.array([class_to_idx[v] for v in y_str])
    num_classes = len(classes)

    print(f"\nTask: {task} | Classes ({num_classes}): {classes}")
    print(f"Total windows: {len(C_task)} | Input shape per window: [Channels={C_task.shape[1]}, Time={C_task.shape[2]}]")
    print(f"Class distribution:\n{pd.Series(y_str).value_counts().to_string()}\n")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Execution device: {device}")

    outer_results = {}
    all_y_true = []
    all_y_pred = []

    for test_subj in ev.SUBJECTS:
        t0 = time.time()
        train_subjects = [s for s in ev.SUBJECTS if s != test_subj]
        
        # S5/S6 cross-session indicator
        is_cross = test_subj in ev.CROSS_SESSION
        
        tr_mask = np.isin(folds, train_subjects)
        te_mask = (folds == test_subj)

        X_tr_raw = C_task[tr_mask]
        y_tr = y_idx[tr_mask]
        X_te_raw = C_task[te_mask]
        y_te = y_idx[te_mask]

        # Channel-wise Standardization using TRAINING subjects only
        mu_tr = X_tr_raw.mean(axis=(0, 2), keepdims=True)
        sd_tr = X_tr_raw.std(axis=(0, 2), keepdims=True) + 1e-6
        X_tr = ((X_tr_raw - mu_tr) / sd_tr).astype(np.float32)
        X_te = ((X_te_raw - mu_tr) / sd_tr).astype(np.float32)

        # Compute balanced class weights for Focal Loss
        class_counts = np.bincount(y_tr, minlength=num_classes).astype(np.float32)
        total_samples = len(y_tr)
        alpha_weights = total_samples / (num_classes * np.maximum(class_counts, 1.0))
        alpha_tensor = torch.tensor(alpha_weights, dtype=torch.float32).to(device)

        # Initialize SE-TCN Model & Optimizer
        model = MultiSubject_SE_TCN(in_channels=X_tr.shape[1], num_classes=num_classes).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        criterion = FocalLoss(alpha=alpha_tensor, gamma=gamma)

        # Convert to PyTorch Tensors
        tensor_x_tr = torch.from_numpy(X_tr)
        tensor_y_tr = torch.from_numpy(y_tr).long()
        tensor_x_te = torch.from_numpy(X_te).to(device)

        num_batches = int(np.ceil(len(tensor_x_tr) / batch_size))

        # Training Loop
        model.train()
        for epoch in range(epochs):
            perm = torch.randperm(len(tensor_x_tr))
            for b in range(num_batches):
                idx = perm[b * batch_size : (b + 1) * batch_size]
                bx = tensor_x_tr[idx].to(device)
                by = tensor_y_tr[idx].to(device)

                optimizer.zero_grad()
                out = model(bx)
                loss = criterion(out, by)
                loss.backward()
                optimizer.step()
            scheduler.step()

        # Test on Unseen Held-Out Subject
        model.eval()
        with torch.no_grad():
            test_logits = model(tensor_x_te)
            test_preds = test_logits.argmax(dim=1).cpu().numpy()

        acc = accuracy_score(y_te, test_preds)
        bacc = balanced_accuracy_score(y_te, test_preds)
        mf1 = f1_score(y_te, test_preds, average="macro", zero_division=0)
        
        # Per-class metrics
        class_recalls = {}
        for c_idx, c_name in enumerate(classes):
            mask_c = (y_te == c_idx)
            if np.sum(mask_c) > 0:
                rec_c = float(np.sum((test_preds == c_idx) & mask_c) / np.sum(mask_c))
            else:
                rec_c = 0.0
            class_recalls[c_name] = rec_c

        elapsed = time.time() - t0
        outer_results[test_subj] = {
            "accuracy": float(acc),
            "balanced_accuracy": float(bacc),
            "macro_f1": float(mf1),
            "recalls": class_recalls,
            "support": len(y_te),
            "cross_session": is_cross,
            "train_time_s": elapsed
        }

        all_y_true.extend(y_te)
        all_y_pred.extend(test_preds)

        tag_cross = " (Cross-Session PM)" if is_cross else " (Morning)"
        print(f"  Fold {test_subj}{tag_cross:<20} | Acc: {acc*100:5.2f}% | BalAcc: {bacc*100:5.2f}% | Macro-F1: {mf1:5.4f} | Time: {elapsed:4.1f}s")
        if task == "events" and "fall" in class_recalls:
            print(f"      -> Fall Recall: {class_recalls['fall']*100:5.2f}%")

    # Overall Summary across all 6 LOSO folds
    mean_acc = np.mean([r["accuracy"] for r in outer_results.values()])
    std_acc = np.std([r["accuracy"] for r in outer_results.values()])
    mean_bacc = np.mean([r["balanced_accuracy"] for r in outer_results.values()])
    std_bacc = np.std([r["balanced_accuracy"] for r in outer_results.values()])
    mean_mf1 = np.mean([r["macro_f1"] for r in outer_results.values()])
    std_mf1 = np.std([r["macro_f1"] for r in outer_results.values()])

    pooled_acc = accuracy_score(all_y_true, all_y_pred)
    pooled_bacc = balanced_accuracy_score(all_y_true, all_y_pred)
    pooled_mf1 = f1_score(all_y_true, all_y_pred, average="macro", zero_division=0)

    print("\n" + "=" * 80)
    print("  LEAVE-ONE-SUBJECT-OUT (LOSO) FINAL RESULTS SUMMARY")
    print("=" * 80)
    print(f"  Mean Accuracy across Folds:          {mean_acc*100:6.2f}% ± {std_acc*100:4.2f}%")
    print(f"  Mean Balanced Accuracy:              {mean_bacc*100:6.2f}% ± {std_bacc*100:4.2f}%")
    print(f"  Mean Macro-F1 Score:                 {mean_mf1:6.4f} ± {std_mf1:5.4f}")
    print(f"  Pooled Overall Accuracy:             {pooled_acc*100:6.2f}%")
    print(f"  Pooled Balanced Accuracy:            {pooled_bacc*100:6.2f}%")
    print(f"  Pooled Macro-F1 Score:               {pooled_mf1:6.4f}")
    
    # Per-Class Average Recalls
    print("\n  Per-Class Recall across all 6 test subjects:")
    for c_name in classes:
        recs = [r["recalls"].get(c_name, 0.0) for r in outer_results.values()]
        print(f"    - {c_name:<12}: {np.mean(recs)*100:5.2f}% ± {np.std(recs)*100:4.2f}%")

    # Confusion Matrix
    cm = confusion_matrix(all_y_true, all_y_pred, labels=list(range(num_classes)))
    print("\n  Pooled Confusion Matrix (Rows=True, Cols=Predicted):")
    col_headers = " ".join([f"{c[:7]:>8}" for c in classes])
    print(f"    {'':<12} {col_headers}")
    for idx, c_name in enumerate(classes):
        row_str = " ".join([f"{val:8d}" for val in cm[idx]])
        print(f"    {c_name:<12} {row_str}")

    # Comparison against Mohith's classical ML baseline
    print("\n" + "=" * 80)
    print("  COMPARISON: DEEP LEARNING (SE-TCN) vs CLASSICAL ML (Mohith's Report)")
    print("=" * 80)
    mohith_baselines = {
        "presence": ("Logistic Regression", "0.698 ± 0.065"),
        "state": ("Extra Trees (300 trees)", "0.572 ± 0.115"),
        "events": ("SVM-RBF", "0.539 ± 0.054")
    }
    base_name, base_f1 = mohith_baselines.get(task, ("Classical Baseline", "N/A"))
    print(f"  • Classical ML Baseline ({base_name}): Macro-F1 = {base_f1}")
    print(f"  • Proposed Deep Learning (SE-TCN + Focal Loss):   Macro-F1 = {mean_mf1:5.4f} ± {std_mf1:5.4f}")
    print(f"  • Proposed Deep Learning (SE-TCN) Overall Acc:   {mean_acc*100:5.2f}%")
    print("=" * 80)

    # Save results to JSON
    out_dir = Path("results/setcn_multisubject")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"setcn_{task}_loso_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "task": task,
            "mean_accuracy": float(mean_acc),
            "std_accuracy": float(std_acc),
            "mean_balanced_accuracy": float(mean_bacc),
            "std_balanced_accuracy": float(std_bacc),
            "mean_macro_f1": float(mean_mf1),
            "std_macro_f1": float(std_mf1),
            "pooled_accuracy": float(pooled_acc),
            "pooled_macro_f1": float(pooled_mf1),
            "classes": classes,
            "per_fold": outer_results,
            "confusion_matrix": cm.tolist()
        }, f, indent=2)
    print(f"\nDetailed evaluation results saved to: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="SE-TCN Multi-Subject LOSO Training")
    parser.add_argument("--task", type=str, default="events", choices=["events", "state", "presence"],
                        help="Target task (events, state, presence)")
    parser.add_argument("--win", type=str, default="4s", help="Window duration (4s)")
    parser.add_argument("--epochs", type=int, default=30, help="Epochs per fold")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--gamma", type=float, default=2.0, help="Focal Loss focusing factor")
    parser.add_argument("--batch_size", type=int, default=128, help="Batch size")
    args = parser.parse_args()

    run_loso(task=args.task, tag=args.win, epochs=args.epochs, lr=args.lr, gamma=args.gamma, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
