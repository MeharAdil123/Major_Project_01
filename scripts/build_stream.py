#!/usr/bin/env python3
"""Stream features for the per-take evaluation of the live decision chain (D-025, Gate 2 note 3).

    python3 scripts/build_stream.py --win 3

Every take is cut exactly as the live engine would: windows every 0.5 s over the whole take (no
edge skipping, no labelling, no dropping of transition windows). Windows failing the quality gate
are kept as rows with gate_ok = False (live: status "degraded", no prediction). Features f2 for the
gate-passing windows. Output: data/features/stream_<len>s.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import features as fx  # noqa: E402
from pipeline import build_dataset as bd  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

HOP_S = 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", type=float, default=3.0)
    ap.add_argument("--max-miss", type=float, default=pp.MAX_MISS_FRAC)
    ap.add_argument("--max-gap", type=int, default=pp.MAX_GAP_PKTS)
    a = ap.parse_args()
    t0 = time.time()
    overrides = bd.load_overrides()
    folders = sorted(p.parent for p in (ROOT / "data" / "raw").glob("*/meta.json") if not p.parent.name.startswith("_"))
    names = fx.feature_names()
    out = ROOT / "data" / "features" / f"stream_{a.win:g}s.csv"
    with open(out, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["session_id", "subject", "take_id", "activity", "kind", "position", "t_start", "t_end",
                     "gate_ok", "rx1_miss", "rx2_miss"] + names)
        for f in folders:
            meta, per_rx = bd.load_take(f)
            ok_take, _ = bd.take_valid(meta, overrides)
            if not ok_take:
                continue
            grid = pp.build_grid(per_rx)
            L = grid["amp"].shape[1]
            first = min(int(d["seq"][0]) for d in per_rx.values())
            off_s = (grid["seq0"] - first) / pp.FS_IN
            span = int(round(a.win * pp.FS_IN))
            starts = list(range(0, L - span + 1, int(HOP_S * pp.FS_IN)))
            w = pp.cut_windows(grid, starts, a.win, a.max_miss, a.max_gap)
            F = fx.batch_features(w["X"][w["ok"]], w["P"][w["ok"]], w["rssi"][w["ok"]]) if w["ok"].any() else None
            j = 0
            for i in range(len(starts)):
                ts = w["start_pkt"][i] / pp.FS_IN + off_s
                row = [meta["session_id"], meta["subject"], meta["take_id"], meta["activity"], meta["kind"],
                       meta["position"], round(ts, 3), round(ts + a.win, 3), bool(w["ok"][i]),
                       round(float(w["miss_frac"][i, 0]), 4), round(float(w["miss_frac"][i, 1]), 4)]
                if w["ok"][i]:
                    row += F[j].tolist()
                    j += 1
                else:
                    row += [""] * len(names)
                wr.writerow(row)
            print(f"{meta['session_id']:<36} windows {len(starts):>3} gate-ok {int(w['ok'].sum()):>3}", flush=True)
    print(f"done in {time.time() - t0:.0f} s -> {out}")


if __name__ == "__main__":
    main()
