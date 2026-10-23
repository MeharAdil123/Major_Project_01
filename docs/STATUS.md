# STATUS — 2026-10-23 ~06:05 IST · Phase 5 done with replay · **waiting at Gate 5**

## Phase 5: what was done (branch `cc/phase5`; decisions D-053 … D-056)
- **Engine v2** (`app/engine.py`): preprocess v2 → f2 → Predictor p2 → presence/state/event + adopted fall alarm (θ 0.5, 2-of-3, 10 s cooldown). No predictions on stale packets (audit E1 fixed: `degraded` / `no_signal`), serial reconnect by by-id, replay with the true label, prediction-only logs.
- **Live = offline:** bit-identical on 378 windows of 12 real takes (`results/phase5/consistency.log`) and as a unit test on a synthetic take.
- **Environment check** (`app/envcheck.py`, dashboard button): 7/7 empty takes pass (leave-one-take-out baseline), 7/8 takes with a person present flagged (`results/phase5/envcheck.log`). Calibration routine proposed, not built (`docs/analysis/calibration_proposal.md`).
- **Dashboard** (`app/live_app.py`, Streamlit): room status, activity, confidence, last event, fall banner, true label in replay, RX1/RX2 amplitude + sanitised-phase heatmaps, P(fall)/P(occupied)/motion and RSSI trends, packet rate/loss/age, event history, environment check, model info, "How it works", limitations, in-sample note for replay.
- **Screenshots:** `results/phase5/screenshots/01–05` (replay walk, heatmaps, fall alarm in the event history, environment check recording and verdict).
- **Speed:** BLAS limited to one thread → live step median 0.50 s, p90 0.64 s with the dashboard running (`results/phase5/step_timing.log`). Feature extraction caches the per-RX PCA (identical output).
- `scripts/pipeline.sh` updated (audit, dataset, phase4, train, consistency, test, replay, demo).
- Tests: `results/audit/pytest_phase5.log`.

## Not done yet (needs your go and the boards)
- **Live test with the boards** (`scripts/pipeline.sh demo`): not run. Per D-032, laptop Wi-Fi and Bluetooth must be off. The engine opens RX1 (native USB) and RX2 (CH343, 2 Mbaud) by their by-id names; the TX serial port is not opened (opening it resets the TX). Suggested live checks: health panel (rates ≈ 195/s), unplug/replug RX2 → reconnect, the environment check in the empty demo room, then a few sit/stand/walk and look-alike movements.

## Open problems
1. Fall detection catches about half of the falls (LOSO); all falls were at one spot; a still person can look like an empty room (REPORT §2, §7; envcheck miss on a standing take).
2. Replay shows in-sample predictions (D-056).
3. Phase 6 archive candidates (moves need your approval): `ml/train.py` (v1 trainer, superseded), `~/WiFi_CSI_Final/transfer/`, `docs/setup/MIGRATE_TO_MAC.md`, `data/features/stream_3s.csv.incomplete_killed_2026-10-22`, plus the moves approved at Gate 0.

## Next step
Your Gate 5 decision: go ahead with the live board test (you set up the boards with laptop Wi-Fi/Bluetooth off), or move to Phase 6.
