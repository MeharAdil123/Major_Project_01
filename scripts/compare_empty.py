#!/usr/bin/env python3
"""Compare empty-room takes (read-only): RSSI, loss, and the static channel profile.

    python3 scripts/compare_empty.py > results/audit/empty_compare.log

Profile = time-mean HT-LTF amplitude per sub-carrier (114 used carriers), each packet first
divided by its own mean (gain-normalised, as preprocess v1). Two takes are compared by the
correlation of their profiles and the RMS difference in dB. Morning = takes in the baseline
table results/audit/raw_takes.csv; afternoon = the others.
"""
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

base = {r["session_id"] for r in csv.DictReader(open(ROOT / "results/audit/raw_takes.csv"))}
rows = {r["session_id"]: r for r in csv.DictReader(open(ROOT / "results/audit/raw_takes_all.csv"))}
takes = sorted(s for s, r in rows.items() if r["subject"] == "none")
prof = {}
print(f"{'take':<30} {'when':<9} {'dur':>5} | {'RX1 rssi':>8} {'loss%':>6} | {'RX2 rssi':>8} {'loss%':>6}")
for s in takes:
    r = rows[s]
    when = "morning" if s in base else "afternoon"
    print(f"{s:<30} {when:<9} {float(r['duration_s']):>5.0f} | {r['RX1_rssi_med']:>8} {r['RX1_loss_pct']:>6} | "
          f"{r['RX2_rssi_med']:>8} {r['RX2_loss_pct']:>6}")
    for rx in (1, 2):
        d = pp.records_from_recording(cw.load(ROOT / "data/raw" / s / f"RX{rx}.bin"))
        a = pp.normalise(d["amp"])
        prof[(s, rx)] = (20 * np.log10(a.mean(axis=0)), a.std(axis=0).mean())
for rx in (1, 2):
    print(f"\nRX{rx}: profile similarity (corr / RMS dB difference); temporal std (mean over carriers)")
    print(" " * 31 + " ".join(f"{t[-12:]:>13}" for t in takes))
    for s in takes:
        p = prof[(s, rx)][0]
        cells = []
        for t in takes:
            q = prof[(t, rx)][0]
            cells.append(f"{np.corrcoef(p, q)[0, 1]:.3f}/{np.sqrt(np.mean((p - q) ** 2)):.2f}")
        print(f"{s[-30:]:<30} " + " ".join(f"{c:>13}" for c in cells) + f"   std {prof[(s, rx)][1]:.4f}")
    m = [s for s in takes if s in base]
    af = [s for s in takes if s not in base]
    within_m = [np.sqrt(np.mean((prof[(a, rx)][0] - prof[(b, rx)][0]) ** 2)) for i, a in enumerate(m) for b in m[i + 1:]]
    within_a = [np.sqrt(np.mean((prof[(a, rx)][0] - prof[(b, rx)][0]) ** 2)) for i, a in enumerate(af) for b in af[i + 1:]]
    cross = [np.sqrt(np.mean((prof[(a, rx)][0] - prof[(b, rx)][0]) ** 2)) for a in m for b in af]
    print(f"RX{rx} RMS dB difference: within morning {np.median(within_m):.2f} (max {max(within_m):.2f}), "
          f"within afternoon {np.median(within_a):.2f} (max {max(within_a):.2f}), "
          f"morning vs afternoon {np.median(cross):.2f} (max {max(cross):.2f})")
