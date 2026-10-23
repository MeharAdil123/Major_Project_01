# STATUS — 2026-10-23 ~11:20 IST · Phase 5 · Option A round 2 done, RX2 still near motion-blind · Gate 5 open

## ▶ Prompt for the next session
> Read CLAUDE.md, docs/STATUS.md, results/phase5/live_library/TEST_CONDITIONS.md (sections "Option A, round 1/2") and docs/context/PROJECT_CONTEXT.md. We are at Gate 5. RX2 was re-seated/re-aimed, but it is still near motion-blind while walking. Do the **antenna swap test**: swap the RX1/RX2 antennas (or move RX2's to a known-good antenna), record walk path1 (horizontal line, user's naming) + empty into data/live_library/diag_takes3 with host/record_session (same flags as 22 Oct: --setting same_room --layout layout_library --operator-position O --tx-power 5, subject DX), and compare with `scripts/phase5_diag_analysis.py diag_takes3` and `scripts/phase5_motion_timeline.py`. If RX2 becomes normal, do the short live re-run (stand A, walk path1, walk path2, sit_down A, fall M). Settle the path-naming conflict against the sketch. Then close Gate 5 and do Phase 6, stopping at Gate 6. Remind me to remove the BSSID lock AC:DE:01:59:B1:41 and unblock Bluetooth.

## Done this session (branch `cc/phase5`)
- **RX2 physical check (user):** position correct per the sketch; antenna re-seated and/or re-aimed (the user did not say which). Height, chair and nearby objects were not reported.
- **Takes** in `data/live_library/diag_takes2/` (not data/raw; plan `protocol/plan_diag_live2.csv`): E01 walk path2 (11:05, **void**: the walk did not happen in the recording window, user confirmed); E02 empty (11:06); E03 walk path1 = horizontal line (11:13). All GOOD, 0 CRC errors, loss 4.5–6.8 %. Logs `results/phase5/live_library/diag2_record.log`, `diag2b_record.log`.
- **Comparison vs 22 Oct** (`scripts/phase5_diag_analysis.py diag_takes2` → `results/phase5/live_library/diag2_analysis.log`, `diag2_summary.json`; motion over time `scripts/phase5_motion_timeline.py` → `diag2_motion_timeline.log`):
  - RX2 RSSI now −35/−36 dBm (before −34 in every take; 22 Oct median −38). Within ±3 dB.
  - E02 empty: correct (48/53 empty); all 15 key features of both RX at the 32nd–88th percentile of 22 Oct empty.
  - E03 walk path1: **walk 42/52** (D03 this morning 34/53; LOSO 1.00). RX1 normal (17th–75th percentile). **RX2 still low:** motion_mean 0th, sd_mean 3rd, sc_corr 5th percentile (D03: 0, 0, 5). Amplitude-SD over time: RX2 3.9–6.7 vs up to 13.7 in a 22 Oct walk. There was one fall alarm during walking (21.5 s, P(fall) 0.54).
  - **Verdict:** RX2 improved a little but is still near motion-blind. Walking is recognised through RX1. The user's condition for the live re-run was not met, so **no live re-run**.
- **Env-check logging bug fixed (D-058):** every completed environment check is now logged with its run number. New test `test_every_completed_env_check_is_logged`; it fails on the old code. Full suite **93 passed** (`results/phase5/tests_after_envlog_fix.log`).
- `scripts/phase5_diag_analysis.py` takes an optional folder name (default `diag_takes`; the summary goes to `<name>_summary.json`, so the first run's files are unchanged).

## Open
1. **Antenna swap test** (TEST_CONDITIONS "Next: Option A" step 5). It separates antenna/connector from board/position. Then the short live re-run if RX2 is normal.
2. **Path naming conflict:** the user says path 1 = horizontal, path 2 = vertical; `config/position_map.yaml` v2 (Gate 0 correction) says the opposite. Config unchanged; E03 is labelled path1 by the user's naming. Settle against `docs/setup/layout_library_sketch.jpg`.
3. **Reminder:** remove the BSSID lock AC:DE:01:59:B1:41 from RNSIT-STUDENTS; unblock Bluetooth if wanted.
4. Phase 6 not started: archive moves (Gate 0 list + `ml/train.py`, `~/WiFi_CSI_Final/transfer/`, `docs/setup/MIGRATE_TO_MAC.md`, `data/features/stream_3s.csv.incomplete_killed_2026-10-22`, needs approval), README, final docs, reproduction run.
5. `models/env_baseline.json` is untracked (model artefact, rule 4: not committed).
6. Limitations stand: fall detection ≈ half of falls (LOSO), all falls at spot M, a still person can look like an empty room, position dependence; a walking false alarm was seen in E03.

## Earlier today (details in TEST_CONDITIONS.md)
Live test in the library (session 3): chain works end to end (0.50 s steps, RX2 reconnect, no false alarms), but presence/state was wrong with a person present. Six diagnostic takes (`data/live_library/diag_takes`) located the cause at RX2 (−34 dBm, motion features at the 0th–5th percentile; RX1 normal). Dashboard engine moved to its own process (D-057). Tag `v1.0-replay` = the state before the live test.
