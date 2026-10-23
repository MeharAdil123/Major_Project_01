#!/usr/bin/env python3
"""Train the final models on all six subjects and save them in Format 3 (D-050). See docs/CONTRACTS.md.

    python3 -m ml.train_final

models/presence/   logistic regression, dynamic f2 features, 4 s windows   (empty | occupied)
models/state/      extra trees, dynamic f2                                 (sit | stand | walk | lie)
models/events/     SVM-RBF, dynamic f2                                     (fall | sit_down | stand_up | bend_pick | none)
models/fall_alarm/ calibrated binary SVM (only if D-051 adopted it; results/phase4/fall_chain/summary.json)
Hyper-parameters: the same grids as the LOSO evaluation, chosen by GroupKFold(3) over the six subjects
(empty-room takes dealt to subject groups as in evaluation). LOSO scores in model_meta.json are the
evaluation results (results/phase4/...), not scores of these refitted models.
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml import evaluate as ev  # noqa: E402
from ml import features as fx  # noqa: E402
from ml import models_classical as mc  # noqa: E402
from pipeline import onset as od  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

TAG, WIN_S, FEATSET = "4s", 4.0, "dynamic"
CHOICE = {"presence": "logreg", "state": "extra_trees", "events": "svm_rbf"}
P4 = ROOT / "results" / "phase4"
CURRENT_CHAIN = dict(source="events model P(fall)", theta=0.6, k=2, n=3, cooldown_s=10.0)


def git_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return None


def loso_scores(task, model):
    r = json.loads((P4 / "track_a" / task / f"{model}__{FEATSET}__{TAG}.json").read_text())
    keep = {k: r["pooled"][k] for k in ("macro_f1", "accuracy", "presence_sensitivity", "presence_specificity", "fall_vs_rest")
            if k in r["pooled"]}
    return dict(macro_f1_mean=r["macro_f1_mean"], macro_f1_std=r["macro_f1_std"], macro_f1_per_fold=r["macro_f1_per_fold"],
                pooled=keep, source=f"results/phase4/track_a/{task}/{model}__{FEATSET}__{TAG}.json")


def save(task, est, classes, meta, models_dir):
    import joblib
    d = models_dir / task
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(est, d / "model.joblib")
    (d / "model_meta.json").write_text(json.dumps(meta, indent=1, default=float))
    print(f"saved {d}: classes {classes}")


def env_profile(X: np.ndarray) -> np.ndarray:
    """Static channel shape of a window set: mean gain-normalised amplitude per RX and carrier, in dB. X [N,2,T,S]."""
    return 20 * np.log10(np.maximum(np.asarray(X, np.float32).mean(axis=(0, 2)), 1e-6))


def env_baseline(df, cols, models_dir: Path, common: dict):
    """Empty-room reference for the live environment check (Phase 5): dynamic-feature distribution of the
    7 training empty-room takes, their static profiles per RX, and the RSSI level."""
    e = df["window_label"].to_numpy() == "empty"
    F = df.loc[e, cols].to_numpy(np.float64)
    z = np.load(ROOT / "data" / "processed" / f"windows_{TAG}.npz", allow_pickle=False)
    assert (z["session_id"] == df["session_id"].to_numpy()).all()
    sess = df.loc[e, "session_id"].to_numpy()
    idx = np.flatnonzero(e)
    profiles = {s: env_profile(z["X"][idx[sess == s]]).tolist() for s in sorted(set(sess))}
    P = np.array(list(profiles.values()))                                    # [takes, 2, S]
    rms = [float(np.sqrt(np.mean((P[i, r] - P[j, r]) ** 2))) for r in (0, 1)
           for i in range(len(P)) for j in range(i + 1, len(P))]
    rs = df.loc[e, ["rx1_rssi_mean", "rx2_rssi_mean"]].to_numpy() if "rx1_rssi_mean" in df else None
    out = dict(source="7 empty-room takes (4 s windows, features_4s.csv)", n_windows=int(e.sum()), takes=sorted(set(sess)),
               dynamic=dict(names=cols, median=np.median(F, 0).tolist(), p05=np.percentile(F, 5, 0).tolist(),
                            p95=np.percentile(F, 95, 0).tolist(), mean=F.mean(0).tolist(), std=(F.std(0) + 1e-12).tolist()),
               profiles_db=profiles, profile_rms_db_between_training_takes=dict(median=float(np.median(rms)), max=float(np.max(rms))),
               rssi=dict(rx1_median=float(np.median(rs[:, 0])), rx2_median=float(np.median(rs[:, 1]))) if rs is not None else None,
               **{k: common[k] for k in ("features_version", "preproc_version", "window_s", "trained_at", "git_commit")})
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "env_baseline.json").write_text(json.dumps(out))
    print(f"saved {models_dir / 'env_baseline.json'}: {e.sum()} empty windows, profile RMS between takes "
          f"median {out['profile_rms_db_between_training_takes']['median']:.2f} dB")


def main(models_dir: Path = ROOT / "models") -> int:
    import sklearn
    df = pd.read_csv(ROOT / "data" / "features" / f"features_{TAG}.csv")
    cols = ev.feature_set(FEATSET)
    groups_all = ev.assign_folds(df)
    common = dict(features_version=fx.FEATURES_VERSION, preproc_version=pp.PREPROC_VERSION, onset_version=od.ONSET_VERSION,
                  window_s=WIN_S, fs=pp.FS, featset=FEATSET, feature_names=cols, synthetic=False,
                  trained_at=time.strftime("%Y-%m-%d %H:%M:%S"), trained_on=sorted(ev.SUBJECTS) + ["7 empty-room takes"],
                  git_commit=git_commit(), python=platform.python_version(), sklearn=sklearn.__version__,
                  limitations="1 room, 1 layout, 6 volunteers, simulated falls on a mattress (all at spot M), no video ground truth, not clinical")
    fall = json.loads((P4 / "fall_chain" / "summary.json").read_text()) if (P4 / "fall_chain" / "summary.json").exists() else None
    adopted = bool(fall and fall.get("adopt"))
    for task, model in CHOICE.items():
        m, y = ev.task_view(df, task)
        X, g = df.loc[m, cols].to_numpy(np.float64), groups_all[m]
        t0 = time.time()
        s = mc.make_search_factory(model)(g).fit(X, y)
        meta = dict(task=task, model=model, classes=list(s.best_estimator_.classes_), best_params=s.best_params_,
                    inner_cv_macro_f1=float(s.best_score_), n_train=int(len(y)), fit_s=round(time.time() - t0, 1),
                    loso=loso_scores(task, model), **common)
        if task == "events":
            meta["alarm"] = (dict(source="models/fall_alarm (calibrated binary SVM)", adopted_D051=True)
                             if adopted else dict(CURRENT_CHAIN, adopted_D051=False,
                                                  evaluation="results/phase4/pertake/svm_rbf__dynamic__4s.json"))
        save(task, s.best_estimator_, meta["classes"], meta, models_dir)
    env_baseline(df, cols, models_dir, common)
    if adopted:
        sys.path.insert(0, str(ROOT / "scripts"))
        import phase4_fall_chain as fc
        X, y, folds, *_ = fc.load()
        params, inner = fc.choose_params(X, y, folds)
        est = fc.fit_model(X, y, folds, params)
        fs = json.loads((P4 / "fall_chain" / "final_settings.json").read_text())["chosen"]
        meta = dict(task="fall_alarm", model="svm_rbf + Platt (sigmoid) calibration, LOSO calibration splits",
                    classes=list(est.classes_), best_params=params, inner_cv_fall_f1=inner, n_train=int(len(y)),
                    alarm=dict(theta=fs["theta"], k=fs["k"], n=fs["n"], cooldown_s=fc.COOLDOWN_S,
                               selection="D-051 constrained selection on all six subjects' outer-LOSO stream predictions"),
                    loso_chain=fall["new"], **common)
        save("fall_alarm", est, meta["classes"], meta, models_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
