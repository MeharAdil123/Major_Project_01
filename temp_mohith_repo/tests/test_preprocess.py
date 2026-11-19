"""pipeline/preprocess.py v2 on SYNTHETIC packets: alignment, gap fill, filter, windows, live = offline."""
import numpy as np
import pytest

from pipeline import preprocess as pp

S = pp.N_SC


def recs(seq, amp, phase=None, rssi=-40.0):
    seq = np.asarray(seq)
    return dict(seq=seq.astype(np.int64), amp=amp.astype(np.float32),
                phase=(np.zeros_like(amp) if phase is None else phase).astype(np.float32),
                rssi=np.full(len(seq), rssi, np.float32))


def test_alignment_by_seq_and_common_range():
    a = np.tile(np.arange(100, dtype=float)[:, None], (1, S)) + 1
    g = pp.build_grid({1: recs(np.arange(1000, 1100), a), 2: recs(np.arange(1010, 1120), np.full((110, S), 7.0))})
    assert g["seq0"] == 1010 and g["amp"].shape == (2, 90, S)
    assert g["amp"][0, 0, 0] == 11 and g["amp"][1, 0, 0] == 7          # RX1 seq 1010 = its row 10


def test_gap_fill_linear_and_marked_missing():
    seq = np.array([0, 1, 2, 6, 7])
    amp = np.tile(np.array([0, 1, 2, 6, 7], float)[:, None], (1, S)) + 10
    ph = np.tile(np.array([3.0, 3.1, -3.1, -3.0, -3.0])[:, None], (1, S))   # crosses +-pi
    g = pp.build_grid({1: recs(seq, amp, ph), 2: recs(np.arange(8), np.ones((8, S)))})
    np.testing.assert_allclose(g["amp"][0, :, 0], np.arange(8) + 10)
    assert list(g["missing"][0]) == [False] * 3 + [True] * 3 + [False] * 2
    filled = g["phase"][0, 3:6, 0]
    assert np.all(np.abs(np.angle(np.exp(1j * (filled - np.pi)))) < 0.2)  # stays near +-pi, no swing through 0
    assert pp.longest_run(g["missing"][0]) == 3


def test_sanitise_removes_line():
    k = pp.USED_SC.astype(float)
    shape = 0.5 * np.sin(k / 10)
    h = np.exp(1j * (shape[None, :] + np.array([[0.03], [-0.02]]) * k + np.array([[2.0], [-1.0]])))
    p = pp.sanitise(h)
    np.testing.assert_allclose(p[0], p[1], atol=1e-5)


def grid_with_signal(L=1600, f_hz=5.0, alias_hz=None, scale_shift=0.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(L) / 200
    base = 20 + 3 * np.sin(np.arange(S) / 6)
    pattern = np.cos(np.arange(S) / 5)[None, :]           # carrier-dependent (a common gain is normalised away)
    sig = 0.1 * np.sin(2 * np.pi * f_hz * t)[:, None] * pattern
    if alias_hz:
        sig = sig + 0.1 * np.sin(2 * np.pi * alias_hz * t)[:, None] * pattern
    amp = base[None, :] * (1 + sig)
    amp = amp * np.where(rng.random(L) < scale_shift, 0.5, 1.0)[:, None]
    ph = np.tile(0.2 * np.sin(2 * np.pi * 1.0 * t)[:, None], (1, S))
    r = {k: recs(np.arange(L), amp, ph) for k in (1, 2)}
    return pp.build_grid(r)


def spectrum_peak(x, fs):
    f = np.fft.rfftfreq(len(x), 1 / fs)
    sp = np.abs(np.fft.rfft(x - x.mean()))
    return f, sp


def test_antialias_removes_component_above_new_nyquist():
    g = grid_with_signal(alias_hz=70.0)                 # 70 Hz would fold to 30 Hz at 100 Hz sampling
    w = pp.window(g, 300, 4.0)
    x = w["X"][0, :, 0]
    f, sp = spectrum_peak(x, pp.FS)
    a5 = sp[np.argmin(abs(f - 5))]
    a30 = sp[np.argmin(abs(f - 30))]
    assert a30 < 0.01 * a5


def test_scale_shifts_removed_by_normalisation():
    g = grid_with_signal(scale_shift=0.3)
    w = pp.window(g, 300, 3.0)
    clean = pp.window(grid_with_signal(), 300, 3.0)
    np.testing.assert_allclose(w["X"], clean["X"], atol=1e-4)


@pytest.mark.parametrize("win_s", [2.0, 3.0, 4.0])
def test_window_shapes_and_live_equals_offline(win_s):
    g = grid_with_signal()
    start = 500
    off = pp.window(g, start, win_s)
    T = int(win_s * pp.FS)
    assert off["X"].shape == (2, T, S) and off["P"].shape == (2, T, S) and off["rssi"].shape == (2, T)
    # live: the buffer holds only this window plus the margins
    span = int(win_s * 200)
    lo, hi = start - pp.MARGIN_PKTS, start + span + pp.MARGIN_PKTS
    sub = {k: (v[:, lo:hi] if k != "seq0" else v + lo) for k, v in g.items()}
    live = pp.window(sub, pp.MARGIN_PKTS, win_s)
    np.testing.assert_allclose(live["X"], off["X"], atol=1e-6)
    np.testing.assert_allclose(live["P"], off["P"], atol=1e-6)


def test_quality_gate_parameters():
    g = grid_with_signal()
    g["missing"][1, 400:400 + 90] = True                       # 15 % of a 3 s window, longest gap 90
    w = pp.cut_windows(g, [300], 3.0, max_miss=0.20, max_gap=100)
    assert w["ok"][0]
    assert not pp.cut_windows(g, [300], 3.0, max_miss=0.10, max_gap=100)["ok"][0]
    assert not pp.cut_windows(g, [300], 3.0, max_miss=0.20, max_gap=20)["ok"][0]
