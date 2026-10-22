#!/usr/bin/env python3
"""Validate pipeline/onset.py on every event take (read-only on data/raw).

    python3 scripts/phase2_onset.py > results/signal/onset_validation.log

For WIN_S in (0.25, 0.5): detection rate, interval inside [cue, cue+4 s], onset (reaction) and
duration per class, RX1/RX2 onset agreement. Takes whose instruction does not start still are
detected against a global still baseline and listed with their pre-cue motion level.
Overlays (10 takes per class, spread over subjects): results/signal/onset_<class>.png
Table: results/signal/onset_takes.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import build_dataset as bd  # noqa: E402
from pipeline import onset as od  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAW, OUT = ROOT / "data" / "raw", ROOT / "results" / "signal"
WINS = (0.25, 0.5)


def starts_still(meta):
    return "walk" not in meta["instruction"].lower().split("on the beep")[0]


def load_event_takes():
    takes = []
    for f in sorted(p.parent for p in RAW.glob("*/meta.json") if not p.parent.name.startswith("_")):
        meta = json.loads((f / "meta.json").read_text())
        if meta["kind"] != "event":
            continue
        _, per_rx = bd.load_take(f)
        grid = pp.build_grid(per_rx)
        first = min(int(d["seq"][0]) for d in per_rx.values())
        off_s = (grid["seq0"] - first) / pp.FS_IN               # grid starts this long after the first packet
        takes.append(dict(meta=meta, grid=grid, off_s=off_s, cue_g=meta["cue_s"] - off_s, still=starts_still(meta)))
    return takes


def stat(x):
    x = np.asarray([v for v in x if np.isfinite(v)], float)
    if not len(x):
        return "n=0"
    return f"median {np.median(x):.2f} [p10 {np.percentile(x, 10):.2f}, p90 {np.percentile(x, 90):.2f}] n={len(x)}"


def run(takes, win):
    sig = [od.motion_signal(tk["grid"], win_s=win) for tk in takes]
    pre_raw = []
    for tk, (t, m) in zip(takes, sig):
        pre = (t >= od.PRE_FROM_S) & (t <= tk["cue_g"] - od.PRE_GUARD_S)
        pre_raw.append(np.median(m[:, pre], axis=1))
    still_base = np.median([p for p, tk in zip(pre_raw, takes) if tk["still"]], axis=0)
    rows = []
    for tk, (t, m), pr in zip(takes, sig, pre_raw):
        d = od.detect(t, m, tk["cue_g"], baseline=None if tk["still"] else still_base, win_s=win)
        meta = tk["meta"]
        to_rec = lambda x: x + tk["off_s"] if np.isfinite(x) else np.nan        # noqa: E731  back to take time
        rows.append(dict(session_id=meta["session_id"], subject=meta["subject"], activity=meta["activity"],
                         position=meta["position"], win_s=win, starts_still=tk["still"],
                         pre_level_vs_still=float(np.max(pr / still_base)),
                         detected=d["detected"], inside_search=d["inside_search"], peak_ratio=d["peak_ratio"],
                         onset_clipped_to_cue=d["early"], end_threshold=d["end_threshold"],
                         onset_s=to_rec(d["onset"]), end_s=to_rec(d["end"]),
                         reaction_s=to_rec(d["onset"]) - meta["cue_s"], duration_s=d["end"] - d["onset"],
                         rx1_onset_s=to_rec(d["rx1_onset"]), rx2_onset_s=to_rec(d["rx2_onset"]),
                         rx1_detected=d["rx1_detected"], rx2_detected=d["rx2_detected"],
                         instruction=meta["instruction"]))
        rows[-1]["_t"], rows[-1]["_m"], rows[-1]["_base"] = t + tk["off_s"], m, (pr if tk["still"] else still_base)
    return rows, still_base


def report(rows, win, still_base):
    print(f"\n================ WIN_S = {win} s  (global still baseline RX1 {still_base[0]:.3f}, RX2 {still_base[1]:.3f})")
    S = [r for r in rows if r["starts_still"]]
    print(f"takes: {len(rows)} ({len(S)} start still)")
    for name, R in (("all", rows), ("start still", S)):
        det = np.mean([r["detected"] for r in R])
        ins = np.mean([r["inside_search"] for r in R])
        print(f"  {name:<12} detected {det:.2f}; interval inside [cue, cue+4 s] {ins:.2f}")
    both = [r for r in rows if r["rx1_detected"] and r["rx2_detected"]]
    dd = [abs(r["rx1_onset_s"] - r["rx2_onset_s"]) for r in both]
    print(f"  RX1 and RX2 both detect: {len(both)}/{len(rows)}; |onset RX1 - RX2| {stat(dd)}; "
          f"<= 0.25 s {np.mean(np.array(dd) <= 0.25):.2f}, <= 0.5 s {np.mean(np.array(dd) <= 0.5):.2f}")
    print(f"  only RX1: {sum(r['rx1_detected'] and not r['rx2_detected'] for r in rows)}, "
          f"only RX2: {sum(r['rx2_detected'] and not r['rx1_detected'] for r in rows)}, "
          f"neither: {sum(not r['rx1_detected'] and not r['rx2_detected'] for r in rows)}")
    for act in sorted({r["activity"] for r in rows}):
        R = [r for r in rows if r["activity"] == act and r["detected"]]
        n = sum(r["activity"] == act for r in rows)
        print(f"    {act:<10} detected {len(R)}/{n}  reaction {stat([r['reaction_s'] for r in R])}")
        print(f"    {'':<10} duration {stat([r['duration_s'] for r in R])}  peak ratio {stat([r['peak_ratio'] for r in R])}")
    miss = [r for r in rows if not r["detected"] or not r["inside_search"]]
    print(f"  not detected or outside the search window ({len(miss)}):")
    for r in miss:
        print(f"    {r['session_id']:<34} {r['position']:<4} det {r['detected']!s:<5} peak {r['peak_ratio']:.2f} "
              f"onset {r['onset_s']:.2f} end {r['end_s']:.2f}" + ("  (onset clipped: motion before cue)" if r["onset_clipped_to_cue"] else ""))


def overlays(rows, win):
    rng = np.random.default_rng(0)
    for act in sorted({r["activity"] for r in rows}):
        R = [r for r in rows if r["activity"] == act]
        by_s = {}
        for r in R:
            by_s.setdefault(r["subject"], []).append(r)
        pick = []
        while len(pick) < min(10, len(R)):                      # round-robin over subjects
            for s in sorted(by_s):
                if by_s[s] and len(pick) < 10:
                    pick.append(by_s[s].pop(int(rng.integers(len(by_s[s])))))
        fig, ax = plt.subplots(len(pick), 1, figsize=(12, 1.9 * len(pick)), sharex=True)
        for a, r in zip(np.atleast_1d(ax), pick):
            rel = r["_m"] / r["_base"][:, None]
            a.plot(r["_t"], rel[0], lw=0.9, label="RX1")
            a.plot(r["_t"], rel[1], lw=0.9, label="RX2")
            a.axvline(3.0, color="k", ls="--", lw=1)
            a.axvspan(3.0, 7.0, color="0.92", zorder=0)
            a.axhline(od.THR_HI, color="r", ls=":", lw=0.8)
            a.axhline(od.THR_LO, color="orange", ls=":", lw=0.8)
            if r["detected"]:
                a.axvspan(r["onset_s"], r["end_s"], color="tab:green", alpha=0.25, zorder=1)
            a.set_yscale("log")
            a.set_ylim(0.3, max(20, np.nanmax(rel) * 1.2))
            a.text(0.005, 0.92, f"{r['session_id'][9:]} @{r['position']}  "
                   + (f"onset +{r['reaction_s']:.2f} s, dur {r['duration_s']:.2f} s" if r["detected"] else "NOT DETECTED")
                   + ("" if r["starts_still"] else "  [starts walking: global baseline]"),
                   transform=a.transAxes, fontsize=8, va="top")
        np.atleast_1d(ax)[0].legend(loc="upper right", fontsize=7)
        np.atleast_1d(ax)[-1].set_xlabel("time in take (s); dashed = cue; grey = search [cue, cue+4 s]; green = detected action")
        fig.suptitle(f"{act}: motion / baseline (log), WIN_S {win} s, red = THR_HI {od.THR_HI:g}, orange = THR_LO {od.THR_LO:g}",
                     fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT / f"onset_{act}.png", dpi=100)
        plt.close(fig)


def main():
    takes = load_event_takes()
    allrows = []
    for win in WINS:
        rows, base = run(takes, win)
        report(rows, win, base)
        allrows += rows
        if win == od.WIN_S:
            overlays(rows, win)
            print("\n== takes that do not start still (instruction), pre-cue motion vs global still baseline:")
            for r in rows:
                if not r["starts_still"]:
                    print(f"  {r['session_id']:<30} pre-cue {r['pre_level_vs_still']:.1f}x  "
                          f"det {r['detected']!s:<5} peak {r['peak_ratio']:.1f}x  onset +{r['reaction_s']:.2f} s "
                          f"dur {r['duration_s']:.2f} s | {r['instruction'][:60]}")
            lvl = sorted(((r["pre_level_vs_still"], r["session_id"]) for r in rows if r["starts_still"]), reverse=True)[:8]
            print("  highest pre-cue level among 'start still' takes: " + ", ".join(f"{s[9:]} {v:.1f}x" for v, s in lvl))
    keys = [k for k in allrows[0] if not k.startswith("_")]
    with open(OUT / "onset_takes.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows({k: r[k] for k in keys} for r in allrows)


if __name__ == "__main__":
    main()
