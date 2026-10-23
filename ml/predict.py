"""Model interface (Format 3), PREDICTOR_VERSION "p2". The live app only talks to this class.

    from ml.predict import Predictor
    p = Predictor("models")                    # models/presence, models/state, models/events [, models/fall_alarm]
    out = p.predict(X, rssi, P)                # one window: X, P [2, T, 114] (preprocess v2), rssi [2, T]
    # {"label": "sit", "confidence": 0.71, "probs": {"empty": .., "sit": .., ...}, "motion": 0.03,
    #  "fall_prob": 0.04, "uncertain": False, "presence_prob": 0.93, "state": "sit", "state_probs": {...},
    #  "event": "none", "event_probs": {...}}

v1 -> p2 (2026-10-23, D-052): f2 features need the sanitised phase P, so predict() takes P as a third
argument; the v1 output keys are unchanged, new keys are added. Hierarchy: presence (empty vs occupied)
-> state (sit/stand/walk/lie) if occupied; events (fall/sit_down/stand_up/bend_pick/none) on every window.
fall_prob comes from models/fall_alarm when present (D-051), else from the event model's P(fall).
The alarm rule itself (k of the last n windows >= theta, cooldown) lives in the engine; its settings are
in self.alarm. Models trained with another preprocessing/feature version or window length are refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml import features as fx  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

PREDICTOR_VERSION = "p2"
CONF_MIN = 0.5           # below this the answer is reported as uncertain


class Predictor:
    def __init__(self, models_dir="models"):
        import joblib
        self.dir = Path(models_dir)
        self.models, self.meta = {}, {}
        for task in ("presence", "state", "events", "fall_alarm"):
            d = self.dir / task
            if not (d / "model.joblib").exists():
                if task == "fall_alarm":
                    continue
                raise FileNotFoundError(f"no {task} model in {d} - run python3 -m ml.train_final")
            meta = json.loads((d / "model_meta.json").read_text())
            for key, want in (("preproc_version", pp.PREPROC_VERSION), ("features_version", fx.FEATURES_VERSION)):
                if meta.get(key) != want:
                    raise RuntimeError(f"{task}: trained with {key} {meta.get(key)}, code is {want}; retrain")
            self.models[task], self.meta[task] = joblib.load(d / "model.joblib"), meta
        self.window_s = float(self.meta["events"]["window_s"])
        if any(float(m["window_s"]) != self.window_s for m in self.meta.values()):
            raise RuntimeError("models trained on different window lengths")
        self.T = int(round(self.window_s * pp.FS))
        names = fx.feature_names()
        self.cols = {t: [names.index(c) for c in m["feature_names"]] for t, m in self.meta.items()}
        if "fall_alarm" in self.models:
            self.alarm = dict(self.meta["fall_alarm"]["alarm"], source="fall_alarm")
        else:
            a = self.meta["events"]["alarm"]
            self.alarm = dict(theta=a["theta"], k=a["k"], n=a["n"], cooldown_s=a["cooldown_s"], source="events")
        self.synthetic = any(bool(m.get("synthetic")) for m in self.meta.values())

    def _proba(self, task, f):
        m = self.models[task]
        p = m.predict_proba(f[:, self.cols[task]])[0]
        return {str(c): float(v) for c, v in zip(m.classes_, p)}

    def predict(self, X: np.ndarray, rssi: np.ndarray, P: np.ndarray) -> dict:
        if P is None:
            raise ValueError("Predictor p2 needs the sanitised phase P (preprocess v2 window['P'])")
        if X.shape[1] != self.T:
            raise ValueError(f"window has {X.shape[1]} samples, models expect {self.T} ({self.window_s} s)")
        f = fx.window_features(X, P, rssi)[None, :].astype(np.float64)
        pres = self._proba("presence", f)
        p_occ = pres.get("occupied", 0.0)
        st = self._proba("state", f)
        ev = self._proba("events", f)
        probs = {"empty": 1.0 - p_occ, **{k: p_occ * v for k, v in st.items()}}
        label = max(probs, key=probs.get)
        fall = self._proba("fall_alarm", f).get("fall", 0.0) if "fall_alarm" in self.models else ev.get("fall", 0.0)
        out = dict(label=label, confidence=float(probs[label]), probs=probs, motion=fx.motion_level(X),
                   fall_prob=float(fall), presence_prob=float(p_occ), state=max(st, key=st.get), state_probs=st,
                   event=max(ev, key=ev.get), event_probs=ev)
        out["uncertain"] = out["confidence"] < CONF_MIN
        return out
