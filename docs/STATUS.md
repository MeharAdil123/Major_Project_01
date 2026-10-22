# STATUS — 2026-10-23 ~03:50 IST · Phase 4 runs complete · **waiting at Gate 4**

## Phase 4: what was done (branch `cc/phase4`; laptop run, D-045)
- Overnight chain `csi-phase4` (systemd user unit under `systemd-inhibit`) finished 03:27; every step exit 0 (`results/phase4/overnight.log`, `step_*.log`).
- Track A: 8 classical models × 3 tasks at 3 s (dynamic + all) and at 2/4 s (dynamic), nested LOSO (64 runs, `results/phase4/track_a/`).
- Window length **4 s** by the pre-set rule (D-046).
- Track B: MiniRocket (NumPy re-implementation, D-043) × 3 tasks.
- Track C: 10 deep models × 3 seeds on events and state (they overfit, D-048).
- Ablations (receivers, amplitude vs phase, static vs dynamic, feature groups removed one at a time, gate 15 %, state-takes-only), position check, per-take live chain (SVM-RBF), latency.
- Selection rule applied (D-047). **Full results: `results/REPORT.md`.**

## Key results (macro-F1, mean ± std over 6 LOSO folds, 4 s)
- Events: MiniRocket 0.572 ± 0.062 · SVM-RBF 0.539 ± 0.054 · XGBoost 0.523 · best deep 0.344.
- State: extra trees 0.572 ± 0.115 · MiniRocket 0.568.
- Presence: MiniRocket 0.729 ± 0.178 (unstable) · logistic regression 0.698 ± 0.065.
- Falls per take (SVM-RBF, live chain): **18 of 42** detected, 9 of 109 look-alike takes alarmed, 7 alarms in 0.45 h of state takes.
- Position dependence: sit_down recall 0.76 at A vs 0.25 at B.

## Open problems / Gate 4 decisions
1. Events: MiniRocket (rule) needs a probability head and a per-take evaluation; SVM-RBF is already evaluated per take.
2. Presence: MiniRocket (rule) vs logistic regression (stable).
3. State: extra trees.
4. Final retraining and Format 3 models only after your choice; `ml/predict.py` and `app/engine.py` are still on v1.
5. Fall detection is weak (18 of 42 falls), and all falls are at one spot; limitations in the report.

## Next step
Your decision at Gate 4, then retrain on all subjects, Format 3 models, REPORT final, then Phase 5.
