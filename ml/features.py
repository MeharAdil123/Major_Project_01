"""Hand-made features for one window, version f2 (Phase 3). Shared by training and live use.

Input  X [R=2, T, S=114] gain-normalised amplitude at 100 Hz, P [R, T, S] sanitised phase (rad),
       rssi [R, T]. T depends on the window length (200 / 300 / 400 for 2 / 3 / 4 s).
Output 1-D float32 vector; names in feature_names(), group of each name in feature_groups().

Groups (D-024): "static" features describe the channel *shape* and level, which depends on where the
person is (position confound); "dynamic" features describe *change over time*. Subgroups are used
for the remove-one-group ablation. Documentation: docs/FEATURES.md.
Never used as features: missing-packet share, loss, low-scale packet share (all depend on position).
"""
from __future__ import annotations

import numpy as np

FEATURES_VERSION = "f2"
FS = 100
N_BANDS = 8
FREQ_BANDS = ((0.3, 1.0), (1.0, 3.0), (3.0, 8.0), (8.0, 20.0))
MOTION_WIN = 25                         # 0.25 s at 100 Hz, as in pipeline/onset.py
N_PC = 3


# ---------------------------------------------------------------- helpers
def _rolling_std(x: np.ndarray, w: int) -> np.ndarray:
    c1 = np.cumsum(np.concatenate([[0.0], x]))
    c2 = np.cumsum(np.concatenate([[0.0], x * x]))
    m = (c1[w:] - c1[:-w]) / w
    return np.sqrt(np.clip((c2[w:] - c2[:-w]) / w - m * m, 0, None))


def _pca(x: np.ndarray):
    xc = x - x.mean(axis=0, keepdims=True)
    try:
        u, s, vt = np.linalg.svd(xc, full_matrices=False)
    except np.linalg.LinAlgError:
        T, S = x.shape
        return np.zeros((T, N_PC)), np.zeros(N_PC), np.zeros((N_PC, S))
    return u[:, :N_PC] * s[:N_PC], s, vt[:N_PC]


def _wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


# ---------------------------------------------------------------- groups (one function each)
def static_shape(x: np.ndarray) -> list[float]:
    """Mean gain-normalised amplitude in 8 sub-carrier bands: the channel shape (where the body is)."""
    return [float(x[:, b].mean()) for b in np.array_split(np.arange(x.shape[1]), N_BANDS)]


def static_rssi(rssi: np.ndarray) -> list[float]:
    """Received power level (body shadowing changes it; position-dependent)."""
    return [float(np.mean(rssi))]


def static_pca(x: np.ndarray) -> list[float]:
    """PCA shape: explained-variance ratios of PC1..3 and where PC1's loading sits across the band."""
    _, s, vt = _pca(x)
    tot = float((s ** 2).sum()) + 1e-12
    evr = [float(v ** 2 / tot) for v in s[:N_PC]] + [0.0] * (N_PC - len(s[:N_PC]))
    load = vt[0] ** 2 if len(vt) else np.zeros(x.shape[1])
    share = [float(load[b].sum() / (load.sum() + 1e-12)) for b in np.array_split(np.arange(x.shape[1]), 4)]
    return evr + share


def dyn_temporal(x: np.ndarray) -> list[float]:
    """How much each sub-carrier moves: temporal std (relative to its mean) and mean |change per 10 ms|."""
    sd = x.std(axis=0) / np.maximum(x.mean(axis=0), 1e-6)
    dif = np.abs(np.diff(x, axis=0)).mean(axis=0)
    return [float(sd.mean()), float(np.median(sd)), float(np.percentile(sd, 90)), float(sd.max()),
            float(dif.mean()), float(np.percentile(dif, 90))]


def dyn_motion(x: np.ndarray) -> list[float]:
    """Motion signal of pipeline/onset.py inside the window: 0.25 s std of PC1..3 (mean, p90, max, where)."""
    pcs, _, _ = _pca(x)
    m = np.sqrt(sum(_rolling_std(pcs[:, k], MOTION_WIN) ** 2 for k in range(pcs.shape[1])))
    return [float(m.mean()), float(np.percentile(m, 90)), float(m.max()), float(np.argmax(m) / max(len(m) - 1, 1))]


def dyn_bandpower(x: np.ndarray) -> list[float]:
    """Doppler-like content: PC1 power above 0.3 Hz, its share in 0.3-1/1-3/3-8/8-20 Hz, dominant frequency."""
    pcs, _, _ = _pca(x)
    pc = pcs[:, 0]
    T = len(pc)
    spec = np.abs(np.fft.rfft(pc * np.hanning(T))) ** 2
    fr = np.fft.rfftfreq(T, 1 / FS)
    sel = fr >= 0.3
    tot = spec[sel].sum() + 1e-12
    out = [float(np.log10(tot))] + [float(spec[(fr >= a) & (fr < b)].sum() / tot) for a, b in FREQ_BANDS]
    out.append(float(fr[sel][np.argmax(spec[sel])]) if sel.any() else 0.0)
    return out


def dyn_corr(x: np.ndarray) -> list[float]:
    """Sub-carrier correlation of the fluctuations: high when one movement drives the whole band."""
    xc = x - x.mean(axis=0, keepdims=True)
    sd = xc.std(axis=0)
    ok = sd > 1e-9
    if ok.sum() < 2:
        return [0.0]
    c = np.corrcoef(xc[:, ok].T)
    n = c.shape[0]
    return [float((np.abs(c).sum() - n) / (n * (n - 1)))]


def dyn_rssi(rssi: np.ndarray) -> list[float]:
    """RSSI variation over the window (movement), not its level."""
    return [float(np.std(rssi))]


def dyn_phase(x: np.ndarray, p: np.ndarray) -> list[float]:
    """Sanitised-phase dynamics, weighted by carrier amplitude so faded carriers (2pi slips) count little.

    circular variance over time per carrier; mean |phase change per 10 ms|; PC1 log-power of the
    weighted phase deviation.
    """
    w = x.mean(axis=0) ** 2
    w = w / (w.sum() + 1e-12)
    z = np.exp(1j * p)
    r = np.abs(z.mean(axis=0))
    cvar = 1 - r                                                   # circular variance in [0, 1]
    d = np.abs(_wrap(np.diff(p, axis=0))).mean(axis=0)
    strong = w >= np.median(w)
    dev = _wrap(p - np.angle(z.mean(axis=0))[None, :]) * np.sqrt(w)[None, :]
    pcs, _, _ = _pca(dev)
    return [float((w * cvar).sum()), float(np.percentile(cvar[strong], 90)),
            float((w * d).sum()), float(np.percentile(d[strong], 90)),
            float(np.log10((pcs[:, 0] ** 2).sum() + 1e-12))]


# ---------------------------------------------------------------- names / groups
_PER_RX = [
    ("static", "shape", [f"band{i}_mean" for i in range(N_BANDS)]),
    ("static", "rssi_level", ["rssi_mean"]),
    ("static", "pca_shape", [f"pca_evr{i + 1}" for i in range(N_PC)] + [f"pc1_load_q{i}" for i in range(4)]),
    ("dynamic", "temporal", ["sd_mean", "sd_median", "sd_p90", "sd_max", "diff_mean", "diff_p90"]),
    ("dynamic", "motion", ["motion_mean", "motion_p90", "motion_max", "motion_argmax"]),
    ("dynamic", "bandpower", ["pc1_logpower"] + [f"pc1_frac_{a:g}_{b:g}Hz" for a, b in FREQ_BANDS] + ["pc1_peak_hz"]),
    ("dynamic", "corr", ["sc_corr"]),
    ("dynamic", "rssi_var", ["rssi_std"]),
    ("dynamic", "phase", ["ph_cvar_w", "ph_cvar_p90", "dph_w", "dph_p90", "ph_pc1_logpower"]),
]
_CROSS = [
    ("static", "rssi_level", ["xrx_rssi_diff"]),
    ("dynamic", "cross", ["xrx_sd_logratio", "xrx_motion_logratio", "xrx_phase_logratio", "xrx_motion_corr"]),
]


def feature_names(n_rx: int = 2) -> list[str]:
    per = [n for _, _, names in _PER_RX for n in names]
    return [f"rx{r + 1}_{n}" for r in range(n_rx) for n in per] + [n for _, _, names in _CROSS for n in names]


def feature_groups(n_rx: int = 2) -> dict[str, tuple[str, str]]:
    """name -> (group "static"|"dynamic", subgroup)."""
    out = {}
    for r in range(n_rx):
        for g, sg, names in _PER_RX:
            for n in names:
                out[f"rx{r + 1}_{n}"] = (g, sg)
    for g, sg, names in _CROSS:
        for n in names:
            out[n] = (g, sg)
    return out


def _rx_features(x, p, rssi):
    return (static_shape(x) + static_rssi(rssi) + static_pca(x) + dyn_temporal(x) + dyn_motion(x)
            + dyn_bandpower(x) + dyn_corr(x) + dyn_rssi(rssi) + dyn_phase(x, p))


def window_features(X: np.ndarray, P: np.ndarray, rssi: np.ndarray) -> np.ndarray:
    X = np.asarray(X, np.float64)
    P = np.asarray(P, np.float64)
    rssi = np.asarray(rssi, np.float64)
    f = []
    for r in range(X.shape[0]):
        f += _rx_features(X[r], P[r], rssi[r])
    per = len(f) // X.shape[0]
    names = [n for _, _, ns in _PER_RX for n in ns]
    i_sd, i_mot, i_ph = names.index("sd_mean"), names.index("motion_mean"), names.index("ph_cvar_w")
    a, b = f[:per], f[per:2 * per]
    m1 = dyn_motion_series(X[0])
    m2 = dyn_motion_series(X[1])
    corr = float(np.corrcoef(m1, m2)[0, 1]) if m1.std() > 0 and m2.std() > 0 else 0.0
    lr = lambda u, v: float(np.log((u + 1e-9) / (v + 1e-9)))                           # noqa: E731
    f += [float(np.mean(rssi[0]) - np.mean(rssi[1])),
          lr(a[i_sd], b[i_sd]), lr(a[i_mot], b[i_mot]), lr(a[i_ph], b[i_ph]), corr]
    return np.asarray(f, np.float32)


def dyn_motion_series(x: np.ndarray) -> np.ndarray:
    pcs, _, _ = _pca(x)
    return np.sqrt(sum(_rolling_std(pcs[:, k], MOTION_WIN) ** 2 for k in range(pcs.shape[1])))


def batch_features(X: np.ndarray, P: np.ndarray, rssi: np.ndarray) -> np.ndarray:
    return np.stack([window_features(X[i], P[i], rssi[i]) for i in range(len(X))])


def motion_level(X: np.ndarray) -> float:
    """Single number for 'is something moving' (mean temporal std over RX and sub-carriers)."""
    return float(np.asarray(X, np.float32).std(axis=1).mean())
