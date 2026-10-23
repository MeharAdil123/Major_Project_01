# STATUS — 2026-10-23 ~11:00 IST · Phase 5 live test done (diagnosed) · Option A pending · Gate 5 open

## ▶ Prompt for the next session
> Read CLAUDE.md, docs/STATUS.md, results/phase5/live_library/TEST_CONDITIONS.md and docs/context/PROJECT_CONTEXT.md. We are at Gate 5 (live test in the library done; failure diagnosed as an RX2 setup shift). Continue with **Option A** from TEST_CONDITIONS.md ("Next: Option A"): guide me through the RX2 physical checks, record walk-path2 + empty into data/live_library/diag_takes2 with host/record_session (same flags as 22 Oct: --setting same_room --layout layout_library --operator-position O --tx-power 5, subject DX), compare against 22 Oct with scripts/phase5_diag_analysis.py, then a short live re-run; antenna swap test if RX2 is still motion-blind. Also fix the env-check logging bug (log every completed check). Then close Gate 5 and do Phase 6 (archive moves approved at Gate 0, README, final docs, tests, reproduction), stopping at Gate 6. Remind me to remove the BSSID lock AC:DE:01:59:B1:41 and unblock Bluetooth.

## Done today (branch `cc/phase5`; tag `v1.0-replay` = tested state before the live test)
- Phases 4–5 on replay: final models (SVM-RBF events, extra trees state, logistic presence, 4 s, dynamic f2); D-051 calibrated fall alarm adopted (θ 0.5, 2-of-3, 10 s; LOSO 21/42 falls, 8/109 look-alike alarms); engine v2; live = offline bit-identical on 378 windows; environment check; dashboard (`results/REPORT.md`, `docs/decisions/DECISIONS.md` D-046…D-056).
- **Dashboard fix (D-057):** the engine now runs as its own process (`app/engine_proc.py`). In one process with Streamlit it stepped every ~1.5 s; now 0.50 s.
- **Live test in the library** (details and numbers: `results/phase5/live_library/TEST_CONDITIONS.md`, `analysis.log`, `diag_analysis.log`, screenshots):
  - Conditions: laptop Wi-Fi on (exception to D-032), locked to channel 1 (BSSID AC:DE:01:59:B1:41); Bluetooth blocked; strong channel-11 library APs nearby. Preflights 1–3 failed the RX2 limits; preflight 4 passed (RX2 −36 dBm, 7.7 % loss, 0.27 % CRC).
  - Session 3: steps 0.50 s, loss 3–6 %, no crash. **RX2 reconnect works** (degraded after 3 s, ok 5 s after replug). **No false fall alarms.** But presence/state mostly "empty" with a person present (stand A 93/105 empty; walk path2 3/83 walk); fall on the mattress gave no alarm (max P(fall) 0.33).
  - Env check: first run "unreliable" (presence occupied in 92 % of empty windows); 5 runs in total, only the first logged (**bug**); the last showed "ok".
- **Diagnosis (6 diagnostic takes, `data/live_library/diag_takes`, not data/raw):**
  - Receivers not swapped (MACs correct).
  - Offline predictions are as wrong as live → not a live-path issue: walk path2 empty 52/52 (LOSO reference 0.96 walk); fall: no alarm.
  - **RX2 shifted:** RSSI −34 dBm in every take (22 Oct −37…−39, varying with the person); RX2 motion/variation features at the 0th–5th percentile of 22 Oct in all takes. RX1 is normal (10th–75th percentile).
  - **Verdict: setup shift at RX2** (strong, motion-insensitive direct path: antenna position, orientation, height or connector).

## Open
1. **Option A** (fix RX2 → walk path2 + empty takes → compare → short live re-run; antenna swap if still blind): see TEST_CONDITIONS.md.
2. Env-check logging bug (only the first result per session logged).
3. **Reminder:** remove the BSSID lock AC:DE:01:59:B1:41 from RNSIT-STUDENTS; unblock Bluetooth if wanted.
4. Phase 6 not started: archive moves (Gate 0 list + `ml/train.py`, `~/WiFi_CSI_Final/transfer/`, `docs/setup/MIGRATE_TO_MAC.md`, `data/features/stream_3s.csv.incomplete_killed_2026-10-22`, needs approval), README, final docs, reproduction run.
5. Limitations stand: fall detection ≈ half of falls (LOSO), all falls at spot M, a still person can look like an empty room, position dependence.
