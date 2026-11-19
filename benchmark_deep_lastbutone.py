#!/usr/bin/env python3
"""Leak-free deep-learning benchmark for the WiFi-CSI HAR project (Group 10).

Every model is trained and evaluated under the SAME protocol, data, budget and early stopping,
so the numbers can be compared fairly with each other and with the base paper (Strohmayer, 2025).

Protocols (--protocol):
  loso    Leave-one-subject-out, 6 folds. Inner validation = next subject (for early stopping).
          Hardest: tests generalisation to an unseen person (headline result for the report).
  group   5-fold StratifiedGroupKFold, grouped by recording take. No window of a test take is ever
          seen in training, so overlapping windows cannot leak. Inner validation is also grouped.
  random  5-fold StratifiedKFold on individual windows (the OLD 80/20-style protocol).
          LEAKY on purpose: 4 s windows with 0.5-1 s hop overlap 75-88 %, so near-copies of each
          test window are in training. Run it only to show the leakage gap in the report.

Models (--models): cnn_bilstm (baseline), se_cnn_bilstm, se_tcn, wiflexformer (base-paper model,
re-implemented from Sec. 6.2.1 of the thesis), plus any model name from ml/deep.py (tcn, cnn1d, ...).

Tasks (--task): presence, state, events (5-class), fall (binary fall vs everything else).
For events and fall the take-level alarm rule (>= 2 of 3 consecutive windows = fall) is also scored.

Improvements (switch on one at a time to build the ablation table):
  --aug strohmayer   base-paper augmentations (circular rotation, resized crop, amplitude, contrast)
  --tta adabn        test-time adaptation: BatchNorm statistics re-estimated on unlabelled test data
  --hybrid           deep embedding + the hand-crafted f2 features used by the SVM / extra trees
  --loss focal       focal loss instead of class-weighted cross-entropy
  --models feat_only --hybrid   control: hand-crafted features only (no CSI branch)

Examples (run from the "WiFi CSI Agent" folder, same place as train_setcn_enhanced.py):
  python benchmark_deep.py --task presence --protocol loso
  python benchmark_deep.py --task fall --protocol loso --models wiflexformer --aug strohmayer --tta adabn --hybrid
  python benchmark_deep.py --task state --protocol random --models cnn_bilstm   # leakage demo

Outputs: results/benchmark/<task>__<protocol>__<model+variant>.json, one row per run in
results/benchmark/summary.csv and, for events / fall, results/benchmark/fall_alarm.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, train_test_split

# ---------------------------------------------------------------- project imports
REPO = Path("temp_mohith_repo").resolve()
if not (REPO / "ml").exists() and (Path("ml")).exists():
    REPO = Path(".").resolve()
sys.path.insert(0, str(REPO))
from ml import deep as dp  # noqa: E402
from ml import evaluate as ev  # noqa: E402

OUT = Path("results") / "benchmark"


# ================================================================ models
class SEBlock(nn.Module):
    """Squeeze-and-excitation over channels (sub-carrier bands)."""

    def __init__(self, c, r=4):
        super().__init__()
        h = max(c // r, 8)
        self.f = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(c, h), nn.ReLU(), nn.Linear(h, c), nn.Sigmoid())

    def forward(self, x):
        return x * self.f(x).unsqueeze(-1)


class SE_CNN_BiLSTM(nn.Module):
    """Proposed: SE attention on input bands + CNN + 2-layer BiLSTM + temporal attention pooling."""

    def __init__(self, c, k, hidden=96, dropout=0.25):
        super().__init__()
        self.se = SEBlock(c)
        self.conv = nn.Sequential(nn.Conv1d(c, 64, 5, padding=2), nn.BatchNorm1d(64), nn.GELU(), nn.MaxPool1d(2),
                                  nn.Conv1d(64, 96, 5, padding=2), nn.BatchNorm1d(96), nn.GELU(), nn.MaxPool1d(2))
        self.lstm = nn.LSTM(96, hidden, num_layers=2, batch_first=True, bidirectional=True, dropout=dropout)
        self.att = nn.Sequential(nn.Linear(2 * hidden, 64), nn.Tanh(), nn.Linear(64, 1))
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(2 * hidden, 64), nn.GELU(), nn.Dropout(0.2), nn.Linear(64, k))

    def forward(self, x):
        y, _ = self.lstm(self.conv(self.se(x)).transpose(1, 2))
        a = torch.softmax(self.att(y), dim=1)
        return self.head((a * y).sum(dim=1))


class ResDilated(nn.Module):
    def __init__(self, ch, d, dropout):
        super().__init__()
        self.b = nn.Sequential(nn.Conv1d(ch, ch, 3, padding=d, dilation=d), nn.BatchNorm1d(ch), nn.ReLU(), nn.Dropout(dropout),
                               nn.Conv1d(ch, ch, 3, padding=d, dilation=d), nn.BatchNorm1d(ch), nn.ReLU(), nn.Dropout(dropout))

    def forward(self, x):
        return x + self.b(x)


class SE_TCN(nn.Module):
    """Proposed: SE attention + dilated residual TCN (d = 1,2,4,8,16) + avg/max pooling.
    Same design as Enhanced_SE_TCN in train_setcn_enhanced.py."""

    def __init__(self, c, k, ch=64, dropout=0.25):
        super().__init__()
        self.inp = nn.Sequential(nn.Conv1d(c, ch, 1), nn.BatchNorm1d(ch), nn.ReLU())
        self.se1, self.se2 = SEBlock(ch), SEBlock(ch)
        self.l1, self.l2, self.l3 = ResDilated(ch, 1, dropout), ResDilated(ch, 2, dropout), ResDilated(ch, 4, dropout)
        self.l4, self.l5 = ResDilated(ch, 8, dropout), ResDilated(ch, 16, dropout)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(2 * ch, 48), nn.BatchNorm1d(48), nn.ReLU(),
                                  nn.Dropout(dropout / 2), nn.Linear(48, k))

    def forward(self, x):
        x = self.se1(self.inp(x))
        x = self.se2(self.l3(self.l2(self.l1(x))))
        x = self.l5(self.l4(x))
        return self.head(torch.cat([x.mean(-1), x.amax(-1)], dim=1))


class WiFlexFormer(nn.Module):
    """Base-paper model (Strohmayer 2025, Sec. 6.2.1; official code github.com/StrohmayerJ/WiFlexFormer).
    Re-implemented from the thesis description for single-channel input [B, F, T]:
    1-D stem (2x Conv1d k=3, 32 filters, BN, GELU, dropout 0.1) -> Gaussian positional encoding ->
    class token -> 4 Transformer encoder layers (16 heads, FF 64) -> linear head on the class token."""

    def __init__(self, c, k, T, d=32, layers=4, heads=16, ff=64, dropout=0.1):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(c, d, 3, padding=1), nn.BatchNorm1d(d), nn.GELU(), nn.Dropout(dropout),
                                  nn.Conv1d(d, d, 3, padding=1), nn.BatchNorm1d(d), nn.GELU(), nn.Dropout(dropout))
        # Gaussian positional encoding: fixed random Fourier features of the time index.
        g = torch.Generator().manual_seed(0)
        B = torch.randn(1, d // 2, generator=g) * 10.0
        t = torch.linspace(0, 1, T).unsqueeze(1)
        self.register_buffer("pos", torch.cat([torch.sin(2 * math.pi * t @ B), torch.cos(2 * math.pi * t @ B)], dim=1).unsqueeze(0))
        self.cls = nn.Parameter(torch.zeros(1, 1, d))
        layer = nn.TransformerEncoderLayer(d, heads, ff, dropout, activation="gelu", batch_first=True)
        self.enc = nn.TransformerEncoder(layer, layers)
        self.head = nn.Linear(d, k)

    def forward(self, x):
        z = self.stem(x).transpose(1, 2)                      # [B, T, d]
        z = z + self.pos[:, :z.shape[1]]
        z = torch.cat([self.cls.expand(z.shape[0], -1, -1), z], dim=1)
        return self.head(self.enc(z)[:, 0])


class GaussianPosition(nn.Module):
    """Learnable Gaussian positional encoding, as in the official WiFlexFormer code (from THAT)."""

    def __init__(self, d, T, K=10):
        super().__init__()
        self.embedding = nn.Parameter(torch.zeros(K, d))
        nn.init.xavier_uniform_(self.embedding, gain=1)
        self.register_buffer("positions", torch.arange(T).unsqueeze(1).repeat(1, K).float())
        self.mu = nn.Parameter(torch.arange(K, dtype=torch.float).unsqueeze(0) * (T / K))
        self.sigma = nn.Parameter(torch.ones(1, K) * 50.0)

    def forward(self, x):                                       # x [B, T, d]
        a = self.positions[:x.shape[1]] - self.mu
        log_p = -(a * a) / (2 * self.sigma) - torch.log(self.sigma) / 2
        return x + torch.softmax(log_p, dim=1) @ self.embedding


class WiFlexFormerOfficial(nn.Module):
    """Port of the official code (github.com/StrohmayerJ/WiFlexFormer, models/wiflexformer.py),
    amplitude path: same layer sizes, learnable Gaussian positional encoding (K = 10),
    random class token, encoder dropout 0.3, default (ReLU) feed-forward. Best paired with --input raw_amp."""

    def __init__(self, c, k, T, d=32, heads=16, layers=4, ff=64):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(c, d, 3, padding=1), nn.BatchNorm1d(d), nn.GELU(), nn.Dropout(0.1),
                                  nn.Conv1d(d, d, 3, padding=1), nn.BatchNorm1d(d), nn.GELU(), nn.Dropout(0.1))
        self.cls = nn.Parameter(torch.randn(1, 1, d))
        self.pos = GaussianPosition(d, T)
        layer = nn.TransformerEncoderLayer(d, heads, ff, 0.3, batch_first=True)
        self.enc = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.head = nn.Linear(d, k)

    def forward(self, x):
        z = self.pos(self.stem(x).transpose(1, 2))
        z = torch.cat([self.cls.expand(z.shape[0], -1, -1), z], dim=1)
        return self.head(self.enc(z)[:, 0])


class NoCSI(nn.Module):
    """Control for --hybrid: ignores the CSI input entirely (constant embedding), so
    'feat_only --hybrid' = an MLP on the hand-crafted features alone. Shows what the deep CSI branch adds."""

    def __init__(self, c, k):
        super().__init__()
        self.head = nn.Linear(1, k)

    def forward(self, x):
        return self.head(x.new_zeros(x.shape[0], 1))


EXTRA = {
    "feat_only": lambda c, k, T: NoCSI(c, k),
    "se_cnn_bilstm": lambda c, k, T: SE_CNN_BiLSTM(c, k),
    "se_tcn": lambda c, k, T: SE_TCN(c, k),
    "wiflexformer": lambda c, k, T: WiFlexFormer(c, k, T),
    "wiflexformer_official": lambda c, k, T: WiFlexFormerOfficial(c, k, T),
}
DEFAULT_MODELS = ["cnn_bilstm", "se_cnn_bilstm", "se_tcn", "wiflexformer"]



def build(name, c, k, T):
    if name in EXTRA:
        return EXTRA[name](c, k, T)
    return dp.build(name, c, k, T)                               # cnn_bilstm, tcn, cnn1d, that, ...


class Hybrid(nn.Module):
    """--hybrid: deep backbone + hand-crafted f2 features (the ones the SVM / extra-trees use).
    The backbone's final classification layer is removed; its embedding is concatenated with a small
    MLP embedding of the features and classified by a new linear head."""

    def __init__(self, backbone, k, n_feat):
        super().__init__()
        last = [(n, mod) for n, mod in backbone.named_modules() if isinstance(mod, nn.Linear) and mod.out_features == k][-1]
        name, lin = last
        parent = backbone.get_submodule(name.rsplit(".", 1)[0]) if "." in name else backbone
        setattr(parent, name.rsplit(".", 1)[-1], nn.Identity())
        self.backbone = backbone
        self.fmlp = nn.Sequential(nn.Linear(n_feat, 64), nn.BatchNorm1d(64), nn.GELU(), nn.Dropout(0.3),
                                  nn.Linear(64, 32), nn.GELU())
        self.head = nn.Sequential(nn.Dropout(0.3), nn.Linear(lin.in_features + 32, k))

    def forward(self, x, f):
        return self.head(torch.cat([self.backbone(x), self.fmlp(f)], dim=1))


def build_full(name, c, k, T, n_feat=0):
    m = build(name, c, k, T)
    return Hybrid(m, k, n_feat) if n_feat else m


def fwd(m, x, f=None):
    return m(x) if f is None else m(x, f)


def n_params(m):
    return int(sum(p.numel() for p in m.parameters()))


# ================================================================ augmentation
def aug_strohmayer(x, g, p=0.5):
    """Augmentations from the base paper (Strohmayer 2025, Sec. 6.3.1), each applied with p = 0.5:
    randomCircularRotation (time), randomResizedCrop (crop -> slow-down / compress -> speed-up),
    randomAmplitude (per receiver), randomContrast (per sub-carrier band channel), U(0.75, 1.25)."""
    B, C, T = x.shape
    x = x.clone()
    u = lambda *s: torch.rand(*s, generator=g)  # noqa: E731
    # circular rotation
    for i in torch.nonzero(u(B) < p).flatten().tolist():
        x[i] = torch.roll(x[i], int(torch.randint(1, T, (1,), generator=g)), dims=-1)
    # resized crop (speed change)
    for i in torch.nonzero(u(B) < p).flatten().tolist():
        L = int(torch.randint(T // 2, T + 1, (1,), generator=g))
        if L >= T:
            continue
        if float(u(1)) < 0.5:                                     # crop + stretch = slower activity
            s = int(torch.randint(0, T - L + 1, (1,), generator=g))
            x[i] = F.interpolate(x[i:i + 1, :, s:s + L], size=T, mode="linear", align_corners=False)[0]
        else:                                                     # compress + wrap = faster activity
            z = F.interpolate(x[i:i + 1], size=L, mode="linear", align_corners=False)[0]
            x[i] = torch.cat([z, z[:, :T - L]], dim=-1)
    # amplitude per receiver (channels 0-15 = RX1, 16-31 = RX2)
    sel = (u(B, 1, 1) < p).float()
    half = C // 2
    scale = torch.cat([0.75 + 0.5 * u(B, 1, 1).expand(B, half, 1), 0.75 + 0.5 * u(B, 1, 1).expand(B, C - half, 1)], dim=1)
    x = x * (sel * scale + (1 - sel))
    # contrast per channel around its mean
    sel = (u(B, 1, 1) < p).float()
    fac = 0.75 + 0.5 * u(B, C, 1)
    mu = x.mean(dim=-1, keepdim=True)
    x = sel * ((x - mu) * fac + mu) + (1 - sel) * x
    return x


def augment(x, g, kind):
    if kind == "none":
        return x
    if kind == "strohmayer":
        return aug_strohmayer(x, g)
    return dp.augment(x, g)                                       # project default (shift, scale, noise, band dropout)


# ================================================================ training
class FocalLoss(nn.Module):
    def __init__(self, weight=None, gamma=2.0):
        super().__init__()
        self.weight, self.gamma = weight, gamma

    def forward(self, logits, y):
        ce = F.cross_entropy(logits, y, weight=self.weight, reduction="none")
        pt = torch.exp(-F.cross_entropy(logits, y, reduction="none"))
        return ((1 - pt) ** self.gamma * ce).mean()


def macro_f1(y, p, k):
    f = []
    for c in range(k):
        if (y == c).any():
            tp, fp, fn = ((p == c) & (y == c)).sum(), ((p == c) & (y != c)).sum(), ((p != c) & (y == c)).sum()
            f.append(2 * tp / max(2 * tp + fp + fn, 1))
    return float(np.mean(f)) if f else 0.0


def predict(m, X, Fx=None, batch=256):
    m.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), batch):
            f = None if Fx is None else torch.from_numpy(Fx[i:i + batch])
            out.append(fwd(m, torch.from_numpy(X[i:i + batch]), f).argmax(1).numpy())
    return np.concatenate(out)


def adabn(m, X, Fx=None, batch=256):
    """--tta adabn: test-time adaptation without labels. BatchNorm running statistics are re-estimated
    on the (unlabelled) test windows, so the network is normalised to the new subject / session.
    A simple member of the test-time-adaptation family used by DATTA in the base paper."""
    bns = [mod for mod in m.modules() if isinstance(mod, nn.modules.batchnorm._BatchNorm)]
    if not bns:
        return 0
    for b in bns:
        b.reset_running_stats()
        b.momentum = None                                          # cumulative average over all test batches
    m.eval()
    for b in bns:
        b.train()
    with torch.no_grad():
        for i in range(0, len(X), batch):
            xb = torch.from_numpy(X[i:i + batch])
            if len(xb) < 2:
                continue
            fwd(m, xb, None if Fx is None else torch.from_numpy(Fx[i:i + batch]))
    m.eval()
    return len(bns)


def train_one(name, Xtr, ytr, Xva, yva, k, seed, a, Ftr=None, Fva=None):
    """Same budget for every model: AdamW, class-weighted loss, augmentation on training windows only,
    early stopping on the inner-validation macro-F1. Returns (model, best_epoch, epochs_run)."""
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    m = build_full(name, Xtr.shape[1], k, Xtr.shape[2], 0 if Ftr is None else Ftr.shape[1])
    opt = torch.optim.AdamW(m.parameters(), lr=a.lr, weight_decay=a.wd)
    cnt = np.bincount(ytr, minlength=k).astype(np.float64)
    w = torch.tensor(len(ytr) / (k * np.maximum(cnt, 1)), dtype=torch.float32)   # "balanced" weights
    lossf = FocalLoss(w, a.gamma) if a.loss == "focal" else nn.CrossEntropyLoss(weight=w)
    xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr.astype(np.int64))
    ft = None if Ftr is None else torch.from_numpy(Ftr)
    best, best_state, best_ep, wait, ep = -1.0, None, 0, 0, 0
    for ep in range(1, a.epochs + 1):
        m.train()
        perm = torch.randperm(len(xt), generator=g)
        for i in range(0, len(xt), a.batch_size):
            b = perm[i:i + a.batch_size]
            if len(b) < 2:                                    # BatchNorm needs >1 sample
                continue
            opt.zero_grad()
            loss = lossf(fwd(m, augment(xt[b], g, a.aug), None if ft is None else ft[b]), yt[b])
            loss.backward()
            nn.utils.clip_grad_norm_(m.parameters(), 2.0)
            opt.step()
        f1 = macro_f1(yva, predict(m, Xva, Fva), k)
        if f1 > best:
            best, best_ep, wait = f1, ep, 0
            best_state = {kk: v.detach().clone() for kk, v in m.state_dict().items()}
        else:
            wait += 1
            if wait >= a.patience:
                break
    m.load_state_dict(best_state)
    m.eval()
    return m, best_ep, ep, best


# ================================================================ protocols
def make_splits(protocol, y, folds, groups, seed, n_splits=5):
    """Yields (fold_name, train_mask, val_mask, test_mask). Validation never overlaps test."""
    n = len(y)
    if protocol == "loso":
        for test in ev.SUBJECTS:
            if not (folds == test).any():
                continue
            train_subj = [s for s in ev.SUBJECTS if s != test]
            val = train_subj[ev.SUBJECTS.index(test) % len(train_subj)]
            yield test, np.isin(folds, [s for s in train_subj if s != val]), folds == val, folds == test
        return
    idx = np.arange(n)
    if protocol == "group":
        outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for i, (trv, te) in enumerate(outer.split(idx, y, groups)):
            inner = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
            tr_i, va_i = next(inner.split(trv, y[trv], groups[trv]))
            yield f"G{i + 1}", _mask(n, trv[tr_i]), _mask(n, trv[va_i]), _mask(n, te)
        return
    if protocol == "random":                                  # leaky baseline protocol
        outer = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for i, (trv, te) in enumerate(outer.split(idx, y)):
            tr_i, va_i = train_test_split(trv, test_size=0.2, stratify=y[trv], random_state=seed)
            yield f"R{i + 1}", _mask(n, tr_i), _mask(n, va_i), _mask(n, te)
        return
    raise ValueError(protocol)


def _mask(n, ix):
    m = np.zeros(n, bool)
    m[ix] = True
    return m


# ================================================================ data
def channels_static(X, P):
    """Same 32 band channels as ml/deep.py channels(), but WITHOUT removing the window mean, so the
    static signal level (posture, presence) stays in the input."""
    X = np.asarray(X, np.float32)
    P = np.asarray(P, np.float32)
    bands = np.array_split(np.arange(X.shape[-1]), dp.N_BANDS)
    out = []
    for r in range(X.shape[1]):
        a = X[:, r]
        w = a.mean(axis=1, keepdims=True) ** 2
        z = np.exp(1j * P[:, r])
        dev = np.angle(z * np.conj(z.mean(axis=1, keepdims=True)))
        for b in bands:
            out.append(a[:, :, b].mean(axis=2))
        for b in bands:
            wb = w[:, :, b]
            out.append((dev[:, :, b] * wb).sum(axis=2) / np.maximum(wb.sum(axis=2), 1e-9))
    C = np.stack(out, axis=1)
    T = C.shape[2] // dp.DECIM * dp.DECIM
    return C[:, :, :T].reshape(C.shape[0], C.shape[1], T // dp.DECIM, dp.DECIM).mean(axis=3).astype(np.float32)


def raw_amplitude(X, P=None):
    """Base-paper style input: amplitude of every sub-carrier, both receivers stacked
    (RX1 114 + RX2 114 = 228 channels), decimated 100 -> 50 Hz, static level kept."""
    X = np.asarray(X, np.float32)                                  # [N, 2, T, 114]
    N, R, T0, S = X.shape
    A = np.transpose(X, (0, 1, 3, 2)).reshape(N, R * S, T0)        # [N, 228, T]
    T = T0 // dp.DECIM * dp.DECIM
    return A[:, :, :T].reshape(N, R * S, T // dp.DECIM, dp.DECIM).mean(axis=3).astype(np.float32)


INPUTS = {"dyn": (dp.channels, "channels_{tag}.npy"),
          "static": (channels_static, "channels_static_{tag}.npy"),
          "raw_amp": (raw_amplitude, "rawamp_{tag}.npy")}


def load_data(tag, feature_set=None, mode="dyn"):
    csv_path = REPO / "data" / "features" / f"features_{tag}.csv"
    df = pd.read_csv(csv_path, usecols=ev.META_COLS)
    fn, name = INPUTS[mode]
    cache = Path("data") / name.format(tag=tag)
    if cache.exists():
        C = np.load(cache)
    else:
        npz = REPO / "data" / "processed" / f"windows_{tag}.npz"
        print(f" Building {cache} from {npz} (first time only) ...", flush=True)
        z = np.load(npz, allow_pickle=False)
        C = np.concatenate([fn(z["X"][i:i + 256], z["P"][i:i + 256]) for i in range(0, len(df), 256)])
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, C)
    assert len(C) == len(df), f"cache has {len(C)} windows but CSV has {len(df)} - delete {cache} and rerun"
    Fx = None
    if feature_set:
        cols = ev.feature_set(feature_set)
        Fx = pd.read_csv(csv_path, usecols=cols)[cols].to_numpy(np.float32)
    return df, C.astype(np.float32), Fx


def select_rx(C, rx):
    """Keep one receiver's channels (first half = RX1, second half = RX2) or both."""
    if rx == "both":
        return C
    h = C.shape[1] // 2
    return C[:, :h] if rx == "1" else C[:, h:]


def task_labels(df, task):
    """presence / state / events from ml/evaluate.py, plus 'fall' = binary fall vs everything else."""
    if task == "fall":
        lab = df["window_label"].astype(str).to_numpy()
        src = df["source"].astype(str).to_numpy()
        return np.ones(len(df), bool), np.where((src == "event") & (lab == "fall"), "fall", "rest")
    return ev.task_view(df, task)


def fall_alarm(dfm, pred_fall, need=2, of=3):
    """Take-level alarm rule as in the live system: alarm if >= `need` of the last `of` windows (time order)
    are predicted 'fall'. Returns falls caught, look-alike (bend_pick) takes with alarm, other takes with alarm."""
    d = dfm[["session_id", "take_id", "activity_label", "kind", "t_start"]].copy()
    d["p"] = pred_fall.astype(int)
    res = dict(fall_takes=0, fall_caught=0, lookalike_takes=0, lookalike_alarm=0, other_takes=0, other_alarm=0)
    for _, t in d.groupby(["session_id", "take_id"]):
        s = t.sort_values("t_start")["p"].to_numpy()
        alarm = bool(len(s) and (np.convolve(s, np.ones(of, int), "valid") >= need).any()) if len(s) >= of else bool(s.sum() >= need)
        act, kind = str(t["activity_label"].iloc[0]), str(t["kind"].iloc[0])
        key = "fall" if (kind == "event" and act == "fall") else "lookalike" if act == "bend_pick" else "other"
        res[f"{key}_takes"] += 1
        res[{"fall": "fall_caught", "lookalike": "lookalike_alarm", "other": "other_alarm"}[key]] += int(alarm)
    return res


def latency_ms(m, c, T, n_feat=0, reps=50):
    """Single-window CPU latency (batch = 1), as in a live system."""
    x = torch.randn(1, c, T)
    f = torch.randn(1, n_feat) if n_feat else None
    m.eval()
    with torch.no_grad():
        for _ in range(5):
            fwd(m, x, f)
        t0 = time.perf_counter()
        for _ in range(reps):
            fwd(m, x, f)
    return (time.perf_counter() - t0) / reps * 1000


def _append_csv(path, keys, rows):
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


# ================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="events", choices=["presence", "state", "events", "fall"])
    ap.add_argument("--protocol", default="loso", choices=["loso", "group", "random"])
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--win", default="4s")
    ap.add_argument("--epochs", type=int, default=30, help="maximum epochs (early stopping usually ends sooner)")
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--wd", type=float, default=1e-2, help="AdamW weight decay")
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--loss", default="wce", choices=["wce", "focal"], help="weighted cross-entropy or focal")
    ap.add_argument("--gamma", type=float, default=2.0)
    ap.add_argument("--aug", default="default", choices=["default", "strohmayer", "none"],
                    help="training augmentation: project default, base-paper set, or none")
    ap.add_argument("--tta", default="none", choices=["none", "adabn"], help="test-time adaptation")
    ap.add_argument("--hybrid", action="store_true", help="add hand-crafted f2 features to the deep model")
    ap.add_argument("--features", default="dynamic", help="feature set for --hybrid (dynamic | all | ...)")
    ap.add_argument("--input", default="dyn", choices=["dyn", "static", "raw_amp"],
                    help="dyn = 32 bands, window mean removed (default) | static = 32 bands, mean kept | "
                         "raw_amp = amplitude of all 228 sub-carriers (base-paper style)")
    ap.add_argument("--rx", default="both", choices=["both", "1", "2"], help="use both receivers or only RX1 / RX2")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    if "feat_only" in a.models and not a.hybrid:
        ap.error("feat_only needs --hybrid (it is the features-only control)")
    torch.set_num_threads(a.threads)

    feats = a.features
    if a.hybrid and a.rx != "both" and feats in ("dynamic", "all"):
        feats = f"rx{a.rx}_dynamic" if feats == "dynamic" else f"rx{a.rx}"   # features of that receiver only
    df, C, Fall = load_data(a.win, feats if a.hybrid else None, a.input)
    C = select_rx(C, a.rx)
    mask, y_str = task_labels(df, a.task)
    C, folds, dfm = C[mask], ev.assign_folds(df)[mask], df[mask].reset_index(drop=True)
    Fall = None if Fall is None else Fall[mask]
    groups = (dfm["session_id"].astype(str) + "|" + dfm["take_id"].astype(str)).to_numpy()
    classes = sorted(set(y_str.tolist()))
    y = np.array([classes.index(v) for v in y_str])
    k, c, T = len(classes), C.shape[1], C.shape[2]
    nf = 0 if Fall is None else Fall.shape[1]
    tags = ([f"in-{a.input}"] if a.input != "dyn" else []) + ([f"rx{a.rx}"] if a.rx != "both" else []) + \
           ([f"aug-{a.aug}"] if a.aug != "default" else []) + (["adabn"] if a.tta == "adabn" else []) + \
           ([f"hybrid-{a.features}"] if a.hybrid else []) + (["focal"] if a.loss == "focal" else []) + \
           ([f"lr{a.lr:g}"] if a.lr != 1e-3 else []) + ([f"wd{a.wd:g}"] if a.wd != 1e-2 else []) + \
           ([f"bs{a.batch_size}"] if a.batch_size != 64 else [])
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print(f" Task {a.task} | protocol {a.protocol.upper()} | {len(y)} windows | {len(set(groups))} takes | "
          f"input [{c}, {T}] | classes {classes}")
    print(f" Class counts: {dict(zip(classes, np.bincount(y, minlength=k).tolist()))} | seeds {a.seeds}")
    print(f" Variant: {'+'.join(tags) or 'plain'}" + (f" | {nf} hand-crafted features" if nf else ""))
    if a.protocol == "random":
        print(" WARNING: 'random' splits overlapping windows of the same take -> leaky, optimistic numbers.")
    print("=" * 88)

    rows, alarm_rows = [], []
    for name in a.models:
        label = "+".join([name] + tags)
        t_all = time.time()
        fold_f1, fold_bacc, fold_acc, info, fold_val = [], [], [], {}, []
        pred_all = {s: np.empty(len(y), dtype=object) for s in a.seeds}
        for seed in a.seeds:
            for fname, tr, va, te in make_splits(a.protocol, y, folds, groups, seed):
                mu = C[tr | va].mean(axis=(0, 2), keepdims=True)          # training statistics only
                sd = C[tr | va].std(axis=(0, 2), keepdims=True) + 1e-6
                norm = lambda x: ((x - mu) / sd).astype(np.float32)  # noqa: E731
                Ftr = Fva = Fte = None
                if Fall is not None:                                       # features: train median / mean / std
                    med = np.nanmedian(Fall[tr | va], axis=0)
                    Ff = np.where(np.isnan(Fall), med, Fall)
                    fm, fs = Ff[tr | va].mean(axis=0), Ff[tr | va].std(axis=0) + 1e-6
                    Ff = np.clip((Ff - fm) / fs, -6, 6).astype(np.float32)
                    Ftr, Fva, Fte = Ff[tr], Ff[va], Ff[te]
                t0 = time.time()
                mdl, best_ep, ran, vf1 = train_one(name, norm(C[tr]), y[tr], norm(C[va]), y[va], k, seed, a, Ftr, Fva)
                if a.tta == "adabn":
                    adabn(mdl, norm(C[te]), Fte)
                p = predict(mdl, norm(C[te]), Fte)
                pred_all[seed][te] = np.array(classes)[p]
                f1 = macro_f1(y[te], p, k)
                bacc = balanced_accuracy_score(y[te], p)
                acc = float((p == y[te]).mean())
                fold_f1.append(f1), fold_bacc.append(bacc), fold_acc.append(acc)
                fold_val.append(vf1)
                info[f"seed{seed}_{fname}"] = dict(val_f1=round(vf1, 4), macro_f1=round(f1, 4), bal_acc=round(bacc, 4), acc=round(acc, 4),
                                                    best_epoch=best_ep, epochs_run=ran, n_test=int(te.sum()))
                print(f"  {label:<30} s{seed} {fname:<3} | Acc {acc * 100:6.2f}% | BalAcc {bacc * 100:6.2f}% | "
                      f"Macro-F1 {f1:.3f} | ep {best_ep:>2}/{ran:<2} | {time.time() - t0:5.1f}s", flush=True)

        # pooled metrics over all test windows (first seed) - includes fall / presence detail
        s0 = a.seeds[0]
        pooled = ev.metrics(y_str, pred_all[s0].astype(str), classes)
        model0 = build_full(name, c, k, T, nf)
        row = dict(task=a.task, protocol=a.protocol, model=label, params=n_params(model0),
                   latency_ms=round(latency_ms(model0, c, T, nf), 2),
                   macro_f1_mean=round(float(np.mean(fold_f1)), 4), macro_f1_std=round(float(np.std(fold_f1)), 4),
                   bal_acc_mean=round(float(np.mean(fold_bacc)), 4), acc_mean=round(float(np.mean(fold_acc)), 4),
                   pooled_macro_f1=round(pooled["macro_f1"], 4), loss=a.loss, seeds=len(a.seeds),
                   wall_s=round(time.time() - t_all, 1), val_f1_mean=round(float(np.mean(fold_val)), 4),
                   lr=a.lr, wd=a.wd, batch_size=a.batch_size, patience=a.patience, epochs=a.epochs)
        if "fall_vs_rest" in pooled:
            fv = pooled["fall_vs_rest"]
            row.update(fall_recall=round(fv["sensitivity"], 4), fall_precision=round(fv["precision"], 4),
                       fall_false_alarm_rate=round(fv["false_alarm_rate"], 4))
            al = fall_alarm(dfm, pred_all[s0].astype(str) == "fall")
            alarm_rows.append(dict(task=a.task, protocol=a.protocol, model=label, **al))
            row["alarm"] = al
            if len(a.seeds) > 1:                                   # alarm counts for every seed, not only the first
                per = {s: fall_alarm(dfm, pred_all[s].astype(str) == "fall") for s in a.seeds}
                row["alarm_per_seed"] = per
                row["alarm_mean"] = {kk: round(float(np.mean([v[kk] for v in per.values()])), 1) for kk in al}
        if "presence_sensitivity" in pooled:
            row.update(presence_sens=round(pooled["presence_sensitivity"], 4),
                       presence_spec=round(pooled["presence_specificity"], 4))
        rows.append(row)
        safe = label.replace("+", "__")
        (OUT / f"{a.task}__{a.protocol}__{safe}.json").write_text(
            json.dumps(dict(summary=row, folds=info, pooled=pooled, args=vars(a),
                            predictions={str(sd): pred_all[sd].astype(str).tolist() for sd in a.seeds}), indent=1))

        print(f"  >> {label}: inner-validation macro-F1 {row['val_f1_mean']:.3f} (use THIS to choose settings)")
        print(f"  >> {label}: Macro-F1 {row['macro_f1_mean']:.3f} ± {row['macro_f1_std']:.3f} | "
              f"BalAcc {row['bal_acc_mean'] * 100:.1f}% | Acc {row['acc_mean'] * 100:.1f}% | "
              f"{row['params']:,} params | {row['latency_ms']} ms/window")
        if "fall_recall" in row:
            al = row["alarm"]
            print(f"  Fall windows: recall {row['fall_recall'] * 100:.1f}%, precision {row['fall_precision'] * 100:.1f}%, "
                  f"false-alarm rate {row['fall_false_alarm_rate'] * 100:.1f}%")
            print(f"  Fall ALARM (2 of 3 windows): {al['fall_caught']}/{al['fall_takes']} falls caught | "
                  f"alarms on {al['lookalike_alarm']}/{al['lookalike_takes']} bend_pick look-alikes | "
                  f"{al['other_alarm']}/{al['other_takes']} other takes  (seed {a.seeds[0]})")
            if "alarm_per_seed" in row:
                for sd, v in row["alarm_per_seed"].items():
                    print(f"     seed {sd}: {v['fall_caught']}/{v['fall_takes']} caught | {v['lookalike_alarm']}/{v['lookalike_takes']} look-alikes | "
                          f"{v['other_alarm']}/{v['other_takes']} other")
                am = row["alarm_mean"]
                print(f"     MEAN over seeds: {am['fall_caught']}/{al['fall_takes']} caught | {am['lookalike_alarm']}/{al['lookalike_takes']} look-alikes | "
                      f"{am['other_alarm']}/{al['other_takes']} other")
        print("  Per-class recall (pooled): " +
              ", ".join(f"{cl} {pooled['per_class'][cl]['recall'] * 100:.1f}%" for cl in classes))
        print("  Confusion matrix (rows = truth):")
        print("      " + " ".join(f"{cl[:8]:>9}" for cl in classes))
        for cl, r in zip(classes, pooled["confusion"]["matrix"]):
            print(f"      {cl[:8]:<8}" + " ".join(f"{v:>9}" for v in r))
        print("-" * 88, flush=True)

    # ---------------------------------------------------------- summary
    print(f"\n SUMMARY  ({a.task}, {a.protocol})")
    print(f" {'model':<34}{'macro-F1':>16}{'bal-acc':>10}{'acc':>9}{'params':>10}{'ms/win':>9}")
    for r in rows:
        print(f" {r['model']:<34}{r['macro_f1_mean']:>9.3f} ± {r['macro_f1_std']:.3f}{r['bal_acc_mean'] * 100:>9.1f}%"
              f"{r['acc_mean'] * 100:>8.1f}%{r['params']:>10,}{r['latency_ms']:>9}")
    keys = ["task", "protocol", "model", "macro_f1_mean", "macro_f1_std", "bal_acc_mean", "acc_mean", "pooled_macro_f1",
            "fall_recall", "fall_precision", "fall_false_alarm_rate", "presence_sens", "presence_spec",
            "params", "latency_ms", "loss", "seeds", "wall_s"]
    _append_csv(OUT / "summary.csv", keys, rows)
    _append_csv(OUT / "tuning.csv", ["task", "protocol", "model", "lr", "wd", "batch_size", "patience", "epochs", "seeds",
                                      "val_f1_mean", "macro_f1_mean", "macro_f1_std"], rows)
    if alarm_rows:
        _append_csv(OUT / "fall_alarm.csv", ["task", "protocol", "model", "fall_takes", "fall_caught", "lookalike_takes",
                                            "lookalike_alarm", "other_takes", "other_alarm"], alarm_rows)
    print(f"\n Saved per-model JSON to {OUT}/ and appended to {OUT / 'summary.csv'}"
          + (f" and {OUT / 'fall_alarm.csv'}" if alarm_rows else ""))


if __name__ == "__main__":
    main()
