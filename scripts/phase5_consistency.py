#!/usr/bin/env python3
"""Live vs offline consistency on real takes with the final models (Phase 5.2). Read-only on data/raw.

    python3 scripts/phase5_consistency.py > results/phase5/consistency.log
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.consistency import compare_take  # noqa: E402
from ml.predict import Predictor  # noqa: E402

TAKES = [l.split()[1] for l in (ROOT / "results" / "signal_selection.txt").read_text().splitlines() if l.strip()] + \
        ["20261022_S1_T06_walk", "20261022_S3_T43_sit", "20261022_S2_E58_bend_pick", "20261022_S6_E21_fall"]


def main():
    p = Predictor(ROOT / "models")
    ok = True
    for sid in TAKES:
        r = compare_take(ROOT / "data" / "raw" / sid, p)
        ok &= r["identical"] or r["windows"] == 0
        print(f"{sid:<32} windows {r['windows']:>3}  max|dX| {r['max_abs_diff_X']:.2e}  max|dP| {r['max_abs_diff_P']:.2e}  "
              f"max|dRSSI| {r['max_abs_diff_rssi']:.2e}  max|dprob| {r['max_abs_diff_prob']:.2e}  "
              f"same label {r['same_label']}/{r['windows']}  same event {r['same_event']}/{r['windows']}  "
              f"{'IDENTICAL' if r['identical'] else ('no ok windows' if r['windows'] == 0 else 'DIFFERENT')}", flush=True)
    print("ALL IDENTICAL" if ok else "DIFFERENCES FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
