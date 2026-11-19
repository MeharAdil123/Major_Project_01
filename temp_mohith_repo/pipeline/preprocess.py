"""Shared preprocessing: CSI records -> aligned grid -> fixed windows (amplitude + sanitised phase).

FROZEN INTERFACE (v2). Used by BOTH the offline dataset builder (pipeline/build_dataset.py) and the
live engine (app/engine.py), so training and the live demo see identical inputs. If the output
changes, bump PREPROC_VERSION and log it in docs/decisions/DECISIONS.md (models trained on another
version are refused by ml/predict.py).

Steps
  1. keep our TX's packets (SEQ_VALID, no radio mismatch), longest TX boot segment
  2. HT-LTF on the 114 used 802.11n HT40 sub-carriers (-58..-2, +2..+58; verified on real data, D-037)
  3. per packet: amplitude |H|, and sanitised phase (unwrap across carriers, remove the least-squares
     line; D-036). Raw phase is never kept.
  4. RX1 and RX2 on one grid indexed by TX sequence number; missing packets are marked and filled
     by linear interpolation (amplitude; phase through its unit phasor)
  5. per window, from the raw grid plus MARGIN_PKTS on each side:
       gain normalisation: each packet divided by its mean amplitude (removes the ~6 dB per-packet
       CSI scale shifts, D-035); anti-alias FIR low-pass + decimation 200 -> 100 Hz (zero phase,
       scipy.signal.decimate); the margin is trimmed so filter edges never reach the window
  6. quality gate per window: missing share <= max_miss and longest gap <= max_gap on every RX
     (defaults 20 % and 20 packets = 100 ms, D-039)
Version history: v1 (2026-10-21) 2 s windows, pair-average decimation, amplitude only.
                 v2 (2026-10-22) anti-alias decimation, sanitised phase channel, window length and
                 gate as parameters, margins (D-039).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import decimate as _decimate

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402

PREPROC_VERSION = "v2"
RX_IDS = (1, 2)                       # array order everywhere: [RX1, RX2]
FS_IN = 200                           # TX packet rate
DECIM = 2
FS = FS_IN // DECIM                   # 100 Hz after decimation
WIN_S = 3.0                           # default window length (2 / 3 / 4 s datasets exist)
WIN = int(WIN_S * FS)                 # samples per window at FS (default)
USED_SC = cw.HT40_EXPECTED_USED       # 114 sub-carriers, verified on 396/404 receiver-takes (D-037)
USED_COL = USED_SC + 64               # columns in the -64..63 HT-LTF array
N_SC = len(USED_SC)
MAX_MISS_FRAC = 0.20                  # default gate: window rejected if > 20 % packets missing on any RX
MAX_GAP_PKTS = 20                     # ... or any gap longer than 20 packets (100 ms)
MARGIN_PKTS = 50                      # 0.25 s of raw packets on each side of a window for the filter

_SC = USED_SC.astype(np.float64)
_A = np.stack([_SC, np.ones_like(_SC)], axis=1)
_PINV = np.linalg.pinv(_A)            # (2, 114): least-squares line through the phase


def sanitise(h: np.ndarray) -> np.ndarray:
    """Complex HT-LTF (N, 114) -> sanitised phase (N, 114), float32."""
    ph = np.unwrap(np.angle(h), axis=1)
    coef = ph @ _PINV.T                                   # (N, 2): slope, offset per packet
    return (ph - coef @ _A.T).astype(np.float32)


def records_from_recording(rec: "cw.Recording"):
    """Recording -> dict(seq, amp[n,114], phase[n,114], rssi[n]) for our TX, longest TX segment."""
    h = rec.hdr
    ok = ((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)
    h, raw = h[ok], rec.csi_raw[ok]
    if len(h):
        segs = cw.tx_segments(h["seq"])
        s = max(segs, key=lambda x: x.stop - x.start)
        h, raw = h[s], raw[s]
    return records_from_arrays(h["seq"], raw, h["rssi"], h)


def records_from_arrays(seq, csi_raw, rssi, hdr=None):
    """Packets -> dict(seq, amp, phase, rssi), sorted by seq, duplicates dropped.

    Packets with an invalid value (FIRST_WORD_INVALID -> NaN) on a used carrier are dropped
    here, offline and live alike (they then count as missing).
    """
    _, ht = cw.to_complex(np.asarray(csi_raw).reshape(-1, cw.CSI_LEN_HT40), hdr)
    hu = ht[:, USED_COL]
    good = np.all(np.isfinite(hu), axis=1)
    seq = np.asarray(seq, np.int64)[good]
    hu = hu[good]
    rssi = np.asarray(rssi, np.float32)[good]
    order = np.argsort(seq, kind="stable")
    seq, hu, rssi = seq[order], hu[order], rssi[order]
    keep = np.concatenate([[True], np.diff(seq) > 0]) if len(seq) else np.zeros(0, bool)
    seq, hu, rssi = seq[keep], hu[keep], rssi[keep]
    return dict(seq=seq, amp=np.abs(hu).astype(np.float32), phase=sanitise(hu) if len(hu) else
                np.zeros((0, N_SC), np.float32), rssi=rssi)


def build_grid(per_rx: dict, seq_lo: int | None = None, seq_hi: int | None = None):
    """per_rx: {rx_id: records}. Returns dict(seq0, amp[R,L,S], phase[R,L,S], rssi[R,L], missing[R,L]).

    The grid covers the seq range all receivers have in common (or seq_lo..seq_hi).
    A receiver with no records gives all-missing rows.
    """
    have = [per_rx[r] for r in RX_IDS if r in per_rx and len(per_rx[r]["seq"])]
    if not have:
        raise ValueError("no records")
    lo = max(int(d["seq"][0]) for d in have) if seq_lo is None else int(seq_lo)
    hi = min(int(d["seq"][-1]) for d in have) if seq_hi is None else int(seq_hi)
    if hi <= lo:
        raise ValueError("receivers do not overlap in time")
    L = hi - lo + 1
    R = len(RX_IDS)
    amp = np.zeros((R, L, N_SC), np.float32)
    phase = np.zeros((R, L, N_SC), np.float32)
    rssi = np.zeros((R, L), np.float32)
    missing = np.ones((R, L), bool)
    x = np.arange(L)
    for k, r in enumerate(RX_IDS):
        d = per_rx.get(r)
        if d is None or not len(d["seq"]):
            continue
        m = (d["seq"] >= lo) & (d["seq"] <= hi)
        idx = (d["seq"][m] - lo).astype(int)
        if len(idx) == 0:
            continue
        missing[k, idx] = False
        a = d["amp"][m]
        p = d["phase"][m] if "phase" in d else np.zeros_like(a)      # amplitude-only callers
        c, s = np.cos(p), np.sin(p)
        for j in range(N_SC):                                # linear gap fill
            amp[k, :, j] = np.interp(x, idx, a[:, j])
            phase[k, :, j] = np.arctan2(np.interp(x, idx, s[:, j]), np.interp(x, idx, c[:, j]))
        rssi[k] = np.interp(x, idx, d["rssi"][m])
    return dict(seq0=lo, amp=amp, phase=phase, rssi=rssi, missing=missing)


def normalise(amp: np.ndarray) -> np.ndarray:
    """Divide every packet by its mean amplitude over sub-carriers (gain / scale-shift removal)."""
    m = amp.mean(axis=-1, keepdims=True)
    return amp / np.maximum(m, 1e-6)


def lowpass_decimate(x: np.ndarray, axis: int) -> np.ndarray:
    """Anti-alias FIR low-pass (zero phase) + keep every DECIM-th sample."""
    return _decimate(np.asarray(x, np.float64), DECIM, ftype="fir", axis=axis, zero_phase=True)


def longest_run(mask_row: np.ndarray) -> int:
    if not mask_row.any():
        return 0
    d = np.diff(np.concatenate([[0], mask_row.astype(np.int8), [0]]))
    return int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())


def window(grid: dict, start_pkt: int, win_s: float = WIN_S) -> dict:
    """One window starting at grid packet start_pkt (200 Hz units), win_s long.

    Uses MARGIN_PKTS raw packets before and after when available (edge-padded otherwise), so the
    filter output inside the window does not depend on where the take or the live buffer ends.
    Returns X [R,T,S] (gain-normalised amplitude), P [R,T,S] (sanitised phase, rad), rssi [R,T],
    miss_frac [R], max_gap [R]; T = win_s * FS.
    """
    span = int(round(win_s * FS_IN))
    L = grid["amp"].shape[1]
    a0, a1 = start_pkt - MARGIN_PKTS, start_pkt + span + MARGIN_PKTS
    idx = np.clip(np.arange(a0, a1), 0, L - 1)
    amp = normalise(grid["amp"][:, idx])
    ph = grid["phase"][:, idx]
    X = lowpass_decimate(amp, axis=1)
    c = lowpass_decimate(np.cos(ph), axis=1)
    s = lowpass_decimate(np.sin(ph), axis=1)
    m = MARGIN_PKTS // DECIM
    T = span // DECIM
    X = X[:, m:m + T]
    P = np.arctan2(s[:, m:m + T], c[:, m:m + T])
    rs = grid["rssi"][:, start_pkt:start_pkt + span]
    rssi = rs.reshape(rs.shape[0], T, DECIM).mean(axis=2)
    mi = grid["missing"][:, start_pkt:start_pkt + span]
    return dict(X=X.astype(np.float32), P=P.astype(np.float32), rssi=rssi.astype(np.float32),
                miss_frac=mi.mean(axis=1), max_gap=np.array([longest_run(r) for r in mi]))


def cut_windows(grid: dict, starts_pkt, win_s: float = WIN_S, max_miss: float = MAX_MISS_FRAC,
                max_gap: int = MAX_GAP_PKTS) -> dict:
    """Windows starting at the given grid packet offsets. Windows not fully inside the grid are skipped.

    Returns X[N,R,T,S], P[N,R,T,S], rssi[N,R,T], miss_frac[N,R], max_gap[N,R], ok[N], start_pkt[N].
    """
    span = int(round(win_s * FS_IN))
    L = grid["amp"].shape[1]
    starts = [int(s) for s in starts_pkt if 0 <= s and s + span <= L]
    T = span // DECIM
    R = len(RX_IDS)
    if not starts:
        z = np.zeros((0, R))
        return dict(X=np.zeros((0, R, T, N_SC), np.float32), P=np.zeros((0, R, T, N_SC), np.float32),
                    rssi=np.zeros((0, R, T), np.float32), miss_frac=z, max_gap=z, ok=np.zeros(0, bool),
                    start_pkt=np.zeros(0, int))
    W = [window(grid, s, win_s) for s in starts]
    MF = np.stack([w["miss_frac"] for w in W])
    MG = np.stack([w["max_gap"] for w in W])
    ok = (MF <= max_miss).all(axis=1) & (MG <= max_gap).all(axis=1)
    return dict(X=np.stack([w["X"] for w in W]), P=np.stack([w["P"] for w in W]),
                rssi=np.stack([w["rssi"] for w in W]), miss_frac=MF, max_gap=MG, ok=ok,
                start_pkt=np.array(starts))
