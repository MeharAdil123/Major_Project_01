"""Event onset/end detector (Phase 2, D-034). Used by Phase 3 to label event windows.

Replaces build_dataset.motion_energy (mean |diff| between consecutive 200 Hz packets), which is
dominated by packet-to-packet noise: its peak-to-baseline ratio was 1.23 (median) on the 141 event
takes that start still, against 5.25 for a low-passed signal (results/signal/phase2_peaks.log).

Motion signal, per receiver:
  1. gain-normalised amplitude (preprocess.normalise; removes the ~6 dB per-packet scale steps)
  2. anti-alias low-pass + decimation 200 -> 50 Hz (scipy FIR, zero phase; passband ~0-20 Hz)
  3. centre each carrier, PCA over the take; keep the first N_PC components
  4. m(t) = sqrt(sum_k var_k(t)), var_k = variance of PC k in a centred sliding window of WIN_S
Detection:
  each RX is divided by its baseline (median of m over [0.8 s, cue - 0.5 s], or a given global
  still-room baseline for takes that do not start still); combined = max over RX.
  The peak in [cue, cue + SEARCH_S] must exceed THR_HI (relative units) to count as an action. The
  interval is the run around the peak that stays above THR_LO x pre-cue level on the onset side and
  above max(THR_LO, POST_K x post-action level) on the end side (post level = median over the last
  POST_S of the take, because the end posture can move more than the start posture, e.g. sitting vs
  standing). Dips shorter than MERGE_S are closed. Other strong bursts (own peak >= THR_HI) inside the
  search window and within MERGE_BURST_S of the interval are merged into it, so a two-part action
  (bend_pick: down, pause, up) is one interval. The window smear is corrected by half a window.
  An onset before the cue (motion already going on) is clipped to the cue and flagged.
  Version history: o1 (2026-10-22) WIN_S 0.25 chosen over 0.5 on 151 event takes
  (results/signal/onset_validation.log). o2 (Gate 2 notes): the end (and burst merging) may run to
  cue + END_SEARCH_S = 6 s, capped there; detections shorter than SHORT_S = 0.6 s are flagged.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import decimate

from pipeline import preprocess as pp

Q = 4                      # 200 Hz -> 50 Hz
FS = pp.FS_IN // Q
N_PC = 3
WIN_S = 0.25
SEARCH_S = 4.0             # onset / peak search: [cue, cue + 4 s]
END_SEARCH_S = 6.0         # end may run to cue + 6 s (o2)
SHORT_S = 0.6              # detections shorter than this are flagged for inspection
PRE_FROM_S = 0.8
PRE_GUARD_S = 0.5
THR_HI = 3.0               # peak must be >= 3x the baseline motion level
THR_LO = 2.0               # interval = contiguous run >= 2x baseline around the peak
MERGE_S = 0.4
MERGE_BURST_S = 1.5
POST_S = 2.0
POST_K = 1.5
ONSET_VERSION = "o2"


def motion_signal(grid: dict, win_s: float = WIN_S, n_pc: int = N_PC) -> tuple[np.ndarray, np.ndarray]:
    """grid from preprocess.build_grid -> (t [Ld] seconds from grid start, m [R, Ld])."""
    amp = pp.normalise(grid["amp"])                                  # [R, L, S]
    out = []
    for r in range(amp.shape[0]):
        a = decimate(amp[r].astype(np.float64), Q, ftype="fir", axis=0, zero_phase=True)
        a = a - np.median(a, axis=0, keepdims=True)
        u, s, _ = np.linalg.svd(a, full_matrices=False)
        pcs = u[:, :n_pc] * s[:n_pc]
        out.append(np.sqrt(sum(_rolling_var(pcs[:, k], int(round(win_s * FS))) for k in range(pcs.shape[1]))))
    m = np.stack(out)
    return np.arange(m.shape[1]) / FS, m


def _rolling_var(x: np.ndarray, w: int) -> np.ndarray:
    """Variance in a centred window of w samples (edges use the nearest full window)."""
    w = max(2, w)
    c1 = np.cumsum(np.concatenate([[0.0], x]))
    c2 = np.cumsum(np.concatenate([[0.0], x * x]))
    mean = (c1[w:] - c1[:-w]) / w
    var = np.clip((c2[w:] - c2[:-w]) / w - mean ** 2, 0, None)
    lead = w // 2
    return np.concatenate([np.full(lead, var[0]), var, np.full(len(x) - len(var) - lead, var[-1])])


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))       # [start, stop)


def _interval(c: np.ndarray, t: np.ndarray, lo: int, hi: int, win_s: float, lo_end: float = THR_LO,
              cue_s: float | None = None, hi_end: int | None = None):
    """Peak in [lo, hi) and the run around it. Returns dict (times in s on t)."""
    if hi <= lo:
        return dict(detected=False, peak_ratio=np.nan, peak_t=np.nan, onset=np.nan, end=np.nan, early=False,
                    end_capped=False)
    pk = lo + int(np.argmax(c[lo:hi]))
    res = dict(peak_ratio=float(c[pk]), peak_t=float(t[pk]), detected=bool(c[pk] >= THR_HI), early=False,
               end_capped=False)
    hi_end = len(c) if hi_end is None else min(len(c), hi_end)
    if not res["detected"]:
        return dict(res, onset=np.nan, end=np.nan)
    gap = int(MERGE_S * FS)

    def run_edge(mask, direction):
        i = pk
        while 0 <= i + direction < len(mask):
            j = i + direction
            if mask[j]:
                i = j
                continue
            k = j                                    # look across a short dip
            while 0 <= k < len(mask) and not mask[k] and abs(k - j) < gap:
                k += direction
            if 0 <= k < len(mask) and mask[k] and abs(k - j) < gap:
                i = k
                continue
            break
        return i

    a = run_edge(c >= THR_LO, -1)
    b = run_edge(c >= lo_end, +1)
    # merge other strong bursts in the search window that lie close to the interval
    far = int(MERGE_BURST_S * FS)
    m2 = c >= max(THR_LO, lo_end)
    changed = True
    while changed:
        changed = False
        for s0, s1 in _runs(m2[lo:hi_end]):
            s0, s1 = s0 + lo, s1 + lo
            if s1 - 1 < a - far or s0 > b + far or (a <= s0 and s1 - 1 <= b):
                continue
            if c[s0:s1].max() >= THR_HI:
                a, b = min(a, s0), max(b, s1 - 1)
                changed = True
    if b >= hi_end:
        b, res["end_capped"] = hi_end - 1, True
    half = win_s / 2
    on, end = float(t[a] + half), float(t[b] - half)
    if cue_s is not None and on < cue_s:
        on, res["early"] = float(cue_s), True
    if end <= on:                                     # very short burst
        on = end = float(t[pk])
    return dict(res, onset=on, end=end)


def detect(t: np.ndarray, m: np.ndarray, cue_s: float, baseline: np.ndarray | None = None,
           win_s: float = WIN_S) -> dict:
    """Onset/end of the action after the cue.

    t, m     from motion_signal (t from grid start; pass cue_s on the same time base)
    baseline per-RX motion level for "still" ([R]); default: the take's own pre-cue median
    Returns times in seconds on t: onset, end, peak_t; peak_ratio; per-RX onsets; pre-cue level.
    """
    pre = (t >= PRE_FROM_S) & (t <= cue_s - PRE_GUARD_S)
    own = np.median(m[:, pre], axis=1) if pre.any() else np.median(m, axis=1)
    base = own if baseline is None else np.asarray(baseline, float)
    rel = m / base[:, None]
    lo = int(np.searchsorted(t, cue_s))
    hi = int(np.searchsorted(t, cue_s + SEARCH_S))
    comb = rel.max(axis=0)
    post = t >= t[-1] - POST_S
    lo_end = max(THR_LO, POST_K * float(np.median(comb[post])))
    hi_end = int(np.searchsorted(t, cue_s + END_SEARCH_S))
    out = _interval(comb, t, lo, hi, win_s, lo_end, cue_s, hi_end)
    out["end_threshold"] = lo_end
    out["pre_level"] = [float(x) for x in own / base] if baseline is not None else [1.0] * len(own)
    out["pre_raw"] = [float(x) for x in own]
    for r in range(m.shape[0]):
        x = _interval(rel[r], t, lo, hi, win_s, max(THR_LO, POST_K * float(np.median(rel[r][post]))), cue_s, hi_end)
        out[f"rx{r + 1}_onset"] = x["onset"]
        out[f"rx{r + 1}_end"] = x["end"]
        out[f"rx{r + 1}_detected"] = x["detected"]
        out[f"rx{r + 1}_peak_ratio"] = x["peak_ratio"]
    out["inside_search"] = bool(out["detected"] and not out["early"] and out["end"] <= cue_s + END_SEARCH_S)
    out["duration"] = out["end"] - out["onset"] if out["detected"] else np.nan
    out["short"] = bool(out["detected"] and out["duration"] < SHORT_S)
    return out
