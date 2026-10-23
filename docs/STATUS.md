# STATUS — 2026-10-23 ~11:30 IST · Phase 5 · antenna swap restored RX2; empty room read as occupied (presence-model fragility); swap-back proposed · Gate 5 open

## ▶ Prompt for the next session
> Read CLAUDE.md, docs/STATUS.md, results/phase5/live_library/TEST_CONDITIONS.md ("Option A, round 1/2/3") and docs/context/PROJECT_CONTEXT.md. We are at Gate 5. After the antenna swap (antenna B → RX1, A → RX2), both receivers respond to walking and walking is recognised (47/52). But the new empty take F02 is predicted "stand" in 38/52 windows. Re-check the empty room (live env check or a new empty take, nobody inside the tape), then do the short live re-run (stand A, walk path1, walk path2, sit_down A, fall M). Settle the path-naming conflict against the sketch. Then close Gate 5 and do Phase 6, stopping at Gate 6. Remind me to remove the BSSID lock AC:DE:01:59:B1:41 and unblock Bluetooth.

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

- **Antenna swap test (11:22–11:23, `data/live_library/diag_takes3`, `diag3_analysis.log`, `diag3_motion_timeline.log`):** antennas swapped (B, formerly on RX2, → RX1; A → RX2); no visible damage. F01 walk path1: **walk 47/52**, RX2 motion features back inside 22 Oct (14th–46th percentile; amplitude SD 5–14), and RX1 with antenna B still normal. So antenna B is not faulty; the fresh U.FL mating fixed RX2 (likely a poorly mated contact). F02 empty: features normal (28th–82nd percentile), **but presence "stand" 38/52 (P(occupied) 0.89)**; RX1 empty RSSI −33 (+4 dB vs 22 Oct).

- **Empty retake F03 (11:26, `presence_contrib.log`, `presence_empty_loso.log`):** RSSI −36/−36 (in range), all key features inside the 22 Oct empty range, **but presence "occupied" 53/53 (P 0.97)**. Contribution analysis: no feature is out of range; many noise features sit mid-distribution instead of at the quiet end, and together they cross the boundary. The presence model is fragile on empty rooms even in LOSO (0.00–0.42 occupied per 22 Oct empty take). E02's "correct" empty was partly due to the blind RX2. New script `scripts/phase5_presence_contrib.py`.

## Open
1. **Empty room read as occupied after the swap.** Proposed: swap the antennas back to the 22 Oct pairing (A → RX1, B → RX2), firmly clicked, then walk path1 + empty takes (diag_takes4). If both RX are normal and empty is correct → short live re-run. Otherwise, report the presence weakness as a limitation and decide with the user whether to run the live test anyway.
2. **Path naming conflict:** the user says path 1 = horizontal, path 2 = vertical; `config/position_map.yaml` v2 (Gate 0 correction) says the opposite. Config unchanged; E03 is labelled path1 by the user's naming. Settle against `docs/setup/layout_library_sketch.jpg`.
3. **Reminder:** remove the BSSID lock AC:DE:01:59:B1:41 from RNSIT-STUDENTS; unblock Bluetooth if wanted.
4. Phase 6 not started: archive moves (Gate 0 list + `ml/train.py`, `~/WiFi_CSI_Final/transfer/`, `docs/setup/MIGRATE_TO_MAC.md`, `data/features/stream_3s.csv.incomplete_killed_2026-10-22`, needs approval), README, final docs, reproduction run.
5. `models/env_baseline.json` is untracked (model artefact, rule 4: not committed).
6. Limitations stand: fall detection ≈ half of falls (LOSO), all falls at spot M, a still person can look like an empty room, position dependence; a walking false alarm was seen in E03.

## Earlier today (details in TEST_CONDITIONS.md)
Live test in the library (session 3): chain works end to end (0.50 s steps, RX2 reconnect, no false alarms), but presence/state was wrong with a person present. Six diagnostic takes (`data/live_library/diag_takes`) located the cause at RX2 (−34 dBm, motion features at the 0th–5th percentile; RX1 normal). Dashboard engine moved to its own process (D-057). Tag `v1.0-replay` = the state before the live test.
