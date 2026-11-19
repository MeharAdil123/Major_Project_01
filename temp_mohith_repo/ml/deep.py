"""Track C: deep models (PyTorch, CPU), scaled down for ~2.6k windows.

Input per window: [C=32, T] = per RX, 8 sub-carrier bands of gain-normalised amplitude and 8 bands of
amplitude-weighted sanitised phase deviation, decimated to 50 Hz (T = 50 x window length), minus the
window mean per channel (dynamic content only, D-024), standardised with training-fold statistics.

Architectures follow the CSI HAR literature / SenseFi benchmark families, reduced in width:
  cnn1d, lstm, gru, bilstm, cnn_lstm, cnn_bilstm, ablstm (attention-BiLSTM, Chen et al. 2019),
  tcn (dilated residual conv), resnet1d, that (two-stream transformer, THAT-style, Li et al. 2021).
Training budget (same for every model): AdamW lr 1e-3, weight decay 1e-2, batch 64, at most
MAX_EPOCHS epochs, early stopping on the inner-validation subject's macro-F1 (patience PATIENCE),
class-weighted cross-entropy; augmentation on training windows only: time shift, amplitude scaling,
Gaussian noise, band (channel) dropout.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn

MAX_EPOCHS = 30
PATIENCE = 6
BATCH = 64
N_BANDS = 8
DECIM = 2                                        # 100 Hz -> 50 Hz


# ------------------------------------------------------------------ input
def channels(X: np.ndarray, P: np.ndarray) -> np.ndarray:
    """Format 2 X, P [N, 2, T, 114] -> [N, 32, T/2] float32 (see module doc)."""
    X = np.asarray(X, np.float32)
    P = np.asarray(P, np.float32)
    bands = np.array_split(np.arange(X.shape[-1]), N_BANDS)
    out = []
    for r in range(X.shape[1]):
        a = X[:, r]
        w = a.mean(axis=1, keepdims=True) ** 2                     # [N,1,S] weights per carrier
        z = np.exp(1j * P[:, r])
        dev = np.angle(z * np.conj(z.mean(axis=1, keepdims=True)))  # deviation from the window's circular mean
        for b in bands:
            out.append(a[:, :, b].mean(axis=2))
        for b in bands:
            wb = w[:, :, b]
            out.append((dev[:, :, b] * wb).sum(axis=2) / np.maximum(wb.sum(axis=2), 1e-9))
    C = np.stack(out, axis=1)                                       # [N, 32, T]
    T = C.shape[2] // DECIM * DECIM
    C = C[:, :, :T].reshape(C.shape[0], C.shape[1], T // DECIM, DECIM).mean(axis=3)
    return (C - C.mean(axis=2, keepdims=True)).astype(np.float32)


def augment(x: torch.Tensor, g: torch.Generator) -> torch.Tensor:
    B, C, T = x.shape
    shift = int(torch.randint(-T // 10, T // 10 + 1, (1,), generator=g))
    x = torch.roll(x, shift, dims=2)
    x = x * (1 + 0.1 * (torch.rand(B, C, 1, generator=g) * 2 - 1))
    x = x + 0.05 * torch.randn(x.shape, generator=g)
    keep = (torch.rand(B, C, 1, generator=g) > 0.1).float()
    return x * keep


# ------------------------------------------------------------------ models
class CNN1D(nn.Module):
    def __init__(self, c, k):
        super().__init__()
        blk = lambda i, o: nn.Sequential(nn.Conv1d(i, o, 5, padding=2), nn.BatchNorm1d(o), nn.ReLU(), nn.MaxPool1d(2))  # noqa: E731
        self.f = nn.Sequential(blk(c, 32), blk(32, 64), blk(64, 64), nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.h = nn.Sequential(nn.Dropout(0.3), nn.Linear(64, k))

    def forward(self, x):
        return self.h(self.f(x))


class RNN(nn.Module):
    def __init__(self, c, k, cell="lstm", bi=False, conv=False, attention=False, hidden=64):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(c, 64, 5, padding=2), nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2),
                                  nn.Conv1d(64, 64, 5, padding=2), nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2)) if conv else None
        rnn = nn.LSTM if cell == "lstm" else nn.GRU
        self.rnn = rnn(64 if conv else c, hidden, batch_first=True, bidirectional=bi)
        d = hidden * (2 if bi else 1)
        self.att = nn.Sequential(nn.Linear(d, 64), nn.Tanh(), nn.Linear(64, 1)) if attention else None
        self.h = nn.Sequential(nn.Dropout(0.3), nn.Linear(d, k))

    def forward(self, x):
        if self.conv is not None:
            x = self.conv(x)
        y, _ = self.rnn(x.transpose(1, 2))                       # [B, T, d]
        if self.att is not None:
            a = torch.softmax(self.att(y), dim=1)
            z = (a * y).sum(dim=1)
        else:
            z = y.mean(dim=1)
        return self.h(z)


class TCN(nn.Module):
    def __init__(self, c, k, ch=64, levels=4):
        super().__init__()
        self.inp = nn.Conv1d(c, ch, 1)
        self.blocks = nn.ModuleList()
        for i in range(levels):
            d = 2 ** i
            self.blocks.append(nn.Sequential(nn.Conv1d(ch, ch, 3, padding=d, dilation=d), nn.BatchNorm1d(ch), nn.ReLU(),
                                             nn.Dropout(0.1), nn.Conv1d(ch, ch, 3, padding=d, dilation=d), nn.BatchNorm1d(ch)))
        self.h = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Dropout(0.3), nn.Linear(ch, k))

    def forward(self, x):
        x = self.inp(x)
        for b in self.blocks:
            x = torch.relu(x + b(x))
        return self.h(x)


class ResNet1D(nn.Module):
    def __init__(self, c, k, ch=64):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(c, ch, 7, padding=3), nn.BatchNorm1d(ch), nn.ReLU())
        self.blocks = nn.ModuleList([nn.Sequential(nn.Conv1d(ch, ch, 5, padding=2), nn.BatchNorm1d(ch), nn.ReLU(),
                                                   nn.Conv1d(ch, ch, 3, padding=1), nn.BatchNorm1d(ch)) for _ in range(3)])
        self.pool = nn.MaxPool1d(2)
        self.h = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Dropout(0.3), nn.Linear(ch, k))

    def forward(self, x):
        x = self.stem(x)
        for b in self.blocks:
            x = self.pool(torch.relu(x + b(x)))
        return self.h(x)


class THAT(nn.Module):
    """Two-stream transformer: a temporal stream (tokens = time patches) and a channel stream
    (tokens = channels), each a small encoder, mean-pooled and concatenated (after THAT, AAAI 2021)."""

    def __init__(self, c, k, T, d=64, patch=5):
        super().__init__()
        self.patch = nn.Conv1d(c, d, patch, stride=patch)
        n_tok = T // patch
        self.pos = nn.Parameter(torch.zeros(1, n_tok, d))
        enc = lambda: nn.TransformerEncoder(nn.TransformerEncoderLayer(d, 4, 2 * d, 0.1, batch_first=True), 2)  # noqa: E731
        self.temporal = enc()
        self.ch_in = nn.Linear(T, d)
        self.channel = nn.TransformerEncoder(nn.TransformerEncoderLayer(d, 4, 2 * d, 0.1, batch_first=True), 1)
        self.h = nn.Sequential(nn.Dropout(0.3), nn.Linear(2 * d, k))

    def forward(self, x):
        t = self.patch(x).transpose(1, 2)
        t = self.temporal(t + self.pos[:, :t.shape[1]]).mean(dim=1)
        c = self.channel(self.ch_in(x)).mean(dim=1)
        return self.h(torch.cat([t, c], dim=1))


def build(name: str, c: int, k: int, T: int) -> nn.Module:
    return {
        "cnn1d": lambda: CNN1D(c, k),
        "lstm": lambda: RNN(c, k, "lstm"),
        "gru": lambda: RNN(c, k, "gru"),
        "bilstm": lambda: RNN(c, k, "lstm", bi=True),
        "cnn_lstm": lambda: RNN(c, k, "lstm", conv=True),
        "cnn_bilstm": lambda: RNN(c, k, "lstm", bi=True, conv=True),
        "ablstm": lambda: RNN(c, k, "lstm", bi=True, attention=True),
        "tcn": lambda: TCN(c, k),
        "resnet1d": lambda: ResNet1D(c, k),
        "that": lambda: THAT(c, k, T),
    }[name]()


MODELS = ("cnn1d", "lstm", "gru", "bilstm", "cnn_lstm", "cnn_bilstm", "ablstm", "tcn", "resnet1d", "that")


def n_params(m: nn.Module) -> int:
    return int(sum(p.numel() for p in m.parameters()))


# ------------------------------------------------------------------ training
def _macro_f1(y, p, k):
    f = []
    for c in range(k):
        tp = ((p == c) & (y == c)).sum()
        fp = ((p == c) & (y != c)).sum()
        fn = ((p != c) & (y == c)).sum()
        if (y == c).any():
            f.append(2 * tp / max(2 * tp + fp + fn, 1))
    return float(np.mean(f)) if f else 0.0


def train_one(name, Xtr, ytr, Xva, yva, k, seed, epochs=MAX_EPOCHS, patience=PATIENCE):
    """Train on (Xtr, ytr), early-stop on (Xva, yva). Returns (model, history, best_epoch)."""
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    m = build(name, Xtr.shape[1], k, Xtr.shape[2])
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-2)
    cnt = np.bincount(ytr, minlength=k).astype(np.float64)
    w = torch.tensor(len(ytr) / (k * np.maximum(cnt, 1)), dtype=torch.float32)
    lossf = nn.CrossEntropyLoss(weight=w)
    xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr.astype(np.int64))
    xv = torch.from_numpy(Xva)
    best, best_state, best_ep, wait, hist = -1.0, None, 0, 0, []
    for ep in range(epochs):
        m.train()
        perm = torch.randperm(len(xt), generator=g)
        tl = 0.0
        for i in range(0, len(xt), BATCH):
            b = perm[i:i + BATCH]
            opt.zero_grad()
            loss = lossf(m(augment(xt[b], g)), yt[b])
            loss.backward()
            opt.step()
            tl += float(loss.detach()) * len(b)
        m.eval()
        with torch.no_grad():
            lv = m(xv)
            vl = float(lossf(lv, torch.from_numpy(yva.astype(np.int64))))
            f1 = _macro_f1(yva, lv.argmax(1).numpy(), k)
        hist.append(dict(epoch=ep + 1, train_loss=tl / len(xt), val_loss=vl, val_macro_f1=f1))
        if f1 > best:
            best, best_ep, wait = f1, ep + 1, 0
            best_state = {kk: v.clone() for kk, v in m.state_dict().items()}
        else:
            wait += 1
            if wait >= patience:
                break
    m.load_state_dict(best_state)
    m.eval()
    return m, hist, best_ep


def predict_proba(m, X, batch=256):
    out = []
    with torch.no_grad():
        for i in range(0, len(X), batch):
            out.append(torch.softmax(m(torch.from_numpy(X[i:i + batch])), dim=1).numpy())
    return np.concatenate(out)
