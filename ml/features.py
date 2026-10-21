"""Hand-made features for one window (interpretable baseline). Shared by training and live use.

Input  X: [R=2, T=200, S=114] gain-normalised amplitude at 100 Hz, rssi: [R, T]
Output 1-D float32 vector, names in feature_names().
"""
from __future__ import annotations

import numpy as np

FEATURES_VERSION = "f1"
FS = 100
N_BANDS = 8
FREQ_BANDS = ((0.3, 1.0), (1.0, 3.0), (3.0, 8.0), (8.0, 20.0))


def _rx_features(x: np.ndarray, rssi: np.ndarray) -> list[float]:
    x = x.astype(np.float32)
    T, S = x.shape
    f = []
    # 1. static shape: mean amplitude in 8 sub-carrier bands (body presence/position changes it)
    bands = np.array_split(np.arange(S), N_BANDS)
    f += [float(x[:, b].mean()) for b in bands]
    # 2. how much each sub-carrier moves over the window
    sd = x.std(axis=0)
    f += [float(sd.mean()), float(np.median(sd)), float(np.percentile(sd, 90)), float(sd.max())]
    dif = np.abs(np.diff(x, axis=0)).mean(axis=0)
    f += [float(dif.mean()), float(np.percentile(dif, 90))]
    # 3. dominant movement pattern: first principal component over time
    xc = x - x.mean(axis=0, keepdims=True)
    try:
        u, s, _ = np.linalg.svd(xc, full_matrices=False)
        pc = u[:, 0] * s[0]
        evr = float(s[0] ** 2 / max((s ** 2).sum(), 1e-12))
    except np.linalg.LinAlgError:
        pc, evr = np.zeros(T), 0.0
    spec = np.abs(np.fft.rfft(pc * np.hanning(T))) ** 2
    fr = np.fft.rfftfreq(T, 1 / FS)
    tot = spec[fr >= 0.3].sum() + 1e-12
    f += [float(np.log10(tot)), evr]
    f += [float(spec[(fr >= a) & (fr < b)].sum() / tot) for a, b in FREQ_BANDS]
    # 4. received power
    f += [float(np.mean(rssi)), float(np.std(rssi))]
    return f


def feature_names(n_rx: int = 2) -> list[str]:
    base = [f"band{i}_mean" for i in range(N_BANDS)] + \
           ["sd_mean", "sd_median", "sd_p90", "sd_max", "diff_mean", "diff_p90",
            "pc1_logpower", "pc1_evr"] + [f"pc1_frac_{a:g}_{b:g}Hz" for a, b in FREQ_BANDS] + \
           ["rssi_mean", "rssi_std"]
    names = [f"rx{r + 1}_{n}" for r in range(n_rx) for n in base]
    return names + ["xrx_sd_ratio"]


def window_features(X: np.ndarray, rssi: np.ndarray) -> np.ndarray:
    f = []
    for r in range(X.shape[0]):
        f += _rx_features(X[r], rssi[r])
    sd = [float(X[r].astype(np.float32).std(axis=0).mean()) for r in range(X.shape[0])]
    f.append(sd[0] / (sd[1] + 1e-6) if len(sd) > 1 else 1.0)
    return np.asarray(f, np.float32)


def batch_features(X: np.ndarray, rssi: np.ndarray) -> np.ndarray:
    return np.stack([window_features(X[i], rssi[i]) for i in range(len(X))])


def motion_level(X: np.ndarray) -> float:
    """Single number for 'is something moving' (mean temporal std over RX and sub-carriers)."""
    return float(X.astype(np.float32).std(axis=1).mean())
