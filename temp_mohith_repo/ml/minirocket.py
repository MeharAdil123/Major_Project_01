"""Track B: MiniRocket (multivariate) re-implemented in NumPy (D-043).

Why a re-implementation: the reference implementations (aeon, sktime) need numba, and the numba
release available here requires numpy <= 2.3; installing it would downgrade numpy 2.5.4 / scipy in
the project venv after the datasets were built. This module follows the published algorithm
(Dempster, Schmidt, Webb, "MINIROCKET", KDD 2021) but is NOT the reference code; results are labelled
"MiniRocket (NumPy re-implementation)".

  kernels   84 = all choices of 3 positions (weight 2) among 9 (others weight -1), length 9
  dilations exponentially spaced, 2^linspace(0, log2((T-1)/8)), unique integers
  channels  each (kernel, dilation) sums the convolution over a random subset of channels
  biases    quantiles (low-discrepancy sequence) of the convolution output of one random training
            window per (kernel, dilation); fitted on training data only, without labels
  padding   alternates per (kernel, dilation): zero-padded 'same' output, or valid part only
  feature   PPV = proportion of positive values of (conv - bias)
"""
from __future__ import annotations

import itertools

import numpy as np

KERNELS = np.array(list(itertools.combinations(range(9), 3)), dtype=np.int64)     # (84, 3)


class MiniRocket:
    def __init__(self, num_features: int = 9996, max_dilations: int = 32, seed: int = 0):
        self.num_features, self.max_dilations, self.seed = num_features, max_dilations, seed

    def fit(self, X: np.ndarray, y=None):
        X = np.asarray(X, np.float32)
        N, C, T = X.shape
        rng = np.random.default_rng(self.seed)
        max_exp = np.log2(max((T - 1) / 8, 1))
        n_dil = min(self.max_dilations, max(1, self.num_features // 84))
        dil = np.unique(np.floor(2 ** np.linspace(0, max_exp, n_dil)).astype(int))
        per = max(1, self.num_features // (84 * len(dil)))
        self.dilations_ = dil
        self.per_ = per
        phi = (np.sqrt(5) + 1) / 2
        q = (np.arange(1, per * 84 * len(dil) + 1) * phi) % 1
        self.combos_ = []                                   # (kernel idx, dilation, padding, channels, biases)
        qi = 0
        max_c = min(C, 9)
        for di, d in enumerate(dil):
            for k in range(84):
                n_ch = int(2 ** rng.uniform(0, np.log2(max_c + 1))) if C > 1 else 1
                n_ch = max(1, min(C, n_ch))
                ch = rng.choice(C, n_ch, replace=False)
                pad = (di + k) % 2 == 0
                ex = X[rng.integers(N)][None]
                conv = self._conv(ex, k, d, ch, pad)[0]
                b = np.quantile(conv, q[qi:qi + per])
                qi += per
                self.combos_.append((k, int(d), pad, ch, b.astype(np.float32)))
        return self

    @staticmethod
    def _conv(X: np.ndarray, k: int, d: int, ch: np.ndarray, pad: bool) -> np.ndarray:
        """Summed (over channels) dilated convolution with kernel k. X [n, C, T] -> [n, T or T-8d]."""
        x = X[:, ch, :].sum(axis=1)                         # linear: sum channels first
        T = x.shape[1]
        p = 4 * d
        xp = np.pad(x, ((0, 0), (p, p)))
        idx = np.arange(9) * d
        # weights: -1 everywhere, +3 extra on the 3 chosen positions (=> 2)
        out = -sum(xp[:, i:i + T] for i in idx) + 3 * sum(xp[:, idx[j]:idx[j] + T] for j in KERNELS[k])
        return out if pad else out[:, p:T - p] if T - 2 * p > 0 else out

    def transform(self, X: np.ndarray, batch: int = 256) -> np.ndarray:
        X = np.asarray(X, np.float32)
        out = np.empty((len(X), sum(len(c[4]) for c in self.combos_)), np.float32)
        for s in range(0, len(X), batch):
            xb = X[s:s + batch]
            col = 0
            for k, d, pad, ch, b in self.combos_:
                conv = self._conv(xb, k, d, ch, pad)
                out[s:s + batch, col:col + len(b)] = (conv[:, :, None] > b[None, None, :]).mean(axis=1)
                col += len(b)
        return out


def band_channels(X: np.ndarray, n_bands: int = 8) -> np.ndarray:
    """Format 2 amplitude [N, R, T, S] -> [N, R*n_bands, T]: mean over sub-carrier bands, minus the
    window mean per channel (dynamic content only, D-024)."""
    X = np.asarray(X, np.float32)
    bands = np.array_split(np.arange(X.shape[-1]), n_bands)
    B = np.stack([X[..., b].mean(axis=-1) for b in bands], axis=2)          # [N, R, n_bands, T]
    B = B.reshape(len(X), -1, X.shape[2])
    return B - B.mean(axis=2, keepdims=True)
