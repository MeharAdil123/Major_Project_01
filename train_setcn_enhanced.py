"""
Enhanced SE-TCN Deep Learning Champion with Architectural & Training Optimizations:
1. Extended Multi-Scale Dilated Receptive Field (5 layers: d = [1, 2, 4, 8, 16] with k = 3 or k = 5, spanning full 4s window).
2. Dual Global Pooling (AvgPool + MaxPool) to capture both steady posture and transient impact shocks.
3. Smoothed Class Weighting (Square-root inverse frequency) to balance rare and majority classes.
4. Jitter and Scaling Data Augmentation on training folds strictly (zero test fold leakage).
5. Label Smoothing to prevent subject-specific overconfidence.
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
)

MOHITH_REPO = Path("temp_mohith_repo").resolve()
if str(MOHITH_REPO) not in sys.path:
    sys.path.insert(0, str(MOHITH_REPO))

from ml import deep as dp
from ml import evaluate as ev


class Subcarrier_SE_Attention(nn.Module):
    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(channels, max(channels // reduction, 8), bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(max(channels // reduction, 8), channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = self.fc(x).unsqueeze(-1)
        return x * w


class Residual_Dilated_Conv1D(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 3, dilation: int = 1, dropout: float = 0.25):
        super().__init__()
        padding = (kernel_size - 1) * dilation // 2
        self.conv1 = nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation)
        self.bn1 = nn.BatchNorm1d(channels)
        self.relu1 = nn.ReLU(inplace=True)
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation)
        self.bn2 = nn.BatchNorm1d(channels)
        self.relu2 = nn.ReLU(inplace=True)
        self.drop2 = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = x
        out = self.drop1(self.relu1(self.bn1(self.conv1(x))))
        out = self.drop2(self.relu2(self.bn2(self.conv2(out))))
        return out + res


class Enhanced_SE_TCN(nn.Module):
    def __init__(self, in_channels: int = 32, num_classes: int = 5, hidden_dim: int = 64, dropout: float = 0.25):
        super().__init__()
        # Input projection
        self.in_proj = nn.Sequential(
            nn.Conv1d(in_channels, hidden_dim, kernel_size=1),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True)
        )
        self.attn1 = Subcarrier_SE_Attention(hidden_dim, reduction=4)

        # 5 Dilated Residual Blocks: d in [1, 2, 4, 8, 16] with kernel_size = 3
        # Total Receptive Field spans 125 timesteps (2.5s) to 200 timesteps (4.0s)
        self.layer1 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=1, dropout=dropout)
        self.layer2 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=2, dropout=dropout)
        self.layer3 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=4, dropout=dropout)
        self.attn2 = Subcarrier_SE_Attention(hidden_dim, reduction=4)
        self.layer4 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=8, dropout=dropout)
        self.layer5 = Residual_Dilated_Conv1D(hidden_dim, kernel_size=3, dilation=16, dropout=dropout)

        # Dual Global Pooling: Concatenate AvgPool and MaxPool
        self.avg_pool = nn.AdaptiveAvgPool1d(1)
        self.max_pool = nn.AdaptiveMaxPool1d(1)

        # Classification Head: Takes 2 * hidden_dim = 128
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, 48),
            nn.BatchNorm1d(48),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout / 2),
            nn.Linear(48, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.in_proj(x)
        x = self.attn1(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.attn2(x)
        x = self.layer4(x)
        x = self.layer5(x)

        p_avg = self.avg_pool(x).squeeze(-1)
        p_max = self.max_pool(x).squeeze(-1)
        feat = torch.cat([p_avg, p_max], dim=1)
        return self.classifier(feat)


class SmoothFocalLoss(nn.Module):
    """
    Multiclass Focal Loss with Label Smoothing and Square-Root Balanced Alpha Weights.
    """
    def __init__(self, alpha: torch.Tensor = None, gamma: float = 1.5, label_smoothing: float = 0.05):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.alpha, label_smoothing=self.label_smoothing)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()


def apply_rf_augmentation(x: torch.Tensor) -> torch.Tensor:
    """
    Apply fast vectorized RF time jitter and amplitude scaling on training batch.
    """
    B, C, T = x.shape
    # 1. Random amplitude scaling [0.92, 1.08]
    scale = (torch.rand(B, 1, 1, device=x.device) * 0.16 + 0.92)
    x = x * scale
    # 2. Random time roll (+/- 4 timesteps)
    shift = int(torch.randint(-4, 5, (1,)).item())
    if shift != 0:
        x = torch.roll(x, shifts=shift, dims=-1)
    # 3. Tiny RF thermal noise
    noise = torch.randn_like(x) * 0.02
    return x + noise


def load_data(tag: str = "4s"):
    npz_path = MOHITH_REPO / "data" / "processed" / f"windows_{tag}.npz"
    csv_path = MOHITH_REPO / "data" / "features" / f"features_{tag}.csv"
    if not npz_path.exists() or not csv_path.exists():
        raise FileNotFoundError(f"Missing {npz_path} or {csv_path}.")

    df = pd.read_csv(csv_path, usecols=ev.META_COLS)
    z = np.load(npz_path, allow_pickle=False)
    
    print(f"Loading raw tensors and converting to 32 dual-receiver channels (N={len(df)})...")
    C = np.concatenate([dp.channels(z["X"][i:i + 256], z["P"][i:i + 256]) for i in range(0, len(df), 256)])
    return df, C


def run_enhanced_loso(task: str = "state", tag: str = "4s", epochs: int = 30, lr: float = 1.2e-3, gamma: float = 1.5, batch_size: int = 64, dropout: float = 0.25):
    print("=" * 80)
    print(f"  ENHANCED SE-TCN (Dual Pooling + 5-Layer Dilations + Smooth Focal Loss)")
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
    print(f"Total windows: {len(C_task)} | Input shape: [Channels={C_task.shape[1]}, Time={C_task.shape[2]}]")
    print(f"Class distribution:\n{pd.Series(y_str).value_counts().to_string()}\n")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Execution device: {device}")

    outer_results = {}
    all_y_true = []
    all_y_pred = []

    for test_subj in ev.SUBJECTS:
        t0 = time.time()
        train_subjects = [s for s in ev.SUBJECTS if s != test_subj]
        is_cross = test_subj in ev.CROSS_SESSION
        
        tr_mask = np.isin(folds, train_subjects)
        te_mask = (folds == test_subj)

        X_tr_raw = C_task[tr_mask]
        y_tr = y_idx[tr_mask]
        X_te_raw = C_task[te_mask]
        y_te = y_idx[te_mask]

        # Channel-wise Standardization on training subjects only
        mu_tr = X_tr_raw.mean(axis=(0, 2), keepdims=True)
        sd_tr = X_tr_raw.std(axis=(0, 2), keepdims=True) + 1e-6
        X_tr = ((X_tr_raw - mu_tr) / sd_tr).astype(np.float32)
        X_te = ((X_te_raw - mu_tr) / sd_tr).astype(np.float32)

        # Smooth Square-Root Class Weighting
        class_counts = np.bincount(y_tr, minlength=num_classes).astype(np.float32)
        sqrt_weights = 1.0 / np.sqrt(np.maximum(class_counts, 1.0))
        alpha_weights = sqrt_weights / sqrt_weights.mean()
        alpha_tensor = torch.tensor(alpha_weights, dtype=torch.float32).to(device)

        # Model & Optimizer
        model = Enhanced_SE_TCN(in_channels=X_tr.shape[1], num_classes=num_classes, hidden_dim=64, dropout=dropout).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
        criterion = SmoothFocalLoss(alpha=alpha_tensor, gamma=gamma, label_smoothing=0.04)

        tensor_x_tr = torch.from_numpy(X_tr)
        tensor_y_tr = torch.from_numpy(y_tr).long()
        tensor_x_te = torch.from_numpy(X_te).to(device)

        num_batches = int(np.ceil(len(tensor_x_tr) / batch_size))

        # Training Loop with Data Augmentation
        model.train()
        for epoch in range(epochs):
            perm = torch.randperm(len(tensor_x_tr))
            for b in range(num_batches):
                idx = perm[b * batch_size : (b + 1) * batch_size]
                bx = tensor_x_tr[idx].to(device)
                by = tensor_y_tr[idx].to(device)

                # Training augmentation
                bx_aug = apply_rf_augmentation(bx)

                optimizer.zero_grad()
                out = model(bx_aug)
                loss = criterion(out, by)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
                optimizer.step()
            scheduler.step()

        # Evaluate on Held-out Subject
        model.eval()
        with torch.no_grad():
            test_logits = model(tensor_x_te)
            test_preds = test_logits.argmax(dim=1).cpu().numpy()

        acc = accuracy_score(y_te, test_preds)
        bacc = balanced_accuracy_score(y_te, test_preds)
        mf1 = f1_score(y_te, test_preds, average="macro", zero_division=0)

        class_recalls = {}
        for c_idx, c_name in enumerate(classes):
            mask_c = (y_te == c_idx)
            rec_c = float(np.sum((test_preds == c_idx) & mask_c) / np.sum(mask_c)) if np.sum(mask_c) > 0 else 0.0
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
    print("  ENHANCED SE-TCN FINAL RESULTS SUMMARY")
    print("=" * 80)
    print(f"  Mean Accuracy across Folds:          {mean_acc*100:6.2f}% ± {std_acc*100:4.2f}%")
    print(f"  Mean Balanced Accuracy:              {mean_bacc*100:6.2f}% ± {std_bacc*100:4.2f}%")
    print(f"  Mean Macro-F1 Score:                 {mean_mf1:6.4f} ± {std_mf1:5.4f}")
    print(f"  Pooled Overall Accuracy:             {pooled_acc*100:6.2f}%")
    print(f"  Pooled Balanced Accuracy:            {pooled_bacc*100:6.2f}%")
    print(f"  Pooled Macro-F1 Score:               {pooled_mf1:6.4f}")

    print("\n  Per-Class Recall across all 6 test subjects:")
    for c_name in classes:
        recs = [r["recalls"].get(c_name, 0.0) for r in outer_results.values()]
        print(f"    - {c_name:<12}: {np.mean(recs)*100:5.2f}% ± {np.std(recs)*100:4.2f}%")

    cm = confusion_matrix(all_y_true, all_y_pred, labels=list(range(num_classes)))
    print("\n  Pooled Confusion Matrix:")
    col_headers = " ".join([f"{c[:7]:>8}" for c in classes])
    print(f"    {'':<12} {col_headers}")
    for idx, c_name in enumerate(classes):
        row_str = " ".join([f"{val:8d}" for val in cm[idx]])
        print(f"    {c_name:<12} {row_str}")

    # Save to json
    out_dir = Path("results/setcn_multisubject")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"enhanced_setcn_{task}_loso_results.json"
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
    print(f"\nSaved enhanced evaluation results to: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Enhanced SE-TCN LOSO Evaluation")
    parser.add_argument("--task", type=str, default="state", choices=["events", "state", "presence"])
    parser.add_argument("--win", type=str, default="4s")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=1.2e-3)
    parser.add_argument("--gamma", type=float, default=1.5)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.25)
    args = parser.parse_args()

    run_enhanced_loso(task=args.task, tag=args.win, epochs=args.epochs, lr=args.lr, gamma=args.gamma,
                      batch_size=args.batch_size, dropout=args.dropout)


if __name__ == "__main__":
    main()
