#!/usr/bin/env python3
"""Compare motion-peak detectors on every event take (read-only; no ground truth exists).

    python3 scripts/phase2_peaks.py > results/signal/phase2_peaks.log

builder : pipeline/build_dataset.motion_energy (mean |diff| of gain-normalised amplitude between
          consecutive 200 Hz packets, both RX averaged, 0.2 s box smoothing), argmax in [cue, cue+4 s]
smooth  : per RX, gain-normalised amplitude low-passed with a 50 ms moving average, then the mean over
          carriers of the std in a 0.5 s sliding window; each RX divided by its own pre-cue median;
          combined = max over RX; argmax in [cue, cue+4 s]
Proxies for quality (no video): peak-to-baseline ratio (pre-cue median, takes that start still), and
agreement of the per-RX peak times |t_RX1 - t_RX2| (both receivers see the same movement).
Output: results/signal/phase2_peaks.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402
from pipeline import build_dataset as bd  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

RAW, OUT = ROOT / "data" / "raw", ROOT / "results" / "signal"
FS = pp.FS_IN


def per_rx_energy_builder(grid, r):
    a = pp.normalise(grid["amp"][r:r + 1])
    d = np.abs(np.diff(a, axis=1)).mean(axis=(0, 2))
    d = np.concatenate([[d[0]], d])
    k = int(0.2 * FS)
    return np.convolve(d, np.ones(k) / k, mode="same")


def per_rx_energy_smooth(grid, r):
    a = pp.normalise(grid["amp"][r])                         # [L, S]
    k = int(0.05 * FS)
    a = np.apply_along_axis(lambda x: np.convolve(x, np.ones(k) / k, mode="same"), 0, a)
    w = int(0.5 * FS)
    c = np.cumsum(np.vstack([np.zeros((1, a.shape[1])), a]), axis=0)
    c2 = np.cumsum(np.vstack([np.zeros((1, a.shape[1])), a ** 2]), axis=0)
    m = (c[w:] - c[:-w]) / w
    v = np.clip((c2[w:] - c2[:-w]) / w - m ** 2, 0, None)
    e = np.sqrt(v).mean(axis=1)
    return np.concatenate([np.full(w // 2, e[0]), e, np.full(len(a) - len(e) - w // 2, e[-1])])


def peak(e, lo, hi):
    return lo + int(np.argmax(e[lo:hi]))


def main():
    rows = []
    folders = sorted(p.parent for p in RAW.glob("*/meta.json") if not p.parent.name.startswith("_"))
    for f in folders:
        meta = json.loads((f / "meta.json").read_text())
        if meta["kind"] != "event":
            continue
        meta_walk = "walk" in meta["instruction"].lower().split("on the beep")[0]
        _, per_rx = bd.load_take(f)
        grid = pp.build_grid(per_rx)
        L = grid["amp"].shape[1]
        # time origin = first packet of either RX (recording start), as in the figures
        seq_first = min(int(d["seq"][0]) for d in per_rx.values())
        off = grid["seq0"] - seq_first                      # grid index 0 is this many packets after start
        cue = int(meta["cue_s"] * FS) - off
        lo, hi = max(cue, 0), min(L, cue + 4 * FS)
        pre = slice(int(0.8 * FS) - off, cue - int(0.5 * FS))
        row = dict(session_id=meta["session_id"], subject=meta["subject"], activity=meta["activity"],
                   position=meta["position"], pre_cue_walking=meta_walk)
        eb = bd.motion_energy(grid)
        row["builder_t"] = (peak(eb, lo, hi) + off) / FS - meta["cue_s"]
        row["builder_snr"] = float(eb[lo:hi].max() / np.median(eb[pre]))
        es = []
        for r, name in ((0, "RX1"), (1, "RX2")):
            b = per_rx_energy_builder(grid, r)
            s = per_rx_energy_smooth(grid, r)
            s_n = s / np.median(s[pre])
            es.append(s_n)
            row[f"builder_t_{name}"] = (peak(b, lo, hi) + off) / FS - meta["cue_s"]
            row[f"smooth_t_{name}"] = (peak(s, lo, hi) + off) / FS - meta["cue_s"]
            row[f"builder_snr_{name}"] = float(b[lo:hi].max() / np.median(b[pre]))
            row[f"smooth_snr_{name}"] = float(s_n[lo:hi].max())
        comb = np.maximum(*es)
        row["smooth_t"] = (peak(comb, lo, hi) + off) / FS - meta["cue_s"]
        row["smooth_snr"] = float(comb[lo:hi].max())
        row["grid_offset_pkts"] = int(off)
        rows.append(row)
    with open(OUT / "phase2_peaks.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def stat(x):
        x = np.asarray(x, float)
        return f"median {np.median(x):.2f}  p25 {np.percentile(x, 25):.2f}  p75 {np.percentile(x, 75):.2f}"
    still = [r for r in rows if not r["pre_cue_walking"]]
    print(f"event takes: {len(rows)} ({len(still)} start still, {len(rows) - len(still)} start walking)")
    print(f"grid offset (packets between first packet and common grid start): max {max(r['grid_offset_pkts'] for r in rows)}")
    for m in ("builder", "smooth"):
        print(f"\n== {m}")
        print(f"  peak-to-baseline ratio (still-start takes): {stat([r[m + '_snr'] for r in still])}")
        print(f"  share with ratio > 2: {np.mean([r[m + '_snr'] > 2 for r in still]):.2f}")
        dt = [abs(r[f'{m}_t_RX1'] - r[f'{m}_t_RX2']) for r in rows]
        print(f"  |t_RX1 - t_RX2| (s): {stat(dt)};  share <= 0.5 s: {np.mean(np.array(dt) <= 0.5):.2f}")
        print(f"  peak time after cue (s): {stat([r[m + '_t'] for r in rows])}")
        print(f"  peak in last 0.3 s of the search window (edge): {np.mean([r[m + '_t'] > 3.7 for r in rows]):.2f}")
        for act in sorted({r['activity'] for r in rows}):
            R = [r for r in rows if r["activity"] == act]
            print(f"    {act:<10} n={len(R):>2}  t {stat([r[m + '_t'] for r in R])}  ratio {stat([r[m + '_snr'] for r in R])}")
    d = [abs(r["builder_t"] - r["smooth_t"]) for r in rows]
    print(f"\n|builder_t - smooth_t| (s): {stat(d)}; share > 1 s: {np.mean(np.array(d) > 1):.2f}")


if __name__ == "__main__":
    main()
