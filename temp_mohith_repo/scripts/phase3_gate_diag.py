#!/usr/bin/env python3
"""D-023: why do some takes lose every window? Then the loss-tolerance sweep (read-only on data/raw).

    python3 scripts/phase3_gate_diag.py > results/dataset/gate_diag.log

Part 1, for S1_T06_walk, S1_T22_sit, S3_T43_sit (and a clean control take), checks per RX:
  - seq order: duplicates, backward jumps (wrap / TX reboot), records outside the common range
  - gap counting: longest gap from the seq differences vs from the grid's missing mask (must agree)
  - alignment: common seq range of RX1/RX2 vs each RX's own range; share of packets seen by both
  - per window (v1, 2 s, hop 1 s): which RX and which rule (missing share / longest gap) rejects it
Part 2: share of windows rejected for missing-packet limits 10 / 15 / 20 % (max gap 100 ms) on
  2 / 3 / 4 s windows (states hop 1 s, events hop 0.5 s), per take, per subject, overall.
Outputs: results/dataset/gate_sweep_takes.csv
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
from pipeline import preprocess as pp  # noqa: E402

RAW, OUT = ROOT / "data" / "raw", ROOT / "results" / "dataset"
CASES = ["20261022_S1_T06_walk", "20261022_S1_T22_sit", "20261022_S3_T43_sit", "20261022_S4_T01_stand"]
LIMITS = (0.10, 0.15, 0.20)
MAX_GAP = 20                 # packets = 100 ms
WINS = (2, 3, 4)


def raw_seq(folder, rx):
    rec = cw.load(folder / f"RX{rx}.bin")
    h = rec.hdr
    ok = ((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)
    return h["seq"][ok].astype(np.int64)


def longest_gap_from_seq(seq):
    d = np.diff(np.unique(seq))
    return int((d - 1).max()) if len(d) else 0


def part1():
    print("== Part 1: diagnosis of takes that lose every v1 window")
    for sid in CASES:
        f = RAW / sid
        print(f"\n-- {sid}")
        per_rx = {}
        for rx in (1, 2):
            s = raw_seq(f, rx)
            d = np.diff(s)
            per_rx[rx] = pp.records_from_recording(cw.load(f / f"RX{rx}.bin"))
            print(f"  RX{rx}: {len(s)} records, seq {s[0]}..{s[-1]} (span {s[-1] - s[0] + 1}), "
                  f"duplicates {int((d == 0).sum())}, backward jumps {int((d < 0).sum())}, "
                  f"loss {100 * (1 - len(np.unique(s)) / (s[-1] - s[0] + 1)):.2f} %, "
                  f"longest gap {longest_gap_from_seq(s)} pkts ({5 * (longest_gap_from_seq(s) + 1)} ms between packets)")
        g = pp.build_grid(per_rx)
        L = g["amp"].shape[1]
        s1, s2 = per_rx[1]["seq"], per_rx[2]["seq"]
        both = len(np.intersect1d(s1, s2)) / len(np.union1d(s1, s2))
        print(f"  grid: seq {g['seq0']}..{g['seq0'] + L - 1} (L={L}); RX1 outside grid {int(((s1 < g['seq0']) | (s1 >= g['seq0'] + L)).sum())}, "
              f"RX2 outside {int(((s2 < g['seq0']) | (s2 >= g['seq0'] + L)).sum())}; seen by both {100 * both:.1f} %")
        for k, rx in enumerate((1, 2)):
            mg = pp.longest_run(g["missing"][k])
            sg = longest_gap_from_seq(per_rx[rx]["seq"][(per_rx[rx]["seq"] >= g["seq0"]) & (per_rx[rx]["seq"] < g["seq0"] + L)])
            print(f"  RX{rx}: missing in grid {100 * g['missing'][k].mean():.2f} %, longest run from mask {mg} vs from seq {sg}"
                  + ("  OK" if mg == sg else "  MISMATCH"))
        span = pp.WIN * pp.DECIM
        starts = list(range(200, L - span - 200 + 1, 200))
        w = pp.cut_windows(g, starts)
        reasons = []
        for mf, mgap in zip(w["miss_frac"], w["max_gap"]):
            r = []
            for k in (0, 1):
                if mf[k] > pp.MAX_MISS_FRAC:
                    r.append(f"RX{k + 1} miss {100 * mf[k]:.0f}%")
                if mgap[k] > pp.MAX_GAP_PKTS:
                    r.append(f"RX{k + 1} gap {mgap[k]}")
            reasons.append(", ".join(r) or "ok")
        print(f"  v1 windows: {int(w['ok'].sum())}/{len(starts)} kept; per-window miss % RX1 "
              f"[{100 * w['miss_frac'][:, 0].min():.0f}..{100 * w['miss_frac'][:, 0].max():.0f}] RX2 "
              f"[{100 * w['miss_frac'][:, 1].min():.0f}..{100 * w['miss_frac'][:, 1].max():.0f}], longest gap RX1 "
              f"{int(w['max_gap'][:, 0].max())} RX2 {int(w['max_gap'][:, 1].max())} pkts")
        from collections import Counter
        print("  reasons:", dict(Counter(", ".join(sorted({x.split(' ')[0] + ' ' + x.split(' ')[1] for x in r.split(', ')}))
                                         if r != "ok" else "ok" for r in reasons)))


def window_starts(L, win_s, kind):
    span = int(win_s * pp.FS_IN)
    hop = pp.FS_IN if kind == "state" else pp.FS_IN // 2
    skip = pp.FS_IN if kind == "state" else 0
    return list(range(skip, L - span - skip + 1, hop)), span


def part2():
    print("\n== Part 2: rejected share for missing limits 10/15/20 % (max gap 100 ms), both RX must pass")
    rows = []
    folders = sorted(p.parent for p in RAW.glob("*/meta.json") if not p.parent.name.startswith("_"))
    for f in folders:
        meta = json.loads((f / "meta.json").read_text())
        per_rx = {rx: pp.records_from_recording(cw.load(f / f"RX{rx}.bin")) for rx in (1, 2)}
        g = pp.build_grid(per_rx)
        L = g["amp"].shape[1]
        miss = g["missing"]
        cm = np.concatenate([np.zeros((2, 1)), np.cumsum(miss, axis=1)], axis=1)
        for win in WINS:
            starts, span = window_starts(L, win, meta["kind"])
            if not starts:
                continue
            st = np.array(starts)
            mf = (cm[:, st + span] - cm[:, st]) / span                      # [2, N]
            gaps = np.array([[pp.longest_run(miss[k, s:s + span]) for s in st] for k in (0, 1)])
            row = dict(session_id=meta["session_id"], subject=meta["subject"], kind=meta["kind"],
                       activity=meta["activity"], position=meta["position"], win_s=win, windows=len(st))
            for lim in LIMITS:
                ok = (mf <= lim).all(axis=0) & (gaps <= MAX_GAP).all(axis=0)
                row[f"rejected_pct_{int(lim * 100)}"] = round(100 * (1 - ok.mean()), 1)
                row[f"rejected_by_gap_only_{int(lim * 100)}"] = int(((mf <= lim).all(axis=0) & ~(gaps <= MAX_GAP).all(axis=0)).sum())
            rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "gate_sweep_takes.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for win in WINS:
        R = [r for r in rows if r["win_s"] == win]
        n = sum(r["windows"] for r in R)
        print(f"\n  {win} s windows ({n} candidate windows in {len(R)} takes)")
        for lim in LIMITS:
            k = f"rejected_pct_{int(lim * 100)}"
            rej = sum(r["windows"] * r[k] / 100 for r in R)
            zero = [r["session_id"][9:] for r in R if r[k] >= 99.9]
            by_gap = sum(r[f"rejected_by_gap_only_{int(lim * 100)}"] for r in R)
            print(f"    limit {int(lim * 100):>2} %: rejected {100 * rej / n:5.1f} % of windows "
                  f"({by_gap} only by the 100 ms gap rule); takes losing all windows: {len(zero)} {zero}")
            per_s = {}
            for r in R:
                per_s.setdefault(r["subject"], []).append((r["windows"], r[k]))
            print("      per subject: " + "  ".join(f"{s} {100 * sum(a * b / 100 for a, b in v) / sum(a for a, _ in v):.1f}%"
                                                  for s, v in sorted(per_s.items())))
        worst = sorted(R, key=lambda r: -r["rejected_pct_15"])[:8]
        print("    worst takes at 15 %: " + ", ".join(f"{r['session_id'][9:]} {r['rejected_pct_15']}%" for r in worst))


if __name__ == "__main__":
    part1()
    part2()
