"""Phase sanitisation (scripts/phase2_signal.py) on SYNTHETIC channels."""
import importlib.util
import sys

import numpy as np

from tests.conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("phase2_signal", ROOT / "scripts" / "phase2_signal.py")
p2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2)


def test_sanitise_removes_per_packet_slope_and_offset():
    rng = np.random.default_rng(0)
    k = p2.SC
    shape = 0.8 * np.sin(k / 15.0)                                # true channel phase shape (static)
    n = 200
    slope = rng.normal(0.02, 0.01, n)[:, None]                    # timing offset, varies per packet
    off = rng.uniform(-np.pi, np.pi, n)[:, None]                  # CFO / PLL phase, random per packet
    H = (1 + 0.3 * np.cos(k / 9.0)) * np.exp(1j * (shape + slope * k + off))
    raw = np.angle(H)
    san = p2.sanitise(H)
    assert p2.circ_std(raw, 0).mean() > 1.5                      # raw phase looks random
    assert p2.circ_std(san, 0).max() < 1e-6                      # sanitised phase is constant over time
    ref = shape - np.polyfit(k, shape, 1) @ np.stack([k, np.ones_like(k)])
    np.testing.assert_allclose(san[0], ref, atol=1e-6)           # equals the shape minus its own line


def test_sanitise_keeps_motion():
    k = p2.SC
    t = np.arange(400) / 200
    moving = 0.6 * np.sin(2 * np.pi * 1.0 * t)[:, None] * np.exp(-((k - 30) / 10.0) ** 2)[None, :]
    H = np.exp(1j * (moving + 0.03 * k + 1.0))
    san = p2.sanitise(H)
    assert p2.circ_std(san, 0)[np.argmin(abs(k - 30))] > 0.3
    assert p2.circ_std(san, 0)[np.argmin(abs(k + 50))] < 0.15


def test_spread_series_respects_sampling_rate():
    t = np.arange(0, 5, 0.05)                                      # 20 Hz series
    c, v = p2.spread_series(np.random.default_rng(1).normal(size=(len(t), 3)), t, kind="lin", fs=20)
    assert len(c) > 30 and np.all(np.isfinite(v))
