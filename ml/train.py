#!/usr/bin/env python3
"""Train + evaluate the baseline models (Format 2 -> Format 3). See docs/CONTRACTS.md.

    python3 -m ml.train                                   # data/processed -> models/, results/
    python3 -m ml.train --data data_synth/processed --models models_synth --results results_synth

Models
  state : empty / sit / stand / walk / lie          (random forest on ml/features.py)
  event : fall vs not_fall, trained on event windows (fall vs sit_down/stand_up/bend_pick)
          plus walking/standing windows as extra negatives
Evaluation (no leakage: whole takes and whole people are held out together)
  * leave-one-subject-out (LOSO): train on the others, test on the unseen person.
    'empty' takes have no person, so they are spread over the folds take by take.
  * the final model is then trained on all data and saved.
Outputs: models/<task>_rf/{model.joblib, model_meta.json}; results/<task>_*.json/png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml import features as fx  # noqa: E402


def load(path: Path):
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in d.files}


def groups_for(subject: np.ndarray, session: np.ndarray) -> np.ndarray:
    """Group id per window: the subject; subject-less takes (empty room) are dealt round-robin."""
    subj = sorted(set(subject.tolist()) - {"none"})
    if not subj:
        return session.copy()
    g = subject.copy().astype(object)
    empty_sessions = sorted(set(session[subject == "none"].tolist()))
    for k, s in enumerate(empty_sessions):
        g[session == s] = subj[k % len(subj)]
    return g.astype(str)


def make_model(seed=0):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced",
                                  n_jobs=-1, random_state=seed)


def evaluate(F, y, groups, classes, title, out_prefix: Path):
    from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
    pred = np.empty_like(y)
    proba = np.zeros((len(y), len(classes)))
    folds = sorted(set(groups.tolist()))
    per_fold = {}
    for g in folds:
        te = groups == g
        tr = ~te
        if len(set(y[tr].tolist())) < 2:
            continue
        m = make_model()
        m.fit(F[tr], y[tr])
        pred[te] = m.predict(F[te])
        p = m.predict_proba(F[te])
        for j, c in enumerate(m.classes_):
            proba[te, list(classes).index(c)] = p[:, j]
        per_fold[g] = dict(n=int(te.sum()), acc=round(float(accuracy_score(y[te], pred[te])), 4))
    rep = classification_report(y, pred, labels=list(classes), output_dict=True, zero_division=0)
    cm = confusion_matrix(y, pred, labels=list(classes))
    res = dict(title=title, scheme="leave-one-subject-out", folds=per_fold, n_windows=int(len(y)),
               accuracy=round(float(accuracy_score(y, pred)), 4),
               macro_f1=round(float(f1_score(y, pred, labels=list(classes), average="macro", zero_division=0)), 4),
               per_class={c: {k: round(float(v), 4) for k, v in rep[c].items()} for c in classes},
               confusion_matrix=dict(labels=list(classes), matrix=cm.tolist()))
    plot_cm(cm, classes, f"{title}\nLOSO accuracy {res['accuracy']:.3f}, macro-F1 {res['macro_f1']:.3f}",
            out_prefix.with_name(out_prefix.name + "_confusion.png"))
    return res, pred, proba


def plot_cm(cm, classes, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cmn = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(1.2 * len(classes) + 2.5, 1.1 * len(classes) + 2))
    ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, f"{cm[i, j]}\n{cmn[i, j]:.0%}", ha="center", va="center", fontsize=8,
                    color="white" if cmn[i, j] > 0.6 else "black")
    ax.set_xticks(range(len(classes)), classes, rotation=30)
    ax.set_yticks(range(len(classes)), classes)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def save_model(F, y, classes, task, data, models_dir: Path, extra: dict):
    import joblib
    m = make_model()
    m.fit(F, y)
    d = models_dir / f"{task}_rf"
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, d / "model.joblib")
    imp = sorted(zip(fx.feature_names(), m.feature_importances_.tolist()), key=lambda t: -t[1])[:15]
    meta = dict(task=task, model="RandomForestClassifier", classes=list(classes),
                features_version=fx.FEATURES_VERSION, preproc_version=str(data["preproc_version"]),
                synthetic=bool(data.get("synthetic", False)), n_train=int(len(y)),
                trained_at=time.strftime("%Y-%m-%d %H:%M:%S"), top_features=imp, **extra)
    (d / "model_meta.json").write_text(json.dumps(meta, indent=2))
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "processed")
    ap.add_argument("--models", type=Path, default=ROOT / "models")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    a = ap.parse_args()
    a.results.mkdir(parents=True, exist_ok=True)
    summary = {}

    st = load(a.data / "windows_state.npz")
    if bool(st.get("synthetic", False)):
        print("WARNING: SYNTHETIC data - numbers below only test the code")
    print(f"state windows: {st['X'].shape}")
    Fs = fx.batch_features(st["X"], st["rssi"])
    ys = st["y"].astype(str)
    classes = np.array(sorted(set(ys.tolist())))
    gs = groups_for(st["subject"].astype(str), st["session_id"].astype(str))
    res, pred, _ = evaluate(Fs, ys, gs, classes, "Activity (state) classifier", a.results / "state")
    # presence = empty vs anything else, derived from the same predictions
    if "empty" in classes:
        t_occ, p_occ = ys != "empty", pred != "empty"
        tp, tn = int((t_occ & p_occ).sum()), int((~t_occ & ~p_occ).sum())
        fp, fn = int((~t_occ & p_occ).sum()), int((t_occ & ~p_occ).sum())
        res["presence"] = dict(sensitivity=round(tp / max(tp + fn, 1), 4),
                               specificity=round(tn / max(tn + fp, 1), 4), tp=tp, tn=tn, fp=fp, fn=fn)
    res["synthetic"] = bool(st.get("synthetic", False))
    (a.results / "state_metrics.json").write_text(json.dumps(res, indent=2))
    d = save_model(Fs, ys, classes, "state", st, a.models, {"eval": {k: res[k] for k in ("accuracy", "macro_f1")}})
    summary["state"] = dict(accuracy=res["accuracy"], macro_f1=res["macro_f1"], presence=res.get("presence"),
                            model=str(d))
    print(f"state: LOSO accuracy {res['accuracy']}, macro-F1 {res['macro_f1']}, presence {res.get('presence')}")

    ev_path = a.data / "windows_event.npz"
    if ev_path.exists():
        ev = load(ev_path)
        Fe = fx.batch_features(ev["X"], ev["rssi"])
        ye = np.where(ev["y"].astype(str) == "fall", "fall", "not_fall")
        ge = ev["subject"].astype(str)
        # extra negatives: walking / standing windows (ordinary movement must not raise alarms)
        neg = np.isin(ys, ["walk", "stand", "sit"])
        rng = np.random.default_rng(0)
        pick = rng.choice(np.flatnonzero(neg), size=min(int(neg.sum()), 2 * len(ye)), replace=False) if neg.any() else []
        F2 = np.concatenate([Fe, Fs[pick]]) if len(pick) else Fe
        y2 = np.concatenate([ye, np.array(["not_fall"] * len(pick))])
        g2 = np.concatenate([ge, gs[pick]]) if len(pick) else ge
        ecls = np.array(["fall", "not_fall"])
        res_e, pred_e, proba_e = evaluate(F2, y2, g2, ecls, "Fall detector (fall vs not_fall)", a.results / "event")
        motion = np.array([fx.motion_level(x) for x in ev["X"]])
        thr = float(np.percentile(motion[ye == "fall"], 5)) if (ye == "fall").any() else 0.0
        res_e["live_motion_threshold"] = thr
        res_e["fall_sensitivity"] = res_e["per_class"]["fall"]["recall"]
        res_e["false_alarm_share_of_negatives"] = round(float(((pred_e == "fall") & (y2 == "not_fall")).sum()
                                                             / max((y2 == "not_fall").sum(), 1)), 4)
        res_e["note"] = "Simulated falls on a mattress by healthy volunteers; not clinical evidence."
        res_e["synthetic"] = bool(ev.get("synthetic", False))
        (a.results / "event_metrics.json").write_text(json.dumps(res_e, indent=2))
        d = save_model(F2, y2, ecls, "event", ev, a.models, {"live_motion_threshold": thr})
        summary["event"] = dict(fall_sensitivity=res_e["fall_sensitivity"],
                                false_alarm_share=res_e["false_alarm_share_of_negatives"], model=str(d))
        print(f"event: fall sensitivity {res_e['fall_sensitivity']}, "
              f"false-alarm share {res_e['false_alarm_share_of_negatives']}")
    (a.results / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"results in {a.results}, models in {a.models}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
