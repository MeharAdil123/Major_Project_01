"""Predictor p2 on a tiny SYNTHETIC Format 3 model set (no trained artefacts needed)."""
import json

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from ml import evaluate as ev
from ml import features as fx
from ml.predict import Predictor
from pipeline import preprocess as pp


def make_models(tmp_path, win_s=4.0, fall_alarm=True):
    cols = ev.feature_set("dynamic")
    rng = np.random.default_rng(0)
    F = rng.normal(size=(60, len(cols)))
    sets = {"presence": ["empty", "occupied"], "state": ["lie", "sit", "stand", "walk"],
            "events": ["bend_pick", "fall", "none", "sit_down", "stand_up"]}
    if fall_alarm:
        sets["fall_alarm"] = ["fall", "rest"]
    for task, classes in sets.items():
        y = np.array(classes * (60 // len(classes) + 1))[:60]
        m = LogisticRegression(max_iter=500).fit(F, y)
        d = tmp_path / task
        d.mkdir(parents=True)
        joblib.dump(m, d / "model.joblib")
        meta = dict(task=task, classes=classes, feature_names=cols, window_s=win_s, preproc_version=pp.PREPROC_VERSION,
                    features_version=fx.FEATURES_VERSION, synthetic=True)
        if task == "events":
            meta["alarm"] = dict(theta=0.6, k=2, n=3, cooldown_s=10.0)
        if task == "fall_alarm":
            meta["alarm"] = dict(theta=0.5, k=2, n=3, cooldown_s=10.0)
        (d / "model_meta.json").write_text(json.dumps(meta))
    return tmp_path


def window(T=400):
    rng = np.random.default_rng(1)
    X = (1 + 0.05 * rng.standard_normal((2, T, 114))).astype(np.float32)
    P = (0.1 * rng.standard_normal((2, T, 114))).astype(np.float32)
    return X, -40 + rng.standard_normal((2, T)).astype(np.float32), P


def test_output_keys_and_probabilities(tmp_path):
    p = Predictor(make_models(tmp_path))
    X, rssi, P = window()
    out = p.predict(X, rssi, P)
    for k in ("label", "confidence", "probs", "motion", "fall_prob", "uncertain"):      # v1 keys kept
        assert k in out
    assert abs(sum(out["probs"].values()) - 1) < 1e-6 and out["label"] in out["probs"]
    assert 0 <= out["fall_prob"] <= 1 and set(out["event_probs"]) == {"bend_pick", "fall", "none", "sit_down", "stand_up"}
    assert p.alarm["source"] == "fall_alarm" and p.alarm["theta"] == 0.5 and p.synthetic


def test_alarm_falls_back_to_event_model(tmp_path):
    p = Predictor(make_models(tmp_path, fall_alarm=False))
    assert p.alarm["source"] == "events" and p.alarm["theta"] == 0.6


def test_refuses_wrong_window_and_missing_phase(tmp_path):
    p = Predictor(make_models(tmp_path))
    X, rssi, P = window(300)
    with pytest.raises(ValueError):
        p.predict(X, rssi, P)
    X, rssi, P = window()
    with pytest.raises(ValueError):
        p.predict(X, rssi, None)


def test_refuses_other_feature_version(tmp_path):
    d = make_models(tmp_path)
    m = json.loads((d / "state" / "model_meta.json").read_text())
    m["features_version"] = "f1"
    (d / "state" / "model_meta.json").write_text(json.dumps(m))
    with pytest.raises(RuntimeError):
        Predictor(d)
