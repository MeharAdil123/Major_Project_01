"""Environment check verdict (app/envcheck.py) on SYNTHETIC statistics."""
import numpy as np

from app import envcheck as ec
from ml import evaluate as ev
from ml import features as fx


def baseline():
    names = ev.feature_set("dynamic")
    return dict(dynamic=dict(names=names, mean=[0.0] * len(names), std=[1.0] * len(names),
                             p05=[-1.6] * len(names), p95=[1.6] * len(names)),
                profiles_db={"A": np.zeros((2, 114)).tolist(), "B": np.ones((2, 114)).tolist()},
                profile_rms_db_between_training_takes=dict(median=1.0, max=1.0))


def feats(shift, n=10, seed=0):
    rng = np.random.default_rng(seed)
    all_names = fx.feature_names()
    F = rng.normal(0, 0.3, (n, len(all_names)))
    dyn = [all_names.index(c) for c in ev.feature_set("dynamic")]
    F[:, dyn] += shift
    return list(F)


def outs(p_occ, p_fall=0.0, n=10):
    return [dict(presence_prob=p_occ, fall_prob=p_fall)] * n


def test_empty_like_baseline_passes():
    r = ec.evaluate(feats(0.0), outs(0.1), [np.zeros((2, 114))] * 10, baseline(), theta=0.5)
    assert r["verdict"] == "ok" and r["nearest_training_take"] == "A" and r["profile_db_vs_nearest"] == [0.0, 0.0]


def test_person_present_fails_on_presence():
    r = ec.evaluate(feats(0.0), outs(0.9), [np.zeros((2, 114))] * 10, baseline(), theta=0.5)
    assert r["verdict"] != "ok" and any("occupied" in x for x in r["reasons"])


def test_shifted_dynamics_fail_and_fall_alarms_fail():
    r = ec.evaluate(feats(3.0), outs(0.1), [np.zeros((2, 114))] * 10, baseline(), theta=0.5)
    assert any("shifted" in x for x in r["reasons"]) and any("outside" in x for x in r["reasons"])
    r = ec.evaluate(feats(0.0), outs(0.1, p_fall=0.9), [np.zeros((2, 114))] * 10, baseline(), theta=0.5)
    assert any("fall probability" in x for x in r["reasons"])


def test_static_profile_difference_is_informational_only():
    r = ec.evaluate(feats(0.0), outs(0.1), [np.full((2, 114), 8.0)] * 10, baseline(), theta=0.5)
    assert r["verdict"] == "ok" and r["profile_db_vs_nearest"][0] == 7.0
