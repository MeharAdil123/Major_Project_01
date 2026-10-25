"""
Comprehensive Deep Learning Benchmark & Optimization Suite
Comparing:
  1. Original Baseline CNN-BiLSTM (Cross-Entropy, no attention)
  2. Proposed Enhanced SE-CNN-BiLSTM (Subcarrier SE Attention + BiLSTM + Temporal Attention + Focal Loss)
  3. Proposed Optimized SE-TCN (Dilated Residual TCN + Dual SE Attention + Hybrid Pooling + Focal Loss)
  4. ResNet-SE-TCN Hybrid (Deep Residual Convolutions + Temporal Dilation)

Evaluated across:
  - Task 1: Presence Detection (Empty vs Occupied)
  - Task 2: Binary Fall Detection (Emergency Fall vs All Normal ADLs)
  - Task 3: Postural State Recognition (4 Classes: Sit, Stand, Walk, Lie)
  - Task 4: 5-Class Events Recognition (Fall, Sit_down, Stand_up, Bend_pick, None)
"""

import sys
import os
import time
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, precision_score, recall_score, confusion_matrix

sys.stdout.reconfigure(line_buffering=True)

# Add temp_mohith_repo to path
MOHITH_REPO = Path("temp_mohith_repo").resolve()
if str(MOHITH_REPO) not in sys.path:
    sys.path.insert(0, str(MOHITH_REPO))

from ml import evaluate as ev


# ============================================================================
# 1. ARCHITECTURAL DEFINITIONS
# ============================================================================

class SE_Block(nn.Module):
    """Subcarrier Squeeze-and-Excitation Channel Attention."""
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
        w = self.fc(x).unsqueeze(-1)
        return x * w


class TemporalAttention(nn.Module):
    """Self-attention pooling across temporal dimension."""
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.att = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        scores = self.att(x)
        weights = torch.softmax(scores, dim=1)
        return (x * weights).sum(dim=1)


# --- Model A: Original Baseline CNN-BiLSTM (from Mohith's Phase 4) ---
class Baseline_CNN_BiLSTM(nn.Module):
    def __init__(self, in_channels: int = 32, num_classes: int = 5, hidden_dim: int = 64):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(in_channels, 64, 5, padding=2), nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(64, 64, 5, padding=2), nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2)
        )
        self.rnn = nn.LSTM(64, hidden_dim, batch_first=True, bidirectional=True)
        self.h = nn.Sequential(nn.Dropout(0.3), nn.Linear(hidden_dim * 2, num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        y, _ = self.rnn(x.transpose(1, 2))
        z = y.mean(dim=1)  # Simple average pooling
        return self.h(z)


# --- Model B: Proposed Enhanced SE-CNN-BiLSTM ---
class Enhanced_SE_CNN_BiLSTM(nn.Module):
    def __init__(self, in_channels: int = 32, num_classes: int = 5, hidden_dim: int = 96, dropout: float = 0.25):
        super().__init__()
        self.se = SE_Block(in_channels, reduction=4)
        self.conv = nn.Sequential(
            nn.Conv1d(in_channels, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.MaxPool1d(2),
            nn.Conv1d(64, 96, kernel_size=5, padding=2),
            nn.BatchNorm1d(96),
            nn.GELU(),
            nn.MaxPool1d(2)
        )
        self.lstm = nn.LSTM(
            input_size=96,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=dropout
        )
        self.temporal_att = TemporalAttention(hidden_dim * 2)
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, 64),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.se(x)
        feat = self.conv(x)
        lstm_out, _ = self.lstm(feat.transpose(1, 2))
        pooled = self.temporal_att(lstm_out)
        return self.classifier(pooled)


# --- Model C: Proposed Optimized SE-TCN ---
class DilatedConvBlock(nn.Module):
    def __init__(self, channels: int, dilation: int, dropout: float = 0.15):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(channels, channels, kernel_size=3, padding=dilation, dilation=dilation),
            nn.BatchNorm1d(channels),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(channels, channels, kernel_size=3, padding=dilation, dilation=dilation),
            nn.BatchNorm1d(channels),
            nn.GELU()
        )
        self.se = SE_Block(channels, reduction=4)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.se(self.net(x))


class Optimized_SE_TCN(nn.Module):
    def __init__(self, in_channels: int = 32, num_classes: int = 5, hidden_dim: int = 96, dropout: float = 0.2):
        super().__init__()
        self.stem_se = SE_Block(in_channels, reduction=4)
        self.inp = nn.Sequential(
            nn.Conv1d(in_channels, hidden_dim, kernel_size=1),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU()
        )
        self.blocks = nn.ModuleList([
            DilatedConvBlock(hidden_dim, dilation=1, dropout=dropout),
            DilatedConvBlock(hidden_dim, dilation=2, dropout=dropout),
            DilatedConvBlock(hidden_dim, dilation=4, dropout=dropout),
            DilatedConvBlock(hidden_dim, dilation=8, dropout=dropout),
        ])
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, 64),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem_se(x)
        x = self.inp(x)
        for block in self.blocks:
            x = block(x)
        avg_pool = torch.mean(x, dim=2)
        max_pool = torch.amax(x, dim=2)
        feat = torch.cat([avg_pool, max_pool], dim=1)
        return self.head(feat)


# ============================================================================
# 2. LOSS FUNCTIONS
# ============================================================================

class FocalLoss(nn.Module):
    def __init__(self, alpha: torch.Tensor = None, gamma: float = 2.0, label_smoothing: float = 0.02):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none", weight=self.alpha, label_smoothing=self.label_smoothing)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()


# ============================================================================
# 3. FAST TRAINING HARNESS
# ============================================================================

def train_model(model_cls, X_tr_norm, y_tr, X_te_norm, y_te, num_classes, epochs=30, lr=0.001, batch_size=64, use_focal=True, gamma=2.0):
    device = torch.device("cpu")
    
    # Class weights for focal loss
    class_counts = np.bincount(y_tr, minlength=num_classes).astype(np.float32)
    alpha = len(y_tr) / (num_classes * np.maximum(class_counts, 1.0))
    alpha_tensor = torch.tensor(alpha, dtype=torch.float32).to(device)
    
    model = model_cls(in_channels=X_tr_norm.shape[1], num_classes=num_classes).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    
    if use_focal:
        criterion = FocalLoss(alpha=alpha_tensor, gamma=gamma)
    else:
        criterion = nn.CrossEntropyLoss()
        
    t_x_tr = torch.from_numpy(X_tr_norm)
    t_y_tr = torch.from_numpy(y_tr).long()
    t_x_te = torch.from_numpy(X_te_norm)
    
    num_batches = int(np.ceil(len(t_x_tr) / batch_size))
    
    model.train()
    for ep in range(epochs):
        perm = torch.randperm(len(t_x_tr))
        for b in range(num_batches):
            idx = perm[b * batch_size : (b + 1) * batch_size]
            bx, by = t_x_tr[idx], t_y_tr[idx]
            optimizer.zero_grad()
            out = model(bx)
            loss = criterion(out, by)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
        scheduler.step()
        
    model.eval()
    with torch.no_grad():
        preds = []
        for i in range(0, len(t_x_te), batch_size):
            bx = t_x_te[i : i + batch_size]
            preds.append(model(bx).argmax(dim=1).cpu().numpy())
        y_pred = np.concatenate(preds)
        
    acc = accuracy_score(y_te, y_pred)
    bal_acc = balanced_accuracy_score(y_te, y_pred)
    f1_macro = f1_score(y_te, y_pred, average="macro")
    cm = confusion_matrix(y_te, y_pred)
    return acc, bal_acc, f1_macro, cm, y_pred


if __name__ == "__main__":
    print("=" * 80, flush=True)
    print("  DEEP LEARNING MODEL OPTIMIZATION ENGINE (>95% TARGET)", flush=True)
    print("=" * 80, flush=True)
    
    # Load cached 32-channel tensor
    t0 = time.time()
    C = np.load("data/channels_4s.npy")
    csv_path = MOHITH_REPO / "data" / "features" / "features_4s.csv"
    df = pd.read_csv(csv_path, usecols=ev.META_COLS)
    print(f"Loaded {len(C)} windows in {time.time()-t0:.2f}s. Tensor shape: {C.shape}", flush=True)
    
    all_results = {}

    # =========================================================================
    # TASK 1: PRESENCE DETECTION (Empty vs Occupied)
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("TASK 1: PRESENCE DETECTION (Empty vs Occupied)", flush=True)
    print("=" * 70, flush=True)
    mask_p, y_str_p = ev.task_view(df, "presence")
    classes_p = ["empty", "occupied"]
    c2i_p = {c: i for i, c in enumerate(classes_p)}
    y_idx_p = np.array([c2i_p[v] for v in y_str_p])
    C_p = C[mask_p]
    
    X_tr_p, X_te_p, y_tr_p, y_te_p = train_test_split(C_p, y_idx_p, test_size=0.2, stratify=y_idx_p, random_state=42)
    mu_p = X_tr_p.mean(axis=(0, 2), keepdims=True)
    sd_p = X_tr_p.std(axis=(0, 2), keepdims=True) + 1e-6
    X_tr_p_norm = ((X_tr_p - mu_p) / sd_p).astype(np.float32)
    X_te_p_norm = ((X_te_p - mu_p) / sd_p).astype(np.float32)
    
    # 1A. Baseline CNN-BiLSTM
    acc, bal, f1, cm, _ = train_model(Baseline_CNN_BiLSTM, X_tr_p_norm, y_tr_p, X_te_p_norm, y_te_p, 2, epochs=25, lr=0.001, use_focal=False)
    print(f"[Baseline CNN-BiLSTM]   Accuracy: {acc*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 1B. Enhanced SE-CNN-BiLSTM
    acc_elstm_p, bal, f1, cm, _ = train_model(Enhanced_SE_CNN_BiLSTM, X_tr_p_norm, y_tr_p, X_te_p_norm, y_te_p, 2, epochs=25, lr=0.001, use_focal=True)
    print(f"[Enhanced SE-CNN-BiLSTM] Accuracy: {acc_elstm_p*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 1C. Optimized SE-TCN
    acc_tcn_p, bal_tcn_p, f1_tcn_p, cm_tcn_p, _ = train_model(Optimized_SE_TCN, X_tr_p_norm, y_tr_p, X_te_p_norm, y_te_p, 2, epochs=25, lr=0.001, use_focal=True)
    print(f"[Optimized SE-TCN]      Accuracy: {acc_tcn_p*100:.2f}% | Balanced Acc: {bal_tcn_p*100:.2f}% | Macro-F1: {f1_tcn_p:.4f}", flush=True)
    print("Confusion Matrix (SE-TCN Presence):\n", cm_tcn_p, flush=True)
    all_results["Presence"] = {
        "Baseline_CNN_BiLSTM": acc * 100,
        "Enhanced_SE_CNN_BiLSTM": acc_elstm_p * 100,
        "Optimized_SE_TCN": acc_tcn_p * 100
    }

    # =========================================================================
    # TASK 2: BINARY FALL DETECTION (Emergency Fall vs All Normal ADLs)
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("TASK 2: BINARY FALL DETECTION (Emergency Fall vs All Normal ADLs)", flush=True)
    print("=" * 70, flush=True)
    mask_e, y_str_e = ev.task_view(df, "events")
    # Binary label: 1 if fall, 0 for any non-fall (walk, sit, stand, bend, empty)
    y_bin_fall = np.where(y_str_e == "fall", 1, 0)
    C_f = C[mask_e]
    
    X_tr_f, X_te_f, y_tr_f, y_te_f = train_test_split(C_f, y_bin_fall, test_size=0.2, stratify=y_bin_fall, random_state=42)
    mu_f = X_tr_f.mean(axis=(0, 2), keepdims=True)
    sd_f = X_tr_f.std(axis=(0, 2), keepdims=True) + 1e-6
    X_tr_f_norm = ((X_tr_f - mu_f) / sd_f).astype(np.float32)
    X_te_f_norm = ((X_te_f - mu_f) / sd_f).astype(np.float32)
    
    # 2A. Baseline CNN-BiLSTM
    acc, bal, f1, cm, _ = train_model(Baseline_CNN_BiLSTM, X_tr_f_norm, y_tr_f, X_te_f_norm, y_te_f, 2, epochs=25, lr=0.001, use_focal=False)
    print(f"[Baseline CNN-BiLSTM]   Accuracy: {acc*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 2B. Enhanced SE-CNN-BiLSTM
    acc_elstm_f, bal, f1, cm, _ = train_model(Enhanced_SE_CNN_BiLSTM, X_tr_f_norm, y_tr_f, X_te_f_norm, y_te_f, 2, epochs=25, lr=0.001, use_focal=True)
    print(f"[Enhanced SE-CNN-BiLSTM] Accuracy: {acc_elstm_f*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 2C. Optimized SE-TCN
    acc_tcn_f, bal_tcn_f, f1_tcn_f, cm_tcn_f, _ = train_model(Optimized_SE_TCN, X_tr_f_norm, y_tr_f, X_te_f_norm, y_te_f, 2, epochs=25, lr=0.001, use_focal=True)
    print(f"[Optimized SE-TCN]      Accuracy: {acc_tcn_f*100:.2f}% | Balanced Acc: {bal_tcn_f*100:.2f}% | Macro-F1: {f1_tcn_f:.4f}", flush=True)
    print("Confusion Matrix (SE-TCN Fall Detection):\n", cm_tcn_f, flush=True)
    all_results["Fall_Detection"] = {
        "Baseline_CNN_BiLSTM": acc * 100,
        "Enhanced_SE_CNN_BiLSTM": acc_elstm_f * 100,
        "Optimized_SE_TCN": acc_tcn_f * 100
    }

    # =========================================================================
    # TASK 3: POSTURAL STATE RECOGNITION (4 Classes: Sit, Stand, Walk, Lie)
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("TASK 3: POSTURAL STATE RECOGNITION (4 Classes: Lie, Sit, Stand, Walk)", flush=True)
    print("=" * 70, flush=True)
    mask_s, y_str_s = ev.task_view(df, "state")
    classes_s = sorted(set(y_str_s))
    c2i_s = {c: i for i, c in enumerate(classes_s)}
    y_idx_s = np.array([c2i_s[v] for v in y_str_s])
    C_s = C[mask_s]
    
    X_tr_s, X_te_s, y_tr_s, y_te_s = train_test_split(C_s, y_idx_s, test_size=0.2, stratify=y_idx_s, random_state=42)
    mu_s = X_tr_s.mean(axis=(0, 2), keepdims=True)
    sd_s = X_tr_s.std(axis=(0, 2), keepdims=True) + 1e-6
    X_tr_s_norm = ((X_tr_s - mu_s) / sd_s).astype(np.float32)
    X_te_s_norm = ((X_te_s - mu_s) / sd_s).astype(np.float32)
    
    # 3A. Baseline CNN-BiLSTM
    acc, bal, f1, cm, _ = train_model(Baseline_CNN_BiLSTM, X_tr_s_norm, y_tr_s, X_te_s_norm, y_te_s, 4, epochs=30, lr=0.001, use_focal=False)
    print(f"[Baseline CNN-BiLSTM]   Accuracy: {acc*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 3B. Enhanced SE-CNN-BiLSTM
    acc_elstm_s, bal, f1, cm, _ = train_model(Enhanced_SE_CNN_BiLSTM, X_tr_s_norm, y_tr_s, X_te_s_norm, y_te_s, 4, epochs=30, lr=0.001, use_focal=True)
    print(f"[Enhanced SE-CNN-BiLSTM] Accuracy: {acc_elstm_s*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 3C. Optimized SE-TCN
    acc_tcn_s, bal_tcn_s, f1_tcn_s, cm_tcn_s, _ = train_model(Optimized_SE_TCN, X_tr_s_norm, y_tr_s, X_te_s_norm, y_te_s, 4, epochs=30, lr=0.001, use_focal=True)
    print(f"[Optimized SE-TCN]      Accuracy: {acc_tcn_s*100:.2f}% | Balanced Acc: {bal_tcn_s*100:.2f}% | Macro-F1: {f1_tcn_s:.4f}", flush=True)
    print("Confusion Matrix (SE-TCN State 4-Class):\n", cm_tcn_s, flush=True)
    all_results["Postural_State"] = {
        "Baseline_CNN_BiLSTM": acc * 100,
        "Enhanced_SE_CNN_BiLSTM": acc_elstm_s * 100,
        "Optimized_SE_TCN": acc_tcn_s * 100
    }

    # =========================================================================
    # TASK 4: 5-CLASS EVENTS HAR (Fall, Sit_down, Stand_up, Bend_pick, None)
    # =========================================================================
    print("\n" + "=" * 70, flush=True)
    print("TASK 4: 5-CLASS EVENTS HAR (Fall, Sit, Stand, Bend, None)", flush=True)
    print("=" * 70, flush=True)
    classes_ev = sorted(set(y_str_e))
    c2i_ev = {c: i for i, c in enumerate(classes_ev)}
    y_idx_ev = np.array([c2i_ev[v] for v in y_str_e])
    
    X_tr_e, X_te_e, y_tr_e, y_te_e = train_test_split(C_f, y_idx_ev, test_size=0.2, stratify=y_idx_ev, random_state=42)
    mu_e = X_tr_e.mean(axis=(0, 2), keepdims=True)
    sd_e = X_tr_e.std(axis=(0, 2), keepdims=True) + 1e-6
    X_tr_e_norm = ((X_tr_e - mu_e) / sd_e).astype(np.float32)
    X_te_e_norm = ((X_te_e - mu_e) / sd_e).astype(np.float32)
    
    # 4A. Baseline CNN-BiLSTM
    acc, bal, f1, cm, _ = train_model(Baseline_CNN_BiLSTM, X_tr_e_norm, y_tr_e, X_te_e_norm, y_te_e, 5, epochs=30, lr=0.001, use_focal=False)
    print(f"[Baseline CNN-BiLSTM]   Accuracy: {acc*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 4B. Enhanced SE-CNN-BiLSTM
    acc_elstm_e, bal, f1, cm, _ = train_model(Enhanced_SE_CNN_BiLSTM, X_tr_e_norm, y_tr_e, X_te_e_norm, y_te_e, 5, epochs=30, lr=0.001, use_focal=True)
    print(f"[Enhanced SE-CNN-BiLSTM] Accuracy: {acc_elstm_e*100:.2f}% | Balanced Acc: {bal*100:.2f}% | Macro-F1: {f1:.4f}", flush=True)
    
    # 4C. Optimized SE-TCN
    acc_tcn_e, bal_tcn_e, f1_tcn_e, cm_tcn_e, _ = train_model(Optimized_SE_TCN, X_tr_e_norm, y_tr_e, X_te_e_norm, y_te_e, 5, epochs=30, lr=0.001, use_focal=True)
    print(f"[Optimized SE-TCN]      Accuracy: {acc_tcn_e*100:.2f}% | Balanced Acc: {bal_tcn_e*100:.2f}% | Macro-F1: {f1_tcn_e:.4f}", flush=True)
    print("Confusion Matrix (SE-TCN Events 5-Class):\n", cm_tcn_e, flush=True)
    all_results["Events_5Class"] = {
        "Baseline_CNN_BiLSTM": acc * 100,
        "Enhanced_SE_CNN_BiLSTM": acc_elstm_e * 100,
        "Optimized_SE_TCN": acc_tcn_e * 100
    }

    # Save all results to disk
    out_file = Path("results/deep_models_optimization_results.json")
    out_file.parent.mkdir(exist_ok=True, parents=True)
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved all benchmark results to {out_file}", flush=True)
