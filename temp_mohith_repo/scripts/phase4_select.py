#!/usr/bin/env python3
"""Gate 4: comparison table and the selection rule (PROMPT Phase 4.2), per task, at the chosen window.

Rule: best = highest LOSO macro-F1 (mean over 6 folds). Candidates = models with mean >= best - std(best).
A candidate "wins or ties" a fold when its fold score >= best's fold score - TIE. The prompt's "at least
3 of the 4 folds" (75 %) becomes at least WIN_FOLDS = 5 of 6 folds. Among candidates that pass, the
simplest (COMPLEXITY rank, then higher mean) is selected. A 4-of-6 reading is reported alongside.
Deep models: fold score = mean over 3 seeds. Output: results/phase4/selection.json, comparison_<task>.csv
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
P4 = ROOT / "results" / "phase4"
TIE = 0.02
WIN_FOLDS = 5
FOLDS = ["S1", "S2", "S3", "S4", "S5", "S6"]
COMPLEXITY = {"logreg": 1, "knn": 2, "svm_rbf": 3, "rf": 4, "extra_trees": 4, "hist_gb": 5, "xgboost": 5,
              "lightgbm": 5, "minirocket_numpy": 6}


def load(task, tag):
    rows = []
    for p in (P4 / "track_a" / task).glob(f"*__dynamic__{tag}.json"):
        r = json.loads(p.read_text())
        rows.append(dict(track="A", model=r["model"], featset="dynamic", mean=r["macro_f1_mean"], std=r["macro_f1_std"],
                         folds=r["macro_f1_per_fold"], fit_s=r["fit_s_total"], predict_ms=r["predict_ms_per_window"],
                         size=f"{r['n_features']} features", pooled=r["pooled"]))
    for p in (P4 / "ablations" / task).glob(f"*__all__{tag}.json"):
        r = json.loads(p.read_text())
        rows.append(dict(track="A", model=r["model"], featset="all", mean=r["macro_f1_mean"], std=r["macro_f1_std"],
                         folds=r["macro_f1_per_fold"], fit_s=r["fit_s_total"], predict_ms=r["predict_ms_per_window"],
                         size=f"{r['n_features']} features", pooled=r["pooled"]))
    p = P4 / "track_b" / task / f"minirocket__{tag}.json"
    if p.exists():
        r = json.loads(p.read_text())
        rows.append(dict(track="B", model="minirocket_numpy", featset="16 band channels", mean=r["macro_f1_mean"],
                         std=r["macro_f1_std"], folds=r["macro_f1_per_fold"], fit_s=r["wall_s"],
                         predict_ms=r["predict_ms_per_window_excl_transform"],
                         size=f"{r['n_kernel_features']} kernel features", pooled=r["pooled"]))
    for p in (P4 / "track_c" / task).glob(f"*__{tag}.json"):
        r = json.loads(p.read_text())
        rows.append(dict(track="C", model=r["model"], featset="32 band channels", mean=r["macro_f1_mean"], std=r["macro_f1_std"],
                         folds=r["macro_f1_per_fold"], fit_s=r["train_s"], predict_ms=r["predict_ms_per_window"],
                         size=f"{r['n_params']} params", seed_std=r["macro_f1_seed_std"],
                         pooled=r["per_seed"]["0"]["pooled"]))
    return rows


def main():
    tag = json.loads((P4 / "chosen_window.json").read_text())["chosen"]
    out = dict(window=tag, tie=TIE, win_folds_required=WIN_FOLDS, tasks={})
    for task in ("events", "state", "presence"):
        rows = load(task, tag)
        best = max(rows, key=lambda r: r["mean"])
        for r in rows:
            r["wins_or_ties"] = int(sum(r["folds"][f] >= best["folds"][f] - TIE for f in FOLDS))
            r["within_1sd"] = bool(r["mean"] >= best["mean"] - best["std"])
            r["passes_5of6"] = r["within_1sd"] and r["wins_or_ties"] >= WIN_FOLDS
            r["passes_4of6"] = r["within_1sd"] and r["wins_or_ties"] >= 4
            r["complexity"] = COMPLEXITY.get(r["model"], 7)
        pick = lambda key: min([r for r in rows if r[key]], key=lambda r: (r["complexity"], -r["mean"]))  # noqa: E731
        sel, sel4 = pick("passes_5of6"), pick("passes_4of6")
        out["tasks"][task] = dict(best=dict(model=best["model"], track=best["track"], mean=best["mean"], std=best["std"]),
                                  selected=dict(model=sel["model"], track=sel["track"], featset=sel["featset"],
                                                mean=sel["mean"], std=sel["std"], wins_or_ties=sel["wins_or_ties"]),
                                  selected_if_4of6=dict(model=sel4["model"], featset=sel4["featset"], mean=sel4["mean"]),
                                  candidates=[dict(model=r["model"], featset=r["featset"], mean=round(r["mean"], 4),
                                                   wins_or_ties=r["wins_or_ties"]) for r in rows if r["within_1sd"]])
        rows.sort(key=lambda r: -r["mean"])
        with open(P4 / f"comparison_{task}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["track", "model", "input", "macro_f1_mean", "macro_f1_std", "seed_std"] + FOLDS +
                       ["wins_or_ties_vs_best", "within_1sd", "passes_rule", "fit_or_train_s", "predict_ms_per_window", "size"]
                       + (["fall_f1", "fall_sensitivity"] if task == "events" else [])
                       + (["sensitivity", "specificity"] if task == "presence" else []))
            for r in rows:
                extra = []
                if task == "events":
                    fv = r["pooled"].get("fall_vs_rest", {})
                    extra = [round(fv.get("f1", np.nan), 3), round(fv.get("sensitivity", np.nan), 3)]
                if task == "presence":
                    extra = [round(r["pooled"].get("presence_sensitivity", np.nan), 3), round(r["pooled"].get("presence_specificity", np.nan), 3)]
                w.writerow([r["track"], r["model"], r["featset"], round(r["mean"], 4), round(r["std"], 4),
                            round(r.get("seed_std", np.nan), 4)] + [round(r["folds"][f], 3) for f in FOLDS] +
                           [r["wins_or_ties"], r["within_1sd"], r["passes_5of6"], round(r["fit_s"], 1),
                            round(r["predict_ms"], 3), r["size"]] + extra)
        print(f"\n== {task} ({tag}): best {best['model']} {best['mean']:.3f} ± {best['std']:.3f}; "
              f"selected {sel['model']} ({sel['featset']}) {sel['mean']:.3f}, wins/ties {sel['wins_or_ties']}/6; "
              f"with 4-of-6: {sel4['model']} ({sel4['featset']})")
        for r in rows[:12]:
            print(f"   {r['track']} {r['model']:<17} {r['featset']:<17} {r['mean']:.3f} ± {r['std']:.3f}  w/t {r['wins_or_ties']}/6"
                  f"  {'1sd' if r['within_1sd'] else '   '}  {'PASS' if r['passes_5of6'] else ''}")
    (P4 / "selection.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.exit(main())
