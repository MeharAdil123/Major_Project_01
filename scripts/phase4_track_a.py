#!/usr/bin/env python3
"""Track A runner: nested LOSO for classical models on data/features/features_<len>s.csv.

    python3 scripts/phase4_track_a.py --tasks events state presence --wins 3 2 4 \
        --featsets dynamic all --models logreg knn svm_rbf rf extra_trees hist_gb xgboost lightgbm

One JSON per run: results/phase4/track_a/<task>/<model>__<featset>__<len>s.json (per-fold metrics,
pooled metrics, confusion, best params per fold, fit time, predict time). Existing JSONs are skipped
(--force reruns). A table of all runs: results/phase4/track_a/summary.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import evaluate as ev  # noqa: E402
from ml import models_classical as mc  # noqa: E402

OUT = ROOT / "results" / "phase4" / "track_a"


def run(df, task, model, featset, tag, force=False, state_sources=None, out_name=None, out_dir=None, rows=None):
    """One nested-LOSO run; writes <name>.json and <name>.pred.csv (per-window predictions).
    rows: optional boolean mask over df (e.g. the 15 % gate subset)."""
    path = (out_dir or OUT) / task / (out_name or f"{model}__{featset}__{tag}.json")
    if path.exists() and not force:
        return json.loads(path.read_text())
    kw = {} if state_sources is None else dict(state_sources=state_sources)
    m, y = ev.task_view(df, task, **kw)
    if rows is not None:
        y = y[rows[m]] if len(y) == m.sum() else y
        m = m & rows
    cols = ev.feature_set(featset)
    X = df.loc[m, cols].to_numpy(np.float64)
    folds = ev.assign_folds(df)[m]
    t0 = time.time()
    r = ev.nested_loso(X, y, folds, mc.make_search_factory(model))
    res = dict(task=task, model=model, featset=featset, window=tag, n_features=len(cols), n_windows=int(len(y)),
               classes=r.classes, **ev.summarise_folds(r.per_fold), pooled=r.pooled, per_fold=r.per_fold,
               best_params=r.best_params, fit_s_total=round(r.fit_s, 1),
               predict_ms_per_window=round(r.predict_ms_per_window, 4), wall_s=round(time.time() - t0, 1),
               cross_session_folds=sorted(ev.CROSS_SESSION), state_sources=list(state_sources) if state_sources else None)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(dict(session_id=df.loc[m, "session_id"].to_numpy(), t_start=df.loc[m, "t_start"].to_numpy(),
                      position=df.loc[m, "position"].to_numpy(), activity=df.loc[m, "activity_label"].to_numpy(),
                      fold=folds, y=y, pred=r.pred)).to_csv(path.with_suffix(".pred.csv"), index=False)
    tmp = path.with_suffix(".json.partial")
    tmp.write_text(json.dumps(res, indent=1))
    tmp.rename(path)                                   # the JSON only exists once the run is complete
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=list(ev.TASKS))
    ap.add_argument("--wins", nargs="+", default=["3"])
    ap.add_argument("--featsets", nargs="+", default=["dynamic", "all"])
    ap.add_argument("--models", nargs="+", default=list(mc.MODELS))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    rows = []
    for w in a.wins:
        tag = f"{w}s"
        df = pd.read_csv(ROOT / "data" / "features" / f"features_{tag}.csv")
        for task in a.tasks:
            for fs in a.featsets:
                for model in a.models:
                    t0 = time.time()
                    r = run(df, task, model, fs, tag, a.force)
                    print(f"{task:<9} {tag} {fs:<8} {model:<12} macro-F1 {r['macro_f1_mean']:.3f} ± {r['macro_f1_std']:.3f}  "
                          f"folds {r['macro_f1_per_fold']}  ({time.time() - t0:.0f} s)", flush=True)
    for p in sorted(OUT.glob("*/*.json")):
        r = json.loads(p.read_text())
        rows.append(dict(task=r["task"], window=r["window"], featset=r["featset"], model=r["model"],
                         macro_f1_mean=round(r["macro_f1_mean"], 4), macro_f1_std=round(r["macro_f1_std"], 4),
                         **{f"f1_{k}": v for k, v in r["macro_f1_per_fold"].items()},
                         pooled_macro_f1=round(r["pooled"]["macro_f1"], 4), n_windows=r["n_windows"],
                         fit_s_total=r["fit_s_total"], predict_ms_per_window=r["predict_ms_per_window"],
                         file=str(p.relative_to(ROOT))))
    if rows:
        with open(OUT / "summary.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
