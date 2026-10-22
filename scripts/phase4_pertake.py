#!/usr/bin/env python3
"""Per-take evaluation of the live fall decision chain (D-025; Gate 2 note 3).

    python3 scripts/phase4_pertake.py --model rf --featset dynamic --win 3

For each LOSO fold: the event classifier (task "events", nested search as in Track A) is trained on
the training subjects' labelled windows; it then scores every gate-passing stream window of the test
subject's takes in time order (data/features/stream_<len>s.csv, hop 0.5 s, as live). The live rule
(app/engine.py, CONTRACTS): alarm when >= 2 of the last 3 windows have P(fall) >= THETA (0.6), with a
10 s cooldown; gate-failing windows give no vote. No motion gate (D-025: dropped rather than fitted).
This runs over ALL takes, independent of the onset detector, so undetected-onset falls still count.
Output: results/phase4/pertake/<model>__<featset>__<len>s.json and .csv (one row per take)
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import evaluate as ev  # noqa: E402
from ml import features as fx  # noqa: E402
from ml import models_classical as mc  # noqa: E402

THETA = 0.6
COOLDOWN_S = 10.0
LOOKALIKE = ("sit_down", "stand_up", "bend_pick")


def alarms(t_end, p_fall, ok, theta=THETA):
    """Replay of the engine rule on one take: returns list of alarm times (window end, s)."""
    votes = collections.deque(maxlen=3)
    last = -1e9
    out = []
    for t, p, g in zip(t_end, p_fall, ok):
        if not g:
            continue                                  # degraded window: no prediction, no vote
        votes.append(p >= theta)
        if sum(votes) >= 2 and t - last > COOLDOWN_S:
            out.append(float(t))
            last = t
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="rf")
    ap.add_argument("--featset", default="dynamic")
    ap.add_argument("--win", default="3")
    a = ap.parse_args()
    tag = f"{a.win}s"
    df = pd.read_csv(ROOT / "data" / "features" / f"features_{tag}.csv")
    st = pd.read_csv(ROOT / "data" / "features" / f"stream_{tag}.csv")
    on = pd.read_csv(ROOT / "data" / "processed" / "onsets.csv").set_index("session_id")
    cols = ev.feature_set(a.featset)
    m, y = ev.task_view(df, "events")
    folds = ev.assign_folds(df)[m]
    X = df.loc[m, cols].to_numpy(np.float64)
    # stream rows -> fold ids (empty takes dealt as in assign_folds)
    st_fold = ev.assign_folds(st.rename(columns={}))
    st["fold"] = st_fold
    p_fall = np.full(len(st), np.nan)
    make = mc.make_search_factory(a.model)
    for test in ev.SUBJECTS:
        tr = folds != test
        s = make(folds[tr])
        s.fit(X[tr], y[tr])
        te = (st["fold"].to_numpy() == test) & st["gate_ok"].to_numpy(bool)
        if te.any():
            pr = s.predict_proba(st.loc[te, cols].to_numpy(np.float64))
            p_fall[te] = pr[:, list(s.classes_).index("fall")]
        print(f"fold {test}: trained on {tr.sum()} windows, scored {te.sum()} stream windows", flush=True)
    rows = []
    for sid, g in st.groupby("session_id", sort=True):
        g = g.sort_values("t_end")
        al = alarms(g["t_end"].to_numpy(), p_fall[g.index], g["gate_ok"].to_numpy(bool))
        act = g["activity"].iloc[0]
        r = dict(session_id=sid, subject=g["subject"].iloc[0], fold=g["fold"].iloc[0], activity=act,
                 kind=g["kind"].iloc[0], position=g["position"].iloc[0], duration_s=float(g["t_end"].max()),
                 windows=len(g), gate_ok=int(g["gate_ok"].sum()), n_alarms=len(al),
                 first_alarm_s=al[0] if al else "", max_p_fall=float(np.nanmax(p_fall[g.index])) if g["gate_ok"].any() else "")
        if sid in on.index:
            o = on.loc[sid]
            r.update(onset_detected=bool(o["detected"]), onset_s=o["onset_s"], usable_for_training=bool(o["usable_for_event_training"]))
            if al and bool(o["detected"]):
                r["alarm_latency_after_onset_s"] = round(al[0] - float(o["onset_s"]), 2)
        rows.append(r)
    R = pd.DataFrame(rows)
    falls = R[R.activity == "fall"]
    look = R[R.activity.isin(LOOKALIKE)]
    other = R[R.kind == "state"]
    res = dict(model=a.model, featset=a.featset, window=tag, theta=THETA, cooldown_s=COOLDOWN_S, motion_gate=None,
               falls_total=int(len(falls)), falls_detected=int((falls.n_alarms > 0).sum()),
               falls_with_detected_onset=int(falls.onset_detected.sum()),
               falls_detected_among_onset_detected=int(((falls.n_alarms > 0) & falls.onset_detected).sum()),
               falls_detected_among_onset_missed=int(((falls.n_alarms > 0) & ~falls.onset_detected).sum()),
               alarm_latency_after_onset_s_median=float(pd.to_numeric(falls.get("alarm_latency_after_onset_s"), errors="coerce").median()),
               lookalike_takes=int(len(look)), lookalike_takes_with_alarm=int((look.n_alarms > 0).sum()),
               lookalike_by_activity={k: dict(takes=int(len(v)), with_alarm=int((v.n_alarms > 0).sum()))
                                      for k, v in look.groupby("activity")},
               state_takes=int(len(other)), state_takes_with_alarm=int((other.n_alarms > 0).sum()),
               state_alarms_per_hour=float(other.n_alarms.sum() / max(other.duration_s.sum() / 3600, 1e-9)),
               state_alarms_by_activity={k: int(v.n_alarms.sum()) for k, v in other.groupby("activity")},
               per_fold={f: dict(falls=int((falls.fold == f).sum()), detected=int(((falls.fold == f) & (falls.n_alarms > 0)).sum()),
                                 lookalike_alarm_takes=int(((look.fold == f) & (look.n_alarms > 0)).sum()))
                         for f in ev.SUBJECTS},
               features_version=fx.FEATURES_VERSION)
    sweep = {}
    for th in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        det = fa = 0
        for sid, g in st.groupby("session_id"):
            g = g.sort_values("t_end")
            al = alarms(g["t_end"].to_numpy(), p_fall[g.index], g["gate_ok"].to_numpy(bool), th)
            act = g["activity"].iloc[0]
            det += act == "fall" and bool(al)
            fa += act in LOOKALIKE and bool(al)
        sweep[str(th)] = dict(falls_detected=int(det), lookalike_takes_with_alarm=int(fa))
    res["theta_sweep_analysis_only"] = sweep
    out = ROOT / "results" / "phase4" / "pertake"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.model}__{a.featset}__{tag}.json").write_text(json.dumps(res, indent=1))
    R.to_csv(out / f"{a.model}__{a.featset}__{tag}.csv", index=False)
    print(json.dumps({k: v for k, v in res.items() if k not in ("per_fold", "theta_sweep_analysis_only")}, indent=1))
    print("theta sweep (analysis only; 0.6 fixed a priori):", sweep)


if __name__ == "__main__":
    main()
