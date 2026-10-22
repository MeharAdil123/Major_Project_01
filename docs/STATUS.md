# STATUS — 2026-10-22 ~17:00 IST · Phase 1 done (Gate 1) · waiting for "S5/S6 finished" before Phase 2

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
- `results/audit/pytest_phase1.log`: **40 passed** (decoder round trip, wire contract, csi_inspect output rules + end-to-end on SYNTHETIC data, config/position map/overrides/folds, recorder with simulated ports: bugs 1–5)
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

## Open problems / questions
1. **Fold count:** you wrote "5 LOSO folds", but with S5 *and* S6 that is 6 folds (S1–S6). D-028 records 6, pending your confirmation.
2. **Empty takes vs folds:** 4 empty-room takes for 6 folds means two folds have no empty take, so presence specificity is undefined there. Are S5/S6 also recording empty takes?
3. **Today's S5/S6 session runs the old recorder** (e765966), so bugs 1–5 can still occur there; the post-recording audit will catch them. `git worktree list` here shows no second worktree, so it is presumably a separate clone.
4. Flashing v2.1: your decision. If yes: bench test first (rx_check 120 s, compare RX2 loss v2 vs v2.1), then copy the images to `releases/v2.1/`.

## Next step
Phase 2 (signal inspection) needs `data/raw`. Per D-028 I wait for your "S5/S6 finished". Then: re-run the Phase 0 audit on the new takes, update the expected counts, and start Phase 2 (stopping at Gate 2).
