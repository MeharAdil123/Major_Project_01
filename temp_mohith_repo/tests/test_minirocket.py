"""MiniRocket re-implementation: shapes, determinism, separability on a SYNTHETIC toy problem."""
import numpy as np

from ml.minirocket import KERNELS, MiniRocket, band_channels


def toy(n=120, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(150) / 50
    y = rng.integers(0, 2, n)
    X = 0.5 * rng.standard_normal((n, 4, 150))
    X[y == 1, 1] += np.sin(2 * np.pi * 3 * t)                  # class 1: a 3 Hz burst on channel 1
    return X.astype(np.float32), y


def test_kernels_and_shapes():
    assert KERNELS.shape == (84, 3)
    X, _ = toy()
    m = MiniRocket(num_features=840, seed=1).fit(X)
    F = m.transform(X)
    assert F.shape[0] == len(X) and F.shape[1] == sum(len(c[4]) for c in m.combos_)
    assert F.min() >= 0 and F.max() <= 1
    np.testing.assert_array_equal(F, MiniRocket(num_features=840, seed=1).fit(X).transform(X))


def test_separates_toy_classes():
    from sklearn.linear_model import RidgeClassifier
    Xtr, ytr = toy(seed=0)
    Xte, yte = toy(seed=1)
    m = MiniRocket(num_features=840).fit(Xtr)
    clf = RidgeClassifier(alpha=10).fit(m.transform(Xtr), ytr)
    assert (clf.predict(m.transform(Xte)) == yte).mean() > 0.9


def test_band_channels_removes_window_mean():
    X = np.random.default_rng(0).random((3, 2, 50, 114)).astype(np.float32) + 5
    B = band_channels(X)
    assert B.shape == (3, 16, 50) and np.allclose(B.mean(axis=2), 0, atol=1e-5)
