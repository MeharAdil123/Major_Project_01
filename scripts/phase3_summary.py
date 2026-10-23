#!/usr/bin/env python3
"""Gate 3 dataset summary (reads data/processed + data/features; writes results/dataset/).

    python3 scripts/phase3_summary.py > results/dataset/summary.log
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import features as fx  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PROC, FEAT, OUT = ROOT / "data" / "processed", ROOT / "data" / "features", ROOT / "results" / "dataset"
SUBJ = ["S1", "S2", "S3", "S4", "S5", "S6", "none"]
ORDER = ["empty", "sit", "stand", "walk", "lie", "fall", "sit_down", "stand_up", "bend_pick"]


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def table(rows, key_row, key_col, rows_order, cols_order, title):
    print(f"\n{title}")
    print(" " * 11 + "".join(f"{c:>9}" for c in cols_order) + "    total")
    for r in rows_order:
        vals = [sum(1 for x in rows if x[key_row] == r and x[key_col] == c) for c in cols_order]
        if sum(vals):
            print(f"{r:<11}" + "".join(f"{v:>9}" for v in vals) + f"{sum(vals):>9}")
    print(f"{'total':<11}" + "".join(f"{sum(1 for x in rows if x[key_col] == c):>9}" for c in cols_order) + f"{len(rows):>9}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for tag in ("2s", "3s", "4s"):
        if not (FEAT / f"features_{tag}.csv").exists():
            continue
        F = read(FEAT / f"features_{tag}.csv")
        idx = read(PROC / f"index_{tag}.csv")
        print(f"\n================ {tag} windows: {len(F)} kept")
        cand = sum(int(r["candidates"]) for r in idx)
        gate = sum(int(r["rejected_gate"]) for r in idx)
        drop = sum(int(r["dropped_label"]) for r in idx)
        print(f"candidates {cand}; gate-rejected {gate} ({100 * gate / cand:.1f} %); dropped by labelling {drop} "
              f"({100 * drop / cand:.1f} %); kept {len(F)}")
        print("gate-rejected % per subject: " + "  ".join(
            f"{s} {100 * sum(int(r['rejected_gate']) for r in idx if r['subject'] == s) / max(1, sum(int(r['candidates']) for r in idx if r['subject'] == s)):.1f}"
            for s in SUBJ))
        unused = [r["session_id"] for r in idx if r["used"] != "True"]
        print(f"takes not used: {unused or 'none'}; takes with 0 kept windows: "
              f"{[r['session_id'][9:] for r in idx if r['used'] == 'True' and int(r['kept']) == 0] or 'none'}")
        table(F, "window_label", "subject", ORDER, SUBJ, "windows per label x subject (all sources)")
        for src in ("state", "event", "event_pre", "event_post"):
            table([x for x in F if x["source"] == src], "window_label", "subject", ORDER, SUBJ, f"source = {src}")
    on = read(PROC / "onsets.csv")
    print("\n================ event takes (onset o2, from the last build)")
    for act in ("fall", "sit_down", "stand_up", "bend_pick"):
        R = [r for r in on if r["activity"] == act]
        print(f"  {act:<10} takes {len(R):>2}; onset detected {sum(r['detected'] == 'True' for r in R):>2}; "
              f"usable for event training {sum(r['usable_for_event_training'] == 'True' for r in R):>2}; not usable: "
              + ", ".join(f"{r['session_id'][9:]} ({r['reason']})" for r in R if r["usable_for_event_training"] != "True"))
    falls = [r for r in on if r["activity"] == "fall"]
    print(f"  falls with a detected onset: {sum(r['detected'] == 'True' for r in falls)} of {len(falls)}")

    # leakage check on 3 s: within-class correlation of missing share with dynamic features
    F = read(FEAT / "features_3s.csv")
    groups = fx.feature_groups()
    dyn = [n for n, (g, _) in groups.items() if g == "dynamic"]
    from scipy.stats import spearmanr
    print("\n================ leakage check (3 s): Spearman rho between max(rx1_miss, rx2_miss) and each dynamic "
          "feature, within each label (labels with >= 40 windows)")
    worst = []
    for lab in ORDER:
        R = [x for x in F if x["window_label"] == lab]
        if len(R) < 40:
            continue
        miss = np.array([max(float(x["rx1_miss"]), float(x["rx2_miss"])) for x in R])
        rhos = []
        for n in dyn:
            v = np.array([float(x[n]) for x in R])
            rho = spearmanr(miss, v).statistic if np.std(v) > 0 else 0.0
            rhos.append((abs(rho), n, rho))
        rhos.sort(reverse=True)
        a = np.array([r[0] for r in rhos])
        print(f"  {lab:<10} n={len(R):>4}: median |rho| {np.median(a):.2f}, share |rho|>0.3 {np.mean(a > 0.3):.2f}; "
              f"top: " + ", ".join(f"{n} {r:+.2f}" for _, n, r in rhos[:3]))
        worst += [(r[0], lab, r[1], r[2]) for r in rhos[:3]]

    # feature distributions per class (3 s)
    show = ["rx1_sd_mean", "rx2_sd_mean", "rx1_motion_max", "rx2_motion_max", "rx1_ph_cvar_w", "rx2_dph_w",
            "rx1_pc1_frac_3_8Hz", "rx1_sc_corr", "xrx_motion_corr", "rx1_rssi_mean", "rx2_rssi_mean", "rx2_band3_mean"]
    fig, ax = plt.subplots(3, 4, figsize=(18, 11))
    labs = [l for l in ORDER if any(x["window_label"] == l for x in F)]
    for a, n in zip(ax.ravel(), show):
        data = [[float(x[n]) for x in F if x["window_label"] == l] for l in labs]
        a.boxplot(data, tick_labels=labs, showfliers=False)
        a.set_title(f"{n} ({groups[n][0]})", fontsize=9, color="C3" if groups[n][0] == "static" else "k")
        a.tick_params(axis="x", rotation=45, labelsize=7)
        if n.endswith(("sd_mean", "motion_max", "ph_cvar_w", "dph_w")):
            a.set_yscale("log")
    fig.suptitle("Feature distributions per window label, 3 s windows, all subjects (red title = static group)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "feature_distributions_3s.png", dpi=100)
    print(f"\nfigure: {OUT / 'feature_distributions_3s.png'}")


if __name__ == "__main__":
    main()
