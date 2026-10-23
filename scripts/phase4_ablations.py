#!/usr/bin/env python3
"""Ablations on the same LOSO folds with the best Track A model per task at the chosen window.

    python3 scripts/phase4_ablations.py --tasks events [--core-only]

Feature sets (ml/evaluate.feature_set): dynamic (reference), all, static, rx1/rx2 (dynamic and all),
dynamic_amp_only and amp_only (amplitude only vs amplitude + phase), dynamic_minus_<subgroup> for each
dynamic subgroup, minus_<static subgroup>. Variants: state task with state-take windows only; 15 % gate
subset (windows with missing share <= 15 % on both RX). Window length 2/3/4 s is Track A stage 2.
Output: results/phase4/ablations/<task>/<model>__<set>__<len>s.json (+ .pred.csv); resumable.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import phase4_track_a as A  # noqa: E402

OUT = ROOT / "results" / "phase4" / "ablations"
CORE = ["dynamic", "all", "static", "rx1_dynamic", "rx2_dynamic", "dynamic_amp_only"]
FULL = CORE + ["rx1", "rx2", "amp_only"] + [f"dynamic_minus_{g}" for g in
                                            ("temporal", "motion", "bandpower", "corr", "rssi_var", "phase", "cross")] \
    + [f"minus_{g}" for g in ("shape", "rssi_level", "pca_shape")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=["events", "state", "presence"])
    ap.add_argument("--core-only", action="store_true")
    a = ap.parse_args()
    ch = json.loads((ROOT / "results" / "phase4" / "chosen_window.json").read_text())
    tag = ch["chosen"]
    df = pd.read_csv(ROOT / "data" / "features" / f"features_{tag}.csv")
    gate15 = ((df["rx1_miss"] <= 0.15) & (df["rx2_miss"] <= 0.15)).to_numpy()
    for task in a.tasks:
        model = ch["best_model_per_task"][task]
        for fs in (CORE if a.core_only else FULL):
            r = A.run(df, task, model, fs, tag, out_dir=OUT)
            print(f"{task:<9} {model:<12} {fs:<26} {r['macro_f1_mean']:.3f} ± {r['macro_f1_std']:.3f} {r['macro_f1_per_fold']}", flush=True)
        r = A.run(df, task, model, "dynamic", tag, out_dir=OUT, rows=gate15, out_name=f"{model}__dynamic_gate15__{tag}.json")
        print(f"{task:<9} {model:<12} {'dynamic, gate 15 %':<26} {r['macro_f1_mean']:.3f} ± {r['macro_f1_std']:.3f} (n={r['n_windows']})", flush=True)
        if task == "state":
            for fs in ("dynamic", "all"):
                r = A.run(df, task, model, fs, tag, out_dir=OUT, state_sources=("state",),
                          out_name=f"{model}__{fs}_stateTakesOnly__{tag}.json")
                print(f"{task:<9} {model:<12} {fs + ', state takes only':<26} {r['macro_f1_mean']:.3f} ± {r['macro_f1_std']:.3f} (n={r['n_windows']})", flush=True)


if __name__ == "__main__":
    main()
