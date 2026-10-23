# STATUS — 2026-10-23 ~05:45 IST · Phase 4 closed (Gate 4 decided) · Phase 5 starting

## Phase 4 (closed; details `results/REPORT.md`, decisions D-046 … D-052)
- Final models (D-050): events SVM-RBF, state extra trees, presence logistic regression; 4 s windows; dynamic-only f2. The two departures from the selection rule are recorded; the rule's picks stay in REPORT.
- Fall-alarm experiment (D-051, ~2 min under systemd-inhibit): calibrated binary SVM with settings chosen from inner LOSO → 21/42 falls vs 18/42, look-alike 8/109 vs 9/109, walking 30.3 vs 45.4 per hour, still 6.4 vs 3.2 per hour → **adopted**. Final alarm θ 0.5, 2-of-3, 10 s cooldown.
- Final models trained on all six subjects (`results/phase4/train_final.log`), Format 3 in `models/` (not committed; `model_meta.json` describes them), `models/env_baseline.json`.
- Predictor p2 (D-052): `predict(X, rssi, P)`; ≈ 125 ms per window on this laptop.
- Tests: `results/audit/pytest_phase4.log`.

## Open problems
1. Fall detection is limited (≈ half the falls; all falls at spot M), presence of still people is weak, and recognition depends on position (REPORT §5). These are limitations, not bugs.
2. `app/engine.py` and `app/live_app.py` are still v1 → Phase 5.

## Next step
Phase 5: engine v2 + replay demo + live/offline consistency test, empty-room environment check, dashboard. Built and tested with replay first; I ask before anything that needs the boards. Stop at Gate 5.
