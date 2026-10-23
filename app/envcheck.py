"""Start-up environment check (PROMPT Phase 5.4): record ~60 s of EMPTY room, compare with the training
empty-room baseline (models/env_baseline.json, written by ml/train_final.py), and say whether predictions
can be trusted here.

Checks (thresholds are initial values, chosen before validation; results/phase5/envcheck.log):
  dyn_z         median over the dynamic features of |median(check) - mean(train empty)| / std(train empty) <= MAX_Z
  dyn_outside   share of dynamic features whose median lies outside the training empty [p05, p95]   <= MAX_OUT
  occupied      share of check windows the presence model calls occupied (room should be empty)      <= MAX_OCC
  fall          share of check windows with fall_prob >= the alarm threshold                         <= MAX_FALL
  profile_db    RMS dB difference of the static channel profile (per RX) to the nearest training empty take.
                Informational only: the models use dynamic features; a new room always differs here.
Verdict "ok" when the first four pass; otherwise "environment differs: predictions unreliable" + reasons.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ml import features as fx

MAX_Z, MAX_OUT, MAX_OCC, MAX_FALL = 2.0, 0.30, 0.20, 0.05
CHECK_S = 60.0
EVERY_N_STEPS = 4                       # one window every 2 s (features cost ~70 ms each)


def load_baseline(models_dir) -> dict | None:
    f = Path(models_dir) / "env_baseline.json"
    return json.loads(f.read_text()) if f.exists() else None


def profile_db(X: np.ndarray) -> np.ndarray:
    """Static profile of one window X [2, T, S]: mean gain-normalised amplitude per RX and carrier, dB."""
    return 20 * np.log10(np.maximum(np.asarray(X, np.float64).mean(axis=1), 1e-6))


def evaluate(feats: list, outs: list, profiles: list, baseline: dict, theta: float) -> dict:
    names = fx.feature_names()
    b = baseline["dynamic"]
    idx = [names.index(n) for n in b["names"]]
    F = np.array(feats)[:, idx]
    med = np.median(F, axis=0)
    z = np.abs(med - np.array(b["mean"])) / np.array(b["std"])
    outside = (med < np.array(b["p05"])) | (med > np.array(b["p95"]))
    occ = float(np.mean([o["presence_prob"] >= 0.5 for o in outs]))
    fall = float(np.mean([o["fall_prob"] >= theta for o in outs]))
    prof = np.mean(profiles, axis=0)                                     # [2, S]
    train = {k: np.array(v) for k, v in baseline["profiles_db"].items()}
    rms = {k: [float(np.sqrt(np.mean((prof[r] - v[r]) ** 2))) for r in (0, 1)] for k, v in train.items()}
    nearest = min(rms, key=lambda k: sum(rms[k]))
    res = dict(windows=len(outs), dyn_z=float(np.median(z)), dyn_outside=float(outside.mean()), occupied=occ, fall=fall,
               top_shifted=[b["names"][i] for i in np.argsort(-z)[:5]], profile_db_vs_nearest=rms[nearest],
               nearest_training_take=nearest,
               training_profile_spread_db=baseline["profile_rms_db_between_training_takes"])
    reasons = []
    if res["dyn_z"] > MAX_Z:
        reasons.append(f"dynamic features shifted (median |z| {res['dyn_z']:.1f} > {MAX_Z})")
    if res["dyn_outside"] > MAX_OUT:
        reasons.append(f"{100 * res['dyn_outside']:.0f} % of dynamic features outside the training empty range")
    if occ > MAX_OCC:
        reasons.append(f"presence model says 'occupied' in {100 * occ:.0f} % of empty-room windows")
    if fall > MAX_FALL:
        reasons.append(f"fall probability above the alarm threshold in {100 * fall:.0f} % of empty-room windows")
    res["verdict"] = "ok" if not reasons else "environment differs: predictions unreliable"
    res["reasons"] = reasons
    res["note"] = ("static channel shape differs from the nearest training empty room by "
                   f"{rms[nearest][0]:.1f} / {rms[nearest][1]:.1f} dB (RX1/RX2; training rooms differ by "
                   f"{baseline['profile_rms_db_between_training_takes']['median']:.1f} dB among themselves). "
                   "Informational: the models use dynamic features only.")
    return res


class EnvCheck:
    """Collects windows from the engine for CHECK_S seconds (room must be empty), then evaluates."""

    def __init__(self, baseline: dict, theta: float, seconds: float = CHECK_S, t_start: float = 0.0):
        self.baseline, self.theta, self.seconds, self.t_start = baseline, theta, seconds, t_start
        self.feats, self.outs, self.profiles, self.n_steps, self.result = [], [], [], 0, None

    def add(self, t: float, window: dict, out: dict):
        if self.result is not None:
            return
        self.n_steps += 1
        if (self.n_steps - 1) % EVERY_N_STEPS == 0:
            self.feats.append(fx.window_features(window["X"], window["P"], window["rssi"]))
            self.outs.append(out)
            self.profiles.append(profile_db(window["X"]))
        if t - self.t_start >= self.seconds and len(self.outs) >= 5:
            self.result = evaluate(self.feats, self.outs, self.profiles, self.baseline, self.theta)

    def status(self, t: float) -> dict:
        if self.result is not None:
            return dict(state="done", **self.result)
        return dict(state="recording", progress=min(1.0, (t - self.t_start) / self.seconds), windows=len(self.outs))
