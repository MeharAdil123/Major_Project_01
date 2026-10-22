# STATUS — 2026-10-22 ~16:30 IST · Phase 1 done (Gate 1, incl. follow-ups) · waiting for "S5/S6 finished" before Phase 2

## Done in this phase
**Gate 0 decisions applied** (log: `docs/decisions/DECISIONS.md`, D-018 … D-028; the folder `docs/decisions/` did not exist yet and was created):
- `config/take_overrides.csv`: S1_T29_walk is used; its `meta.json` is untouched (D-018).
- CLAUDE.md rule 4 clarified (both copies): `releases/**/*.bin` stay tracked (D-020).
- PROMPT now points to `docs/decisions/DECISIONS.md` (D-019).
- **Layout correction (D-027):** path1 = ALONG the link (x ≈ −1.5, y 1.2→4.0), path2 = ACROSS (y ≈ 2.55, x −2→+2). PROJECT_CONTEXT had them swapped. Corrected in `docs/context/PROJECT_CONTEXT.md` and `docs/PROTOCOL.md`. The single source is `config/position_map.yaml` (v2), read via `pipeline/positions.py`. The sketch is committed at `docs/setup/layout_library_sketch.jpg` and agrees with the correction (the mattress is not drawn on it; its coordinates come from your message). No `meta.json` was edited.
- `host/csi_inspect.py`: default output is `results/signal/<session_id>/`, and any output path inside `data/raw` (also through symlinks) is refused before anything is read (D-022).
- Item 9 checked: the three B01 empty-short takes are distinct folders (`B01_empty`, `_r2`, `_r4`), and `ml/train.groups_for` puts each empty take on its own fold (test `test_empty_takes_dealt_to_folds_take_by_take`).

**Phase 1** (details: `docs/firmware/REVIEW_phase1.md`):
- Firmware review against `wire_protocol_v2.md`: all spec items match; a test now enforces the C/Python header contract.
- v2 rebuilt from e765966 → **bit-identical to `releases/v2`** (TX, RX1, RX2).
- v2.1 patches (on this branch, **not flashed**):
  - F1: RX link driver and ISR moved to core 1.
  - F2: TX build-default power 2 → 5 dBm.
  - F3: TX task watchdog.
  - F4: reset reason + uptime in HELLO.
  - All six images build with **0 warnings, 0 errors**.
- ESP-IDF: the repair is `cd ~/WiFi_CSI_Final/esp/esp-idf-v5.5.5 && ./install.sh esp32,esp32s3` (downloads; **not run**). It was not needed: `scripts/fw_build.sh` builds with the installed compilers (only the RISC-V debugger is missing).
- Recorder v1.1: bugs 1–5 fixed. Takes are staged in `data/raw/_incoming/`, and `meta.json` is written only after the decision.
- pytest suite started (`tests/`, 40 tests).
- `pyyaml 6.0.3` and `pytest 9.1.1` installed in the venv; every host package is pinned in `host/requirements.txt`.

## Verified results (logs)
- `results/audit/pytest_phase1.log`: **43 passed** (decoder round trip, wire contract, csi_inspect output rules + end-to-end on SYNTHETIC data, config/position map/overrides/folds, recorder with simulated ports: bugs 1–5)
- `results/firmware/BUILDS.md` + `v2_rebuild_*.log`, `v21_build_*.log`: build hashes, warnings, sizes

## Gate 1 findings table
| Issue | Severity | Fix | Status |
| --- | --- | --- | --- |
| F1 UART/USB ISR on core 0 with Wi-Fi (RX2 loss, D-012) | M | link init on core 1 | built, not flashed, effect unmeasured |
| F2 TX default power 2 dBm, 5 dBm only in NVS | M | default 5 dBm | built, not flashed |
| F3 no TX watchdog | M | task WDT 5 s → reboot | built, not flashed |
| F4 no reset reason | L | `reset`, `uptime_s` in HELLO | built, not flashed |
| F5/R4 dead or silent serial port → silent empty takes | H | abort + reconnect | done, tested |
| R2 0-CSI take keepable | H | auto-reject | done, tested |
| R3 `q` keeps the take | H | strict prompts, `q` quits without keeping | done, tested |
| R5 meta written before the decision | M | `_incoming` staging | done, tested |
| R6/bug 4 file size as emptiness test | L | decoded CSI count only | done, tested |
| W3 RX1 USB drops | M | host reconnect (recorder now, engine in Phase 5); optional udev autosuspend rule (needs sudo, ask) | partly done |
| F6 WDT panic also reboots on idle starvation | L | accept or disable the idle check | your call |
| csi_inspect writes into raw folders | H | `results/signal/<sid>` default + refusal | done, tested |

## Phase 1 follow-ups (user, 2026-10-22)
- **6 LOSO folds (S1–S6)** confirmed → D-028 updated. The S5/S6 recording checkout (to be created at e765966) is left alone.
- **TX build-default 5 dBm** → D-029. Already part of v2.1 (F2); the built TX sdkconfig has `CONFIG_TX_POWER_QDBM=20`. Built, not flashed.
- **USB autosuspend** → D-030: `setup/linux/99-wifi-csi-usb-power.rules` (RX1 303a:1001, RX2 1a86:55d3; `power/control=on`). It passes `udevadm verify`. **Not installed**; install commands are in `setup/linux/README.md`.
- **S5/S6 audit prepared** → D-031: `scripts/audit_raw.py --baseline-csv results/audit/raw_takes.csv --rssi-tol 3` flags new takes whose RSSI differs from the 22 Oct baseline (same activity and position) by > 3 dB, and reports a per-subject median. Tested on synthetic rows (`tests/test_audit_raw.py`). Calibration on 22 Oct data (`results/audit/rssi_drift_calibration.log`): per-take flags fire on 22 % (S4) / 18 % (S3) of same-day takes; per-subject medians ≤ 1.2 dB. So the subject median is the real indicator.
- Tests: **43 passed** (`results/audit/pytest_phase1.log`).

## Open problems / questions
1. Empty takes vs 6 folds: 4 empty-room takes for 6 folds leaves two folds without one (presence specificity undefined there). An empty-room take before and after the S5/S6 session would fill this and is also the cleanest set-up-drift check.
2. The S5/S6 session runs the old recorder (e765966); bugs 1–5 can still occur there. The post-recording audit catches them.
3. Flashing v2.1: your decision (bench test first: rx_check 120 s, RX2 loss v2 vs v2.1).
4. F6: the TX watchdog also reboots on idle starvation; accept or disable the idle check.

## Next step
Phase 2 (signal inspection) needs `data/raw`. Per D-028 I wait for your "S5/S6 finished". Then: re-run the Phase 0 audit on the new takes, update the expected counts, and start Phase 2 (stopping at Gate 2).
