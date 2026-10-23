#!/usr/bin/env python3
"""Track B runner: MiniRocket (NumPy re-implementation, ml/minirocket.py) + ridge classifier.

    python3 scripts/phase4_track_b.py --task events --win 3

Input: 16 channels (8 sub-carrier bands x 2 RX of gain-normalised amplitude, window mean removed) at
100 Hz. Per outer fold: MiniRocket biases are fitted on the training windows only (label-free), then
StandardScaler + RidgeClassifier with alpha chosen by inner GroupKFold (3) over training subjects.
Output: results/phase4/track_b/<task>/minirocket__<len>s.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeClassifier
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import evaluate as ev  # noqa: E402
from ml.minirocket import MiniRocket, band_channels  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="events")
    ap.add_argument("--win", default="3")
    a = ap.parse_args()
    tag = f"{a.win}s"
    out = ROOT / "results" / "phase4" / "track_b" / a.task
    if (out / f"minirocket__{tag}.json").exists():
        print("exists, skip:", out / f"minirocket__{tag}.json")
        return
    df = pd.read_csv(ROOT / "data" / "features" / f"features_{tag}.csv", usecols=ev.META_COLS)
    z = np.load(ROOT / "data" / "processed" / f"windows_{tag}.npz", allow_pickle=False)
    assert (z["session_id"] == df["session_id"].to_numpy()).all()
    Xc = np.concatenate([band_channels(z["X"][i:i + 256].astype(np.float32)) for i in range(0, len(df), 256)])
    m, y = ev.task_view(df, a.task)
    Xc, folds = Xc[m], ev.assign_folds(df)[m]
    classes = sorted(set(y.tolist()))
    pred = np.empty(len(y), dtype=object)
    per_fold, best, t_all, pms = {}, {}, time.time(), []
    for test in ev.SUBJECTS:
        tr, te = folds != test, folds == test
        mr = MiniRocket(seed=0).fit(Xc[tr])
        Ftr, Fte = mr.transform(Xc[tr]), mr.transform(Xc[te])
        cv = list(GroupKFold(3).split(Ftr, groups=folds[tr]))
        s = GridSearchCV(Pipeline([("sc", StandardScaler()), ("m", RidgeClassifier(class_weight="balanced"))]),
                         {"m__alpha": [1, 10, 100, 1000, 10000]}, scoring="f1_macro", cv=cv, n_jobs=4).fit(Ftr, y[tr])
        t0 = time.perf_counter()
        pred[te] = s.predict(Fte)
        pms.append((time.perf_counter() - t0) / te.sum() * 1000)
        per_fold[test] = ev.metrics(y[te], pred[te].astype(str), classes)
        best[test] = s.best_params_
        print(f"fold {test}: macro-F1 {per_fold[test]['macro_f1']:.3f} alpha {s.best_params_} features {Ftr.shape[1]}", flush=True)
    res = dict(task=a.task, model="minirocket_numpy", window=tag, classes=classes, **ev.summarise_folds(per_fold),
               pooled=ev.metrics(y, pred.astype(str), classes), per_fold=per_fold, best_params=best,
               n_kernel_features=int(Ftr.shape[1]), input_channels=int(Xc.shape[1]),
               predict_ms_per_window_excl_transform=float(np.mean(pms)), wall_s=round(time.time() - t_all, 1),
               note="MiniRocket NumPy re-implementation (D-043), not the reference code")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"minirocket__{tag}.json").write_text(json.dumps(res, indent=1))
    print(f"MiniRocket {a.task} {tag}: {res['macro_f1_mean']:.3f} ± {res['macro_f1_std']:.3f} {res['macro_f1_per_fold']}")


if __name__ == "__main__":
    main()
