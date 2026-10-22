#!/usr/bin/env python3
"""Track C runner: deep models under the same LOSO folds and labels as Track A.

    python3 scripts/phase4_track_c.py --task events --win 3 --models cnn1d lstm ... --seeds 0 1 2

Outer fold = test subject. Inner validation subject (early stopping) = the next subject in S1..S6 order
(cyclic) among the training subjects; never the test subject. Channel standardisation uses training
windows only. 3 seeds; report mean +- std over folds per seed and over seeds. Training curves of fold
S1, seed 0 are saved. Output: results/phase4/track_c/<task>/<model>__<len>s.json (+ curves png).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import deep as dp  # noqa: E402
from ml import evaluate as ev  # noqa: E402

OUT = ROOT / "results" / "phase4" / "track_c"


def load(tag):
    df = pd.read_csv(ROOT / "data" / "features" / f"features_{tag}.csv", usecols=ev.META_COLS)
    z = np.load(ROOT / "data" / "processed" / f"windows_{tag}.npz", allow_pickle=False)
    assert len(z["y"]) == len(df) and (z["session_id"] == df["session_id"].to_numpy()).all(), "npz/csv row mismatch"
    assert (z["y"] == df["window_label"].astype(str).to_numpy()).all()
    C = np.concatenate([dp.channels(z["X"][i:i + 256], z["P"][i:i + 256]) for i in range(0, len(df), 256)])
    return df, C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="events")
    ap.add_argument("--win", default="3")
    ap.add_argument("--models", nargs="+", default=list(dp.MODELS))
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    tag = f"{a.win}s"
    df, C = load(tag)
    m, y = ev.task_view(df, a.task)
    C, folds = C[m], ev.assign_folds(df)[m]
    classes = sorted(set(y.tolist()))
    yi = np.array([classes.index(v) for v in y])
    k = len(classes)
    (OUT / a.task).mkdir(parents=True, exist_ok=True)
    for name in a.models:
        path = OUT / a.task / f"{name}__{tag}.json"
        if path.exists():
            print("skip", path)
            continue
        res = dict(task=a.task, model=name, window=tag, classes=classes, seeds=a.seeds,
                   n_params=dp.n_params(dp.build(name, C.shape[1], k, C.shape[2])), input_shape=list(C.shape[1:]),
                   budget=dict(max_epochs=dp.MAX_EPOCHS, patience=dp.PATIENCE, batch=dp.BATCH, lr=1e-3, wd=1e-2),
                   per_seed={}, train_s=0.0)
        t_all = time.time()
        pms = []
        for seed in a.seeds:
            pred = np.empty(len(y), dtype=object)
            per_fold, epochs = {}, {}
            for test in ev.SUBJECTS:
                train_subj = [s for s in ev.SUBJECTS if s != test]
                val = train_subj[(ev.SUBJECTS.index(test)) % len(train_subj)]
                tr, va, te = np.isin(folds, [s for s in train_subj if s != val]), folds == val, folds == test
                mu = C[tr | va].mean(axis=(0, 2), keepdims=True)
                sd = C[tr | va].std(axis=(0, 2), keepdims=True) + 1e-6
                norm = lambda x: ((x - mu) / sd).astype(np.float32)  # noqa: E731
                t0 = time.time()
                mdl, hist, best_ep = dp.train_one(name, norm(C[tr]), yi[tr], norm(C[va]), yi[va], k, seed)
                res["train_s"] += time.time() - t0
                t0 = time.perf_counter()
                p = dp.predict_proba(mdl, norm(C[te]))
                pms.append((time.perf_counter() - t0) / max(te.sum(), 1) * 1000)
                pred[te] = np.array(classes)[p.argmax(1)]
                per_fold[test] = ev.metrics(y[te], pred[te].astype(str), classes)
                epochs[test] = dict(best_epoch=best_ep, epochs_run=len(hist), inner_val_subject=val)
                if seed == a.seeds[0] and test == "S1":
                    res["curves_fold_S1_seed0"] = hist
            s = ev.summarise_folds(per_fold)
            res["per_seed"][str(seed)] = dict(**s, pooled=ev.metrics(y, pred.astype(str), classes), epochs=epochs,
                                              per_fold={f: dict(macro_f1=v["macro_f1"],
                                                                fall_vs_rest=v.get("fall_vs_rest")) for f, v in per_fold.items()})
            print(f"{name:<11} seed {seed}: macro-F1 {s['macro_f1_mean']:.3f} ± {s['macro_f1_std']:.3f} {s['macro_f1_per_fold']}", flush=True)
        means = [v["macro_f1_mean"] for v in res["per_seed"].values()]
        fold_means = {f: float(np.mean([v["macro_f1_per_fold"][f] for v in res["per_seed"].values()])) for f in ev.SUBJECTS}
        res.update(macro_f1_mean=float(np.mean(list(fold_means.values()))), macro_f1_std=float(np.std(list(fold_means.values()))),
                   macro_f1_seed_std=float(np.std(means)), macro_f1_per_fold={f: round(v, 4) for f, v in fold_means.items()},
                   predict_ms_per_window=float(np.mean(pms)), wall_s=round(time.time() - t_all, 1), train_s=round(res["train_s"], 1))
        path.write_text(json.dumps(res, indent=1))
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            h = res["curves_fold_S1_seed0"]
            fig, ax = plt.subplots(1, 2, figsize=(9, 3))
            ax[0].plot([x["train_loss"] for x in h], label="train")
            ax[0].plot([x["val_loss"] for x in h], label="val (inner subject)")
            ax[0].set_title("loss")
            ax[0].legend()
            ax[1].plot([x["val_macro_f1"] for x in h])
            ax[1].set_title("val macro-F1")
            fig.suptitle(f"{name}, {a.task}, {tag}, test fold S1, seed {a.seeds[0]}", fontsize=9)
            fig.tight_layout()
            fig.savefig(OUT / a.task / f"{name}__{tag}_curves.png", dpi=90)
            plt.close(fig)
        except Exception as e:  # figures must not stop the run
            print("curve plot failed:", e)
        print(f"{name}: {res['macro_f1_mean']:.3f} ± {res['macro_f1_std']:.3f} (seed std {res['macro_f1_seed_std']:.3f}), "
              f"{res['n_params']} params, {res['wall_s']:.0f} s", flush=True)


if __name__ == "__main__":
    main()
