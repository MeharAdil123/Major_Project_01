#!/usr/bin/env python3
"""Phase 2 signal inspection over every take in data/raw (read-only).

    python3 scripts/phase2_signal.py [--limit N] > results/signal/phase2_signal.log

Per take and receiver it measures:
  carriers   HT-LTF empty sub-carriers and L-LTF empty bins / placement (host/csi_inspect.py logic)
  scaling    per-packet CSI power (dB, 114 used carriers): level clusters, size of the step between
             them, whether a step scales all carriers equally, and the slope against RSSI
  phase      raw phase vs sanitised phase (unwrap across carriers, remove per-packet linear fit);
             temporal spread (circular std) and motion contrast
  contrast   event takes: spread in [cue+0.3, cue+3.3] s / spread in [0.3, 2.7] s, for gain-normalised
             amplitude, sanitised phase and its time difference
Outputs: results/signal/phase2_takes.csv, results/signal/phase2_summary.json (+ this log).
Nothing is written under data/.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import csi_inspect as ci  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

cw = ci.cw
USED_COL = pp.USED_COL                          # columns of the 114 used carriers in the -64..63 array
SC = pp.USED_SC.astype(float)
OUT = ROOT / "results" / "signal"
LOW_STEP_DB = 3.0                               # packets more than this below the main level = "low level"


def load_rx(folder: Path, rx: int):
    rec = cw.load(folder / f"RX{rx}.bin")
    p = ci.prepare(rec)                         # ours + longest TX segment + complex
    return p


def sanitise(ht_used: np.ndarray) -> np.ndarray:
    """Raw HT-LTF (N,114) complex -> sanitised phase (N,114): unwrap across carriers, minus LS line."""
    ph = np.unwrap(np.angle(ht_used), axis=1)
    A = np.stack([SC, np.ones_like(SC)], axis=1)
    coef, *_ = np.linalg.lstsq(A, ph.T, rcond=None)          # (2, N)
    return ph - (A @ coef).T


GAP = int(np.flatnonzero(np.diff(SC) > 1)[0])        # pair index across the DC gap (-2 -> +2)


def sanitise_robust(hu: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sanitised phase without unwrapping across carriers (robust near amplitude nulls).

    1. coarse slope = angle(sum_k H[k+1] conj(H[k])) over neighbouring carriers (not across the DC
       gap); offset = angle(sum_k H[k] e^{-j slope k}); de-rotate -> wrapped residual z, near 0.
    2. refine: least-squares line a k + b through z, weighted by |H|^2 (faded carriers barely count).
    Returns (residual phase in (-pi, pi], total slope per packet).
    """
    prod = hu[:, 1:] * np.conj(hu[:, :-1])
    prod[:, GAP] = 0
    s0 = np.angle(prod.sum(axis=1))
    rot = hu * np.exp(-1j * s0[:, None] * SC[None, :])
    rot *= np.exp(-1j * np.angle(rot.sum(axis=1)))[:, None]
    z = np.angle(rot)
    w = np.abs(hu) ** 2
    sw, swk, swkk = w.sum(1), (w * SC).sum(1), (w * SC ** 2).sum(1)
    swz, swkz = (w * z).sum(1), (w * SC * z).sum(1)
    den = sw * swkk - swk ** 2
    a = (sw * swkz - swk * swz) / den
    b = (swkk * swz - swk * swkz) / den
    return wrap(z - a[:, None] * SC[None, :] - b[:, None]), s0 + a


def sanitise_slope(ht_used):
    ph = np.unwrap(np.angle(ht_used), axis=1)
    A = np.stack([SC, np.ones_like(SC)], axis=1)
    return np.linalg.lstsq(A, ph.T, rcond=None)[0][0]


def slope_jump_frac(slope):
    """Share of packets whose slope is > 0.01 rad/carrier away from the 21-packet running median."""
    from scipy.ndimage import median_filter
    return float(np.mean(np.abs(slope - median_filter(slope, 21, mode="nearest")) > 0.01))


def spread_series(x, t, win_s=1.0, kind="lin", fs=200):
    """Mean over carriers of the temporal spread in sliding windows (hop 0.1 s). Returns (centres, values)."""
    c, v = [], []
    for t0 in np.arange(t[0], t[-1] - win_s, 0.1):
        m = (t >= t0) & (t < t0 + win_s)
        if m.sum() < 0.5 * win_s * fs:
            continue
        seg = x[m]
        if kind == "circ":
            seg = seg - np.angle(np.mean(np.exp(1j * seg), axis=0))
            v.append(float(circ_std(seg, 0).mean()))
        else:
            v.append(float((seg.std(axis=0) / np.abs(seg.mean(axis=0)).clip(1e-6)).mean()) if kind == "cv"
                     else float(seg.std(axis=0).mean()))
        c.append(t0 + win_s / 2)
    return np.array(c), np.array(v)


def smooth_rows(x, k=10):
    """Moving average over k packets (50 ms at 200 Hz) along time, for complex or real arrays."""
    ker = np.ones(k) / k
    return np.apply_along_axis(lambda r: np.convolve(r, ker, mode="same"), 0, x)


def circ_std(x: np.ndarray, axis=0) -> np.ndarray:
    r = np.abs(np.mean(np.exp(1j * x), axis=axis))
    return np.sqrt(-2 * np.log(np.clip(r, 1e-12, 1)))


def wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


def spreads(amp_n, sph, sel):
    """Mean over carriers of the temporal spread inside a packet selection."""
    if sel.sum() < 50:
        return dict(amp=np.nan, phase=np.nan, dphase=np.nan)
    a = amp_n[sel]
    s = sph[sel]
    d = wrap(np.diff(s, axis=0))
    return dict(amp=float((a.std(axis=0) / a.mean(axis=0)).mean()),       # coefficient of variation
                phase=float(circ_std(s - np.angle(np.mean(np.exp(1j * s), axis=0)), 0).mean()),
                dphase=float(np.sqrt((d ** 2).mean(axis=0)).mean()))


def analyse_rx(p, meta):
    h, ht = p["hdr"], p["ht"]
    n = len(h)
    t = (h["tx_time_us"].astype(np.int64) - int(h["tx_time_us"][0])) / 1e6
    hu = ht[:, USED_COL]
    ok = np.all(np.isfinite(hu), axis=1)
    hu, t, rssi = hu[ok], t[ok], h["rssi"][ok].astype(float)
    amp = np.abs(hu)
    # carriers (csi_inspect logic on the full 128 / 64 arrays)
    r = ci.analyse(p, int(p["hdr"]["tx_time_us"][0]), None, None)
    res, verdict = ci.lltf_mapping(p)
    out = dict(records=n, ht_null=r["htltf_null_subcarriers"], ht_used=r["htltf_used_count"],
               ht_80211n=r["htltf_matches_80211n_ht40"], lltf_null=r["lltf_null_bins"], lltf_verdict=verdict)
    # scaling levels
    pw = 10 * np.log10(np.mean(amp ** 2, axis=1))
    main = float(np.median(pw[pw > np.percentile(pw, 30)]))
    low = pw < main - LOW_STEP_DB
    high = pw > main + LOW_STEP_DB
    out.update(pw_main_db=round(main, 2), low_frac=float(low.mean()), high_frac=float(high.mean()))
    if low.sum() >= 5:
        out["low_step_db"] = round(float(np.median(pw[low]) - main), 2)
        # same scale on every carrier? compare mean amplitude profile of low vs main packets (time-local)
        ratio_db = 20 * np.log10(amp[low].mean(axis=0) / amp[~low & ~high].mean(axis=0))
        out["low_step_carrier_spread_db"] = round(float(ratio_db.std()), 2)
        out["low_rssi_minus_main_rssi"] = round(float(rssi[low].mean() - rssi[~low].mean()), 2)
        # run lengths of low-level packets (consecutive in packet order)
        d = np.diff(np.concatenate([[0], low.astype(np.int8), [0]]))
        runs = np.flatnonzero(d == -1) - np.flatnonzero(d == 1)
        out["low_run_median"] = float(np.median(runs))
        out["low_run_max"] = int(runs.max())
    keep = ~low & ~high
    if np.std(rssi[keep]) > 0:
        out["slope_pw_vs_rssi"] = round(float(np.polyfit(rssi[keep], pw[keep], 1)[0]), 3)
    # phase: raw vs sanitised (temporal circular std, mean over carriers), whole take
    raw_ph = np.angle(hu)
    sph = sanitise(hu)                                   # standard: unwrap + LS line (used below)
    sph_r, slope_r = sanitise_robust(hu)                 # alternative, compared only (rejected)
    out["raw_phase_cstd"] = round(float(circ_std(raw_ph, 0).mean()), 3)
    out["san_phase_cstd"] = round(float(circ_std(sph, 0).mean()), 3)
    out["san_phase_cstd_robust"] = round(float(circ_std(sph_r, 0).mean()), 3)
    out["slope_jump_frac_unwrap"] = slope_jump_frac(sanitise_slope(hu))
    out["slope_jump_frac_robust"] = slope_jump_frac(slope_r)
    amp_n = amp / amp.mean(axis=1, keepdims=True)       # gain-normalised (removes the scale steps)
    # 50 ms smoothed series: amplitude, sanitised phase (via smoothed unit phasors), phase rate
    amp_s = smooth_rows(amp_n)
    ph_s = np.angle(smooth_rows(np.exp(1j * sph)))
    dph = np.abs(wrap(np.diff(ph_s[::10], axis=0)))      # change per 50 ms
    t_d = t[::10][1:]
    series = dict(amp=spread_series(amp_s, t, kind="cv"), phase=spread_series(ph_s, t, kind="circ"),
                  dphase=spread_series(dph, t_d, kind="lin", fs=20))
    if meta["kind"] == "event" and meta.get("cue_s") is not None:
        cue = float(meta["cue_s"])
        out["pre_cue_walking"] = "walk" in (meta.get("instruction") or "").lower().split("on the beep")[0]
        for k, (c, v) in series.items():
            pre = v[(c >= 0.8) & (c <= cue - 0.5)]
            act = v[(c >= cue) & (c <= cue + 4)]
            post = v[c >= cue + 5]
            out[f"pre_{k}"] = float(np.median(pre)) if len(pre) else np.nan
            out[f"peak_{k}"] = float(act.max()) if len(act) else np.nan
            out[f"post_{k}"] = float(np.median(post)) if len(post) else np.nan
            out[f"contrast_{k}"] = out[f"peak_{k}"] / out[f"pre_{k}"] if out[f"pre_{k}"] else np.nan
            out[f"tpeak_{k}"] = float(c[(c >= cue) & (c <= cue + 4)][np.argmax(act)] - cue) if len(act) else np.nan
    else:
        for k, (c, v) in series.items():
            out[f"whole_{k}"] = float(np.median(v)) if len(v) else np.nan
    zero = (amp == 0).mean()
    out["zero_amp_frac"] = float(zero)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    folders = sorted(p.parent for p in a.raw.glob("*/meta.json") if not p.parent.name.startswith("_"))
    if a.limit:
        folders = folders[:a.limit]
    rows = []
    for f in folders:
        meta = json.loads((f / "meta.json").read_text())
        for rx in (1, 2):
            p = load_rx(f, rx)
            r = analyse_rx(p, meta)
            rows.append(dict(session_id=meta["session_id"], subject=meta["subject"], kind=meta["kind"],
                             activity=meta["activity"], position=meta["position"], rx=f"RX{rx}", **r))
        print(f"{meta['session_id']:<40} " + "  ".join(
            f"RX{x['rx'][-1]} low {x['low_frac']:.3f} step {x.get('low_step_db', '-')}" for x in rows[-2:]), flush=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / "phase2_takes.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    # ---------------- summary
    S = {}
    S["takes"] = len(folders)
    S["ht_null_patterns"] = dict(collections.Counter(r["ht_null"] for r in rows))
    S["ht_used_counts"] = dict(collections.Counter(int(r["ht_used"]) for r in rows))
    S["lltf_null_patterns"] = dict(collections.Counter(r["lltf_null"] for r in rows))
    S["lltf_verdicts"] = dict(collections.Counter(r["lltf_verdict"] for r in rows))
    for rx in ("RX1", "RX2"):
        R = [r for r in rows if r["rx"] == rx]
        lf = np.array([r["low_frac"] for r in R])
        steps = np.array([r["low_step_db"] for r in R if "low_step_db" in r])
        spread = np.array([r["low_step_carrier_spread_db"] for r in R if "low_step_carrier_spread_db" in r])
        S[f"{rx}_scaling"] = dict(
            takes_with_low_packets=int((lf > 0).sum()), low_frac_median=float(np.median(lf)),
            low_frac_p90=float(np.percentile(lf, 90)), low_frac_max=float(lf.max()),
            step_db_median=float(np.median(steps)) if len(steps) else None,
            step_db_p5_p95=[float(np.percentile(steps, 5)), float(np.percentile(steps, 95))] if len(steps) else None,
            carrier_spread_db_median=float(np.median(spread)) if len(spread) else None,
            high_frac_max=float(max(r["high_frac"] for r in R)),
            slope_pw_vs_rssi_median=float(np.nanmedian([r.get("slope_pw_vs_rssi", np.nan) for r in R])),
            low_frac_median_by_activity={act: float(np.median([r["low_frac"] for r in R if r["activity"] == act]))
                                         for act in sorted({r["activity"] for r in R})})
        S[f"{rx}_phase"] = dict(raw_cstd_median=float(np.median([r["raw_phase_cstd"] for r in R])),
                                san_cstd_median_unwrap=float(np.median([r["san_phase_cstd"] for r in R])),
                                san_cstd_median_robust=float(np.median([r["san_phase_cstd_robust"] for r in R])),
                                slope_jump_frac_unwrap_mean=float(np.mean([r["slope_jump_frac_unwrap"] for r in R])),
                                slope_jump_frac_robust_mean=float(np.mean([r["slope_jump_frac_robust"] for r in R])),
                                zero_amp_frac_mean=float(np.mean([r["zero_amp_frac"] for r in R])))
        ev = [r for r in R if r["kind"] == "event" and not r.get("pre_cue_walking")]
        S[f"{rx}_event_takes_used"] = len(ev)
        con = {}
        for k in ("amp", "phase", "dphase"):
            c = np.array([r[f"contrast_{k}"] for r in ev], float)
            con[k] = dict(median=float(np.nanmedian(c)), frac_above_1_5=float(np.nanmean(c > 1.5)),
                          frac_above_2=float(np.nanmean(c > 2)),
                          by_activity={act: float(np.nanmedian([r[f"contrast_{k}"] for r in ev if r["activity"] == act]))
                                       for act in sorted({r["activity"] for r in ev})})
        S[f"{rx}_event_contrast"] = con
        st = [r for r in R if r["kind"] == "state"]
        S[f"{rx}_state_spread"] = {act: {k: float(np.median([r[f"whole_{k}"] for r in st if r["activity"] == act]))
                                         for k in ("amp", "phase", "dphase")}
                                   for act in sorted({r["activity"] for r in st})}
    (OUT / "phase2_summary.json").write_text(json.dumps(S, indent=2))
    print("\n" + json.dumps(S, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
