#!/usr/bin/env python3
"""D-051: bounded fall-alarm experiment. Binary fall-vs-rest SVM with Platt calibration; alarm threshold
and k-of-n rule chosen from INNER leave-one-subject-out predictions only.

    python3 scripts/phase4_fall_chain.py            # resumable: one file per outer fold
    python3 scripts/phase4_fall_chain.py --final    # selection on all six subjects' outer-LOSO predictions

Per outer fold (test subject T, training subjects = the other five):
  1. SVM hyper-parameters (C, gamma) by GroupKFold(3) over the training subjects, scoring = F1 of "fall".
  2. Model = CalibratedClassifierCV(SVC, method="sigmoid", cv = leave-one-subject-out over the training
     subjects, ensemble=False): Platt calibration fitted on out-of-subject decision values, training subjects only.
  3. Inner predictions: for every training subject U, a model trained on the other four scores U's stream
     windows (data/features/stream_4s.csv). No window is ever scored by a model that saw it.
  4. Settings grid: theta in 0.30..0.95 (step 0.05) x rule in {1-of-2, 2-of-3, 2-of-4}, 10 s cooldown.
     Constraints on the inner predictions: look-alike takes with an alarm / look-alike takes <= 9/109, and
     walking alarms per hour <= BASE_WALK_PER_H (current chain). Objective: max share of fall takes detected;
     ties -> fewer look-alike alarms -> fewer walking alarms -> higher theta. If nothing meets the constraints,
     the setting with the fewest look-alike alarms (then highest theta) is used, and this is logged.
  5. The model trained on all five training subjects scores T's stream windows; the chosen setting is applied
     unchanged.
Outputs: results/phase4/fall_chain/fold_<T>.json, fold_<T>_stream.csv; summary.json (+ --final: final_settings.json)
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import evaluate as ev  # noqa: E402

OUT = ROOT / "results" / "phase4" / "fall_chain"
TAG = "4s"
LOOKALIKE = ("sit_down", "stand_up", "bend_pick")
STILL = ("empty", "sit", "stand", "lie")
MAX_LOOKALIKE_SHARE = 9 / 109
BASE = dict(falls=18, lookalike=9, walk_per_h=45.4, still_per_h=3.18)    # current chain (results/phase4/pertake)
THETAS = np.round(np.arange(0.30, 0.951, 0.05), 2)
RULES = ((1, 2), (2, 3), (2, 4))
COOLDOWN_S = 10.0
GRID = [dict(C=c, gamma=g) for c in (1, 10) for g in ("scale", 0.01)]


def alarms(t_end, p, ok, theta, k, n):
    votes, last, out = collections.deque(maxlen=n), -1e9, []
    for t, x, g in zip(t_end, p, ok):
        if not g:
            continue
        votes.append(x >= theta)
        if sum(votes) >= k and t - last > COOLDOWN_S:
            out.append(float(t))
            last = t
    return out


def evaluate_takes(st: pd.DataFrame, p: np.ndarray, theta, k, n, onsets=None):
    """Per-take alarms for the rows of st (one or more subjects). Returns summary dict + per-take frame."""
    rows = []
    for sid, g in st.groupby("session_id", sort=True):
        g = g.sort_values("t_end")
        al = alarms(g["t_end"].to_numpy(), p[g["_i"].to_numpy()], g["gate_ok"].to_numpy(bool), theta, k, n)
        r = dict(session_id=sid, subject=g["subject"].iloc[0], fold=g["fold"].iloc[0], activity=g["activity"].iloc[0],
                 duration_s=float(g["t_end"].max()), n_alarms=len(al), first_alarm_s=al[0] if al else np.nan)
        if onsets is not None and sid in onsets.index and bool(onsets.loc[sid, "detected"]) and al:
            r["latency_s"] = al[0] - float(onsets.loc[sid, "onset_s"])
        rows.append(r)
    R = pd.DataFrame(rows)
    f, lk, wk, sl = R[R.activity == "fall"], R[R.activity.isin(LOOKALIKE)], R[R.activity == "walk"], R[R.activity.isin(STILL)]
    h = lambda d: max(d.duration_s.sum() / 3600, 1e-9)  # noqa: E731
    s = dict(falls=int((f.n_alarms > 0).sum()), fall_takes=int(len(f)),
             lookalike=int((lk.n_alarms > 0).sum()), lookalike_takes=int(len(lk)),
             walk_alarms=int(wk.n_alarms.sum()), walk_h=round(float(h(wk)), 4),
             walk_per_h=float(wk.n_alarms.sum() / h(wk)) if len(wk) else 0.0,
             still_alarms=int(sl.n_alarms.sum()), still_h=round(float(h(sl)), 4),
             still_per_h=float(sl.n_alarms.sum() / h(sl)) if len(sl) else 0.0,
             latency_median_s=float(np.nanmedian(R["latency_s"])) if "latency_s" in R and R["latency_s"].notna().any() else np.nan)
    return s, R


def select(st, p, walk_limit=BASE["walk_per_h"]):
    """Constrained choice of (theta, k, n) on the given (inner) predictions."""
    cands = []
    for th in THETAS:
        for k, n in RULES:
            s, _ = evaluate_takes(st, p, th, k, n)
            ok = (s["lookalike"] <= MAX_LOOKALIKE_SHARE * s["lookalike_takes"] + 1e-9) and s["walk_per_h"] <= walk_limit + 1e-9
            cands.append(dict(theta=float(th), k=k, n=n, ok=ok, fall_share=s["falls"] / max(s["fall_takes"], 1),
                              lookalike=s["lookalike"], walk_per_h=s["walk_per_h"], **{f"inner_{a}": b for a, b in s.items()}))
    feas = [c for c in cands if c["ok"]]
    if feas:
        best = sorted(feas, key=lambda c: (-c["fall_share"], c["lookalike"], c["walk_per_h"], -c["theta"]))[0]
        best["fallback"] = False
    else:
        best = sorted(cands, key=lambda c: (c["lookalike"], -c["theta"]))[0]
        best["fallback"] = True
    return best, cands


def fit_model(X, y, groups, params):
    base = Pipeline([("sc", StandardScaler()), ("m", SVC(kernel="rbf", class_weight="balanced", **params))])
    cv = list(LeaveOneGroupOut().split(X, y, groups)) if len(set(groups)) > 2 else 3
    return CalibratedClassifierCV(base, method="sigmoid", cv=cv, ensemble=False).fit(X, y)


def choose_params(X, y, groups):
    cv = list(GroupKFold(3).split(X, y, groups))
    best, bs = None, -1
    for prm in GRID:
        sc = []
        for tr, va in cv:
            m = Pipeline([("sc", StandardScaler()), ("m", SVC(kernel="rbf", class_weight="balanced", **prm))]).fit(X[tr], y[tr])
            sc.append(f1_score(y[va], m.predict(X[va]), pos_label="fall", zero_division=0))
        if np.mean(sc) > bs:
            best, bs = prm, float(np.mean(sc))
    return best, bs


def load():
    cols = ev.feature_set("dynamic")
    df = pd.read_csv(ROOT / "data" / "features" / f"features_{TAG}.csv")
    m, y5 = ev.task_view(df, "events")
    y = np.where(y5 == "fall", "fall", "rest")
    folds = ev.assign_folds(df)[m]
    X = df.loc[m, cols].to_numpy(np.float64)
    st = pd.read_csv(ROOT / "data" / "features" / f"stream_{TAG}.csv")
    st["fold"] = ev.assign_folds(st)
    st["_i"] = np.arange(len(st))
    Xs = np.nan_to_num(st[cols].to_numpy(np.float64))                 # gate-failing rows are never voted on
    on = pd.read_csv(ROOT / "data" / "processed" / "onsets.csv").set_index("session_id")
    return X, y, folds, st, Xs, on


def proba_fall(model, X):
    return model.predict_proba(X)[:, list(model.classes_).index("fall")]


def run_fold(T, X, y, folds, st, Xs, on):
    path = OUT / f"fold_{T}.json"
    if path.exists():
        return json.loads(path.read_text())
    t0 = time.time()
    trs = [s for s in ev.SUBJECTS if s != T]
    tr = folds != T
    params, inner_f1 = choose_params(X[tr], y[tr], folds[tr])
    # inner LOSO stream predictions on the training subjects
    p_inner = np.full(len(st), np.nan)
    for U in trs:
        m = fit_model(X[tr & (folds != U)], y[tr & (folds != U)], folds[tr & (folds != U)], params)
        rows = st["fold"].to_numpy() == U
        p_inner[rows] = proba_fall(m, Xs[rows])
    inner = st[st["fold"].isin(trs)]
    chosen, cands = select(inner, p_inner)
    # outer model on all training subjects, applied unchanged to T
    m = fit_model(X[tr], y[tr], folds[tr], params)
    rows = st["fold"].to_numpy() == T
    p_test = np.full(len(st), np.nan)
    p_test[rows] = proba_fall(m, Xs[rows])
    test_s, test_R = evaluate_takes(st[rows], p_test, chosen["theta"], chosen["k"], chosen["n"], on)
    pd.DataFrame(dict(session_id=st.loc[rows, "session_id"], t_end=st.loc[rows, "t_end"],
                      gate_ok=st.loc[rows, "gate_ok"], p_fall=p_test[rows])).to_csv(OUT / f"fold_{T}_stream.csv", index=False)
    test_R.to_csv(OUT / f"fold_{T}_takes.csv", index=False)
    res = dict(test_subject=T, params=params, inner_fall_f1=inner_f1, chosen=chosen, test=test_s,
               n_candidates_feasible=int(sum(c["ok"] for c in cands)), wall_s=round(time.time() - t0, 1))
    tmp = path.with_suffix(".json.partial")
    tmp.write_text(json.dumps(res, indent=1, default=float))
    tmp.rename(path)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    X, y, folds, st, Xs, on = load()
    if a.final:
        p = np.full(len(st), np.nan)
        for T in ev.SUBJECTS:
            d = pd.read_csv(OUT / f"fold_{T}_stream.csv")
            rows = st["fold"].to_numpy() == T
            assert (d["session_id"].to_numpy() == st.loc[rows, "session_id"].to_numpy()).all()
            p[rows] = d["p_fall"].to_numpy()
        chosen, cands = select(st, p)
        out = dict(note="selection on all six subjects' outer-LOSO stream predictions (each scored by a model that never saw it)",
                   chosen=chosen, n_feasible=int(sum(c["ok"] for c in cands)))
        (OUT / "final_settings.json").write_text(json.dumps(out, indent=1, default=float))
        print(json.dumps(out["chosen"], indent=1, default=float))
        return
    res = {}
    for T in ev.SUBJECTS:
        r = run_fold(T, X, y, folds, st, Xs, on)
        res[T] = r
        c, s = r["chosen"], r["test"]
        print(f"fold {T}: params {r['params']} theta {c['theta']} rule {c['k']}-of-{c['n']}"
              f"{' (fallback)' if c['fallback'] else ''} | test falls {s['falls']}/{s['fall_takes']}, look-alike {s['lookalike']}/{s['lookalike_takes']}, "
              f"walk alarms {s['walk_alarms']}, still alarms {s['still_alarms']}  ({r['wall_s']} s)", flush=True)
    tot = lambda k: sum(r["test"][k] for r in res.values())  # noqa: E731
    lat = pd.concat([pd.read_csv(OUT / f"fold_{T}_takes.csv") for T in ev.SUBJECTS])
    summ = dict(new=dict(falls=tot("falls"), fall_takes=tot("fall_takes"), lookalike=tot("lookalike"),
                         lookalike_takes=tot("lookalike_takes"), walk_alarms=tot("walk_alarms"),
                         walk_per_h=tot("walk_alarms") / sum(r["test"]["walk_h"] for r in res.values()),
                         still_alarms=tot("still_alarms"),
                         still_per_h=tot("still_alarms") / sum(r["test"]["still_h"] for r in res.values()),
                         latency_median_s=float(lat["latency_s"].median()) if "latency_s" in lat else None,
                         per_fold={T: dict(falls=f"{r['test']['falls']}/{r['test']['fall_takes']}", lookalike=r["test"]["lookalike"],
                                           walk_alarms=r["test"]["walk_alarms"], theta=r["chosen"]["theta"],
                                           rule=f"{r['chosen']['k']}-of-{r['chosen']['n']}", fallback=r["chosen"]["fallback"])
                                   for T, r in res.items()}),
                current=BASE)
    n = summ["new"]
    summ["adopt"] = bool(n["falls"] > BASE["falls"] and n["lookalike"] <= BASE["lookalike"] and n["walk_per_h"] <= BASE["walk_per_h"] + 1e-9)
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
