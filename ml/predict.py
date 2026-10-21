"""Model interface (Format 3). The live app only talks to this class.

    from ml.predict import Predictor
    p = Predictor("models")                        # loads models/state_rf and (if present) models/event_rf
    out = p.predict(X, rssi)                       # X [2,200,114] gain-normalised, rssi [2,200]
    # -> {"label": "sit", "confidence": 0.82, "probs": {...}, "motion": 0.013,
    #     "fall_prob": 0.04, "uncertain": False}

Any model (random forest, CNN, ...) can sit behind this class as long as predict() keeps
this input/output. A model trained with a different preprocessing version is refused.
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

CONF_MIN = 0.5           # below this the answer is reported as uncertain


class Predictor:
    def __init__(self, models_dir="models"):
        import joblib
        self.dir = Path(models_dir)
        self.state, self.state_meta = self._load(joblib, "state_rf")
        if self.state is None:
            raise FileNotFoundError(f"no state model in {self.dir / 'state_rf'} - run python3 -m ml.train")
        self.event, self.event_meta = self._load(joblib, "event_rf")
        self.motion_thr = float(self.event_meta.get("live_motion_threshold", np.inf)) if self.event else np.inf
        self.synthetic = bool(self.state_meta.get("synthetic", False))

    def _load(self, joblib, name):
        d = self.dir / name
        if not (d / "model.joblib").exists():
            return None, {}
        meta = json.loads((d / "model_meta.json").read_text())
        if meta.get("preproc_version") != pp.PREPROC_VERSION:
            raise RuntimeError(f"{name}: trained with preprocessing {meta.get('preproc_version')}, "
                               f"code is {pp.PREPROC_VERSION}; retrain")
        if meta.get("features_version") != fx.FEATURES_VERSION:
            raise RuntimeError(f"{name}: features {meta.get('features_version')} != {fx.FEATURES_VERSION}; retrain")
        return joblib.load(d / "model.joblib"), meta

    def predict(self, X: np.ndarray, rssi: np.ndarray) -> dict:
        f = fx.window_features(X, rssi)[None, :]
        p = self.state.predict_proba(f)[0]
        cls = list(self.state.classes_)
        k = int(np.argmax(p))
        out = dict(label=cls[k], confidence=float(p[k]), probs={c: float(v) for c, v in zip(cls, p)},
                   motion=fx.motion_level(X), fall_prob=0.0)
        out["uncertain"] = out["confidence"] < CONF_MIN
        if self.event is not None and out["motion"] >= self.motion_thr:
            pe = self.event.predict_proba(f)[0]
            out["fall_prob"] = float(pe[list(self.event.classes_).index("fall")])
        return out
