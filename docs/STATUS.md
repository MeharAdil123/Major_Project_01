# STATUS — 2026-10-22 ~20:55 IST · Phase 3 done (Gate 3 passed without stop, D-044) · Phase 4 running on this laptop (D-045)

## Phase 3: what was done (branch `cc/phase3`)
- **Onset o2** (Gate 2 notes): the end may run to cue + 6 s; detections < 0.6 s are flagged (7). Updated overlays: `results/signal/onset_*.png`; log `results/signal/onset_validation_o2.log`. 92 % of event takes have their onset in [cue, cue+4 s] and end ≤ cue+6 s.
- **D-023 gate diagnosis** (`results/dataset/gate_diag.log`): no bug. Gap counts agree, there are no duplicates or seq wraps, and alignment is clean. The three zero-window takes have 18–22 % scattered loss on one RX. Rejected share at 10 / 15 / 20 % missing: 21.5 / 9.8 / 3.9 % (3 s windows). At 10 %, S1 loses 67 % of its windows. **Gate = 20 % + 100 ms** (D-039); 15 % is the sensitivity check.
- **Preprocess v2** (`pipeline/preprocess.py`): anti-alias decimation, sanitised-phase channel, window margins (live = offline, tested), window length and gate as parameters.
- **Labels** (`pipeline/labels.py`, D-040), **features f2** (`ml/features.py`, `docs/FEATURES.md`, D-041: 83 features, 33 static / 50 dynamic), **Format 2 v2** (D-042, `docs/CONTRACTS.md`).
- **Datasets** (`results/dataset/build_{2,3,4}s.log`, summary `results/dataset/summary.log`):

  | | 2 s | 3 s | 4 s |
  | --- | --- | --- | --- |
  | kept / candidates | 2972 / 3915 | 2602 / 3562 | 2401 / 3209 |
  | gate-rejected | 4.0 % | 3.9 % | 3.6 % |
  | dropped as transition | 20.1 % | 23.0 % | 21.6 % |
  | fall / sit_down / stand_up / bend_pick windows | 179 / 178 / 193 / 85 | 226 / 237 / 246 / 98 | 279 / 301 / 312 / 113 |

  Gate rejection per subject (3 s): S1 12.3 %, S2 8.3 %, S3 5.4 %, S4–S6 ≤ 0.5 %. Falls with a detected onset: **41 of 42**; usable for event training: fall 36, sit_down 39, stand_up 42, bend_pick 15.
- Leakage check (3 s): the within-class correlation of missing share with dynamic features is low (median |ρ| 0.08–0.23). The exception is bend_pick, where it is up to 0.76 with a *positive* sign. That is body position (near RX2), not interpolation smoothing.
- Feature distributions: `results/dataset/feature_distributions_3s.png`.
- Tests: `results/audit/pytest_phase3.log`.

## Phase 4 (in progress)
Code: `ml/evaluate.py` (folds, tasks, feature sets, nested LOSO, metrics), `ml/models_classical.py` (8 models), `ml/minirocket.py` (NumPy MiniRocket, D-043), `ml/deep.py` (10 PyTorch models), runners `scripts/phase4_track_{a,b,c}.py`, `scripts/build_stream.py`, `scripts/phase4_pertake.py`.
Run order: Track A at 3 s (all models × 3 tasks × {dynamic, all}) → Track A at 2/4 s (dynamic) → best window → Track B + C at that window → ablations → per-take live chain → REPORT → **Gate 4**.

## Open problems
1. `ml/predict.py`, `app/engine.py` and `scripts/pipeline.sh synth` still use the v1 interface; rewritten in Phase 4.4 / 5.
2. 4 s windows leave almost no pre-action windows (the onset is ~4 s into a 10 s take).
3. bend_pick is the weakest class (98 windows at 3 s; 5 takes undetected).

## Machine and overnight run (D-045)
No Mac move; Phase 4 runs on this laptop. Since 2026-10-22 20:50 the chain `scripts/phase4_overnight.sh` runs as the user service **`csi-phase4`** under `systemd-inhibit` (sleep, idle and lid-close blocked). It is independent of the Claude Code session but needs the user to stay logged in (linger is off).
- Progress: `results/phase4/overnight.log` (START/END + exit code per step); step output in `results/phase4/step_<name>.log`.
- Status: `systemctl --user status csi-phase4` · stop: `systemctl --user stop csi-phase4`.
- Resume after any stop (each step skips finished result files; per-(model, seed) files for the deep track):
  `systemd-run --user --unit=csi-phase4 --working-directory=$HOME/WiFi_CSI_Final/wifi-csi-har systemd-inhibit --what=sleep:idle:handle-lid-switch --who=wifi-csi-har --why="Phase 4 runs" --mode=block bash scripts/phase4_overnight.sh`
- Steps: Track A 3 s (8 models × 3 tasks × dynamic/all) → Track A 2 s and 4 s (dynamic) → stream features → window choice (`results/phase4/chosen_window.json`, rule fixed in advance) → per-take live chain → event ablations → MiniRocket ×3 tasks → deep models (events, 10 × 3 seeds) → state/presence ablations → deep models (state).
- An incomplete `data/features/stream_3s.csv` from the earlier, killed job was renamed `stream_3s.csv.incomplete_killed_2026-10-22` (not deleted).

## Next step
Phase 4 runs in the background; stop at Gate 4 with the comparison table, ablations and the chosen model.
