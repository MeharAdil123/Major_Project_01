"""Phase 4 evaluation framework: LOSO folds, tasks, feature sets, nested search, metrics.

Rules (docs/PROJECT_RULES.md rule 6, CONTRACTS): leave-one-subject-out over S1..S6 only; empty-room takes are dealt
to folds take by take; scaling, feature selection and hyper-parameter search happen inside the
training subjects of each outer fold (inner GroupKFold over training subjects); never random windows.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from ml import features as fx
from pipeline import labels as lb

SUBJECTS = ["S1", "S2", "S3", "S4", "S5", "S6"]
CROSS_SESSION = {"S5", "S6"}                          # afternoon session (D-033): folds test a session change
META_COLS = ["session_id", "subject", "take_id", "activity_label", "window_label", "position", "t_start",
             "rx1_miss", "rx2_miss", "source", "kind"]


# ------------------------------------------------------------------ folds
def assign_folds(df: pd.DataFrame) -> np.ndarray:
    """Fold id (= test subject) per row. Empty-room takes (subject 'none') are dealt round-robin,
    take by take, in session-id order: B00->S1, B01->S2, _r2->S3, _r4->S4, _r5->S5, _r6->S6, _r8->S1."""
    fold = df["subject"].astype(str).to_numpy().copy()
    empties = sorted(df.loc[df["subject"] == "none", "session_id"].unique())
    for k, s in enumerate(empties):
        fold[df["session_id"].to_numpy() == s] = SUBJECTS[k % len(SUBJECTS)]
    return fold


# ------------------------------------------------------------------ tasks
TASKS = ("presence", "state", "events")


def task_view(df: pd.DataFrame, task: str, state_sources=("state", "event_pre", "event_post")):
    """Returns (mask over df rows, y labels for those rows)."""
    lab = df["window_label"].astype(str).to_numpy()
    src = df["source"].astype(str).to_numpy()
    if task == "presence":
        m = np.ones(len(df), bool)
        return m, np.where(lab == "empty", "empty", "occupied")
    if task == "state":
        m = np.isin(lab, lb.STATES) & np.isin(src, state_sources)
        return m, lab[m]
    if task == "events":
        m = np.ones(len(df), bool)
        return m, np.where(src == "event", lab, "none")
    raise ValueError(task)


# ------------------------------------------------------------------ feature sets
def feature_set(name: str) -> list[str]:
    """all | dynamic | static | rx1 | rx2 | amp_only | minus_<subgroup> | dynamic_minus_<subgroup>."""
    names = fx.feature_names()
    groups = fx.feature_groups()
    if name == "all":
        return names
    if name == "dynamic":
        return [n for n in names if groups[n][0] == "dynamic"]
    if name == "static":
        return [n for n in names if groups[n][0] == "static"]
    if name in ("rx1", "rx2"):
        return [n for n in names if n.startswith(name + "_")]
    if name in ("rx1_dynamic", "rx2_dynamic"):
        return [n for n in names if n.startswith(name[:3] + "_") and groups[n][0] == "dynamic"]
    if name == "amp_only":
        return [n for n in names if groups[n][1] != "phase" and n != "xrx_phase_logratio"]
    if name == "dynamic_amp_only":
        return [n for n in feature_set("amp_only") if groups[n][0] == "dynamic"]
    if name.startswith("dynamic_minus_"):
        sg = name[len("dynamic_minus_"):]
        return [n for n in feature_set("dynamic") if groups[n][1] != sg]
    if name.startswith("minus_"):
        sg = name[len("minus_"):]
        return [n for n in names if groups[n][1] != sg]
    raise ValueError(name)


# ------------------------------------------------------------------ metrics
def metrics(y_true, y_pred, classes) -> dict:
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    present = [c for c in classes if (np.asarray(y_true) == c).any()]
    out = dict(macro_f1=float(f1_score(y_true, y_pred, labels=present, average="macro", zero_division=0)),
               accuracy=float(np.mean(np.asarray(y_true) == np.asarray(y_pred))), n=int(len(y_true)),
               per_class={c: dict(precision=float(p[i]), recall=float(r[i]), f1=float(f[i]), support=int(s[i]))
                          for i, c in enumerate(classes)},
               confusion=dict(labels=list(classes), matrix=confusion_matrix(y_true, y_pred, labels=classes).tolist()))
    if set(classes) == {"empty", "occupied"}:
        yt, yp = np.asarray(y_true) == "occupied", np.asarray(y_pred) == "occupied"
        out["presence_sensitivity"] = float((yt & yp).sum() / max(yt.sum(), 1))
        out["presence_specificity"] = float((~yt & ~yp).sum() / max((~yt).sum(), 1))
    if "fall" in classes:
        yt, yp = np.asarray(y_true) == "fall", np.asarray(y_pred) == "fall"
        tp, fp, fn = (yt & yp).sum(), (~yt & yp).sum(), (yt & ~yp).sum()
        out["fall_vs_rest"] = dict(sensitivity=float(tp / max(tp + fn, 1)), precision=float(tp / max(tp + fp, 1)),
                                   f1=float(2 * tp / max(2 * tp + fp + fn, 1)),
                                   false_alarm_rate=float(fp / max((~yt).sum(), 1)))
    return out


def summarise_folds(per_fold: dict) -> dict:
    f = np.array([v["macro_f1"] for v in per_fold.values()])
    return dict(macro_f1_mean=float(f.mean()), macro_f1_std=float(f.std(ddof=0)),
                macro_f1_per_fold={k: round(v["macro_f1"], 4) for k, v in per_fold.items()})


# ------------------------------------------------------------------ nested LOSO
@dataclass
class Result:
    pred: np.ndarray
    proba: np.ndarray | None
    classes: list
    per_fold: dict
    pooled: dict
    best_params: dict
    fit_s: float
    predict_ms_per_window: float


def nested_loso(X: np.ndarray, y: np.ndarray, folds: np.ndarray, make_search, n_jobs: int = 4) -> Result:
    """make_search(train_folds) -> an sklearn search object (fit/predict/predict_proba, best_params_),
    whose CV splits the training rows by their fold ids (inner subjects)."""
    from joblib import Parallel, delayed
    classes = sorted(set(y.tolist()))

    def one(test):
        tr, te = folds != test, folds == test
        s = make_search(folds[tr])
        t0 = time.perf_counter()
        s.fit(X[tr], y[tr])
        fit_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        pr = s.predict(X[te])
        pt = (time.perf_counter() - t0) / max(te.sum(), 1) * 1000
        pb = None
        if hasattr(s, "predict_proba"):
            try:
                raw = s.predict_proba(X[te])
                pb = np.zeros((te.sum(), len(classes)))
                for j, c in enumerate(s.classes_):
                    pb[:, classes.index(c)] = raw[:, j]
            except (AttributeError, NotImplementedError):
                pb = None
        return test, pr, pb, getattr(s, "best_params_", {}), fit_s, pt

    tests = [s for s in SUBJECTS if (folds == s).any()]
    outs = Parallel(n_jobs=n_jobs)(delayed(one)(t) for t in tests)
    pred = np.empty(len(y), dtype=object)
    proba = np.full((len(y), len(classes)), np.nan)
    per_fold, best = {}, {}
    fit_s, pms = 0.0, []
    for test, pr, pb, bp, fs, pt in outs:
        te = folds == test
        pred[te] = pr
        if pb is not None:
            proba[te] = pb
        per_fold[test] = metrics(y[te], pr, classes)
        best[test] = {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in bp.items()}
        fit_s += fs
        pms.append(pt)
    return Result(pred=pred.astype(str), proba=None if np.isnan(proba).all() else proba, classes=classes,
                  per_fold=per_fold, pooled=metrics(y, pred.astype(str), classes), best_params=best,
                  fit_s=fit_s, predict_ms_per_window=float(np.mean(pms)))
