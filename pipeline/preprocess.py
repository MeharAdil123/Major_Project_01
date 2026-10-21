"""Shared preprocessing: CSI records -> aligned amplitude grid -> fixed windows.

FROZEN INTERFACE (v1). Used by BOTH the offline dataset builder (pipeline/build_dataset.py)
and the live engine (app/engine.py), so training and the live demo see identical inputs.
You may improve the internals; if the output changes, bump PREPROC_VERSION and tell the team
(models trained on another version are rejected by ml/predict.py).

Steps
  1. keep our TX's packets (SEQ_VALID, no radio mismatch)
  2. HT-LTF amplitude on the 114 used 802.11n HT40 sub-carriers (-58..-2, +2..+58)
  3. put RX1 and RX2 on one grid indexed by TX sequence number (both receivers hear the
     same broadcast, so seq aligns them exactly); missing packets -> linear interpolation
  4. gain normalisation: divide each packet by its mean amplitude (removes AGC steps)
  5. 200 Hz -> 100 Hz by averaging packet pairs
  6. windows of 2 s (200 samples)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402

PREPROC_VERSION = "v1"
RX_IDS = (1, 2)                       # array order everywhere: [RX1, RX2]
FS_IN = 200                           # TX packet rate
DECIM = 2
FS = FS_IN // DECIM                   # 100 Hz after decimation
WIN_S = 2.0
WIN = int(WIN_S * FS)                 # 200 samples
USED_SC = cw.HT40_EXPECTED_USED       # 114 sub-carriers (update after real-data check)
USED_COL = USED_SC + 64               # columns in the -64..63 HT-LTF array
N_SC = len(USED_SC)
MAX_MISS_FRAC = 0.10                  # window rejected if > 10 % packets missing on any RX
MAX_GAP_PKTS = 20                     # ... or any gap longer than 20 packets (100 ms)


def records_from_recording(rec: "cw.Recording"):
    """Recording -> dict(seq, amp[n,114], rssi[n]) for our TX's packets, longest TX segment."""
    h = rec.hdr
    ok = ((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)
    h, raw = h[ok], rec.csi_raw[ok]
    if len(h):
        segs = cw.tx_segments(h["seq"])
        s = max(segs, key=lambda x: x.stop - x.start)
        h, raw = h[s], raw[s]
    return records_from_arrays(h["seq"], raw, h["rssi"], h)


def records_from_arrays(seq, csi_raw, rssi, hdr=None):
    _, ht = cw.to_complex(np.asarray(csi_raw).reshape(-1, cw.CSI_LEN_HT40), hdr)
    amp = np.abs(ht[:, USED_COL]).astype(np.float32)
    seq = np.asarray(seq, np.int64)
    order = np.argsort(seq, kind="stable")
    seq, amp, rssi = seq[order], amp[order], np.asarray(rssi, np.float32)[order]
    keep = np.concatenate([[True], np.diff(seq) > 0])       # drop duplicate seq
    return dict(seq=seq[keep], amp=amp[keep], rssi=rssi[keep])


def build_grid(per_rx: dict, seq_lo: int | None = None, seq_hi: int | None = None):
    """per_rx: {rx_id: records dict}. Returns dict(seq0, amp[R,L,114], rssi[R,L], missing[R,L]).

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
    amp = np.zeros((len(RX_IDS), L, N_SC), np.float32)
    rssi = np.zeros((len(RX_IDS), L), np.float32)
    missing = np.ones((len(RX_IDS), L), bool)
    for k, r in enumerate(RX_IDS):
        d = per_rx.get(r)
        if d is None or not len(d["seq"]):
            continue
        m = (d["seq"] >= lo) & (d["seq"] <= hi)
        idx = (d["seq"][m] - lo).astype(int)
        a = d["amp"][m]
        # drop packets with NaN (first-word-invalid) values: treat as missing
        good = np.all(np.isfinite(a), axis=1)
        idx, a, rs = idx[good], a[good], d["rssi"][m][good]
        if len(idx) == 0:
            continue
        missing[k, idx] = False
        x = np.arange(L)
        for j in range(N_SC):                                # linear gap fill
            amp[k, :, j] = np.interp(x, idx, a[:, j])
        rssi[k] = np.interp(x, idx, rs)
    return dict(seq0=lo, amp=amp, rssi=rssi, missing=missing)


def normalise(amp: np.ndarray) -> np.ndarray:
    """Divide every packet by its mean amplitude over sub-carriers (AGC/gain removal)."""
    m = amp.mean(axis=-1, keepdims=True)
    return amp / np.maximum(m, 1e-6)


def decimate(x: np.ndarray, axis: int) -> np.ndarray:
    n = (x.shape[axis] // DECIM) * DECIM
    x = np.take(x, np.arange(n), axis=axis)
    shp = list(x.shape)
    shp[axis:axis + 1] = [n // DECIM, DECIM]
    return x.reshape(shp).mean(axis=axis + 1)


def longest_run(mask_row: np.ndarray) -> int:
    if not mask_row.any():
        return 0
    d = np.diff(np.concatenate([[0], mask_row.astype(np.int8), [0]]))
    return int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())


def cut_windows(grid: dict, starts_pkt) -> dict:
    """Windows starting at the given grid packet offsets (200 Hz units).

    Returns X[N,R,200,114] (gain-normalised amplitude, float32), rssi[N,R,200],
    miss_frac[N,R], max_gap[N,R], ok[N] (quality gate), start_pkt[N].
    """
    span = WIN * DECIM
    L = grid["amp"].shape[1]
    starts = [int(s) for s in starts_pkt if 0 <= s and s + span <= L]
    X, R, MF, MG = [], [], [], []
    for s in starts:
        a = normalise(grid["amp"][:, s:s + span])
        X.append(decimate(a, axis=1))
        R.append(decimate(grid["rssi"][:, s:s + span], axis=1))
        mi = grid["missing"][:, s:s + span]
        MF.append(mi.mean(axis=1))
        MG.append([longest_run(row) for row in mi])
    if not starts:
        z = np.zeros((0, len(RX_IDS)))
        return dict(X=np.zeros((0, len(RX_IDS), WIN, N_SC), np.float32), rssi=np.zeros((0, len(RX_IDS), WIN)),
                    miss_frac=z, max_gap=z, ok=np.zeros(0, bool), start_pkt=np.zeros(0, int))
    MF, MG = np.array(MF), np.array(MG)
    ok = (MF <= MAX_MISS_FRAC).all(axis=1) & (MG <= MAX_GAP_PKTS).all(axis=1)
    return dict(X=np.stack(X).astype(np.float32), rssi=np.stack(R).astype(np.float32),
                miss_frac=MF, max_gap=MG, ok=ok, start_pkt=np.array(starts))
