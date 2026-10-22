# Decision register

One entry per decision: id, date, decision, why, consequences. Earlier entries (D-006c … D-017) are carried over from `docs/context/PROJECT_CONTEXT.md` §8, where only their short form survived; their full reasoning is in the original handover notes. Superseded entries stay listed and are marked.

## Carried over (in force on 2026-10-22)

| ID | Decision |
| --- | --- |
| D-006c | Boards: TX ESP-WROOM-32U + 8 dBi patch; RX1/RX2 YD Sixspan ESP32-S3 with U.FL 6 dBi omni (register in PROJECT_CONTEXT §2). |
| D-010 | Raw CSI: L-LTF + HT-LTF (+STBC HT-LTF2) on, LTF merge and channel smoothing off. |
| D-011 | UART CRC rejects must stay < 0.5 %. |
| D-012 | RX2 loss limit 3 % on the bench (suspected cause: UART ISR on core 0 with Wi-Fi). |
| D-013 | Scope: presence; states sit/stand/walk/lie; events fall, sit_down, stand_up (+ bend_pick as look-alike negative); live monitor with uncertainty. Through-wall, breathing, counting, auto-calibration, sleep, clinical use are out of scope. |
| D-014 | Protocol: state takes 30 s; event takes 10 s with audio cue at 3 s. |
| D-015 | Evaluation: leave-one-subject-out. |
| D-016 | Keep the random forest unless a CNN is clearly better on LOSO. *(Phase 4 replaces this with the selection rule in PROMPT Phase 4.2.)* |
| D-017 | Record on ch 11 at 5 dBm with a relaxed keep rule: RX1 ≥ 180/s (≥ 165 at spot A), RX2 ≥ 160/s (≥ 150 at spot B), no gap > 100 ms. Not coded in the recorder (which applies 180/s on both); recorded here so it is not lost. |

## Gate 0 decisions (2026-10-22, user)

**D-018 Take overrides.** `20261022_S1_T29_walk` (`valid:false`, empty notes) is used. Overrides live in the version-controlled `config/take_overrides.csv` (`session_id, use, reason`); raw `meta.json` files are never edited. The dataset builder must apply this file and log every override.

**D-019 Decision log location.** This file, `docs/decisions/DECISIONS.md`. PROMPT and STATUS updated.

**D-020 What "never commit .bin" means.** CLAUDE.md rule 4 covers recorded data and trained artefacts (`data/**`, raw `RXn.bin` recordings, `.npz`, models). Firmware images in `releases/**/*.bin` stay tracked. CLAUDE.md clarified.

**D-021 Archive plan.** The moves proposed in Phase 0 STATUS are approved and will be applied in Phase 6.

**D-022 csi_inspect output.** Default output `results/signal/<session_id>/`; any output path inside `data/raw` is refused.

**D-023 Quality gate procedure.** In Phase 3, first diagnose why S1_T06_walk, S1_T22_sit and S3_T43_sit lose every window despite low loss (gap counting, seq wrap, RX alignment); fix bugs before touching thresholds. Then report rejected % per take for missing-packet limits of 10 / 15 / 20 % with a 100 ms max gap.

**D-024 Position confound is first-class.** Features are split into static/shape (band means, RSSI levels, PCA shape) and dynamic/motion (temporal variation, band power, motion energy, derivatives). Every Phase 4 model is reported with all features and with dynamic-only; the event task defaults to dynamic-only unless it loses clearly. A sit_down/stand_up comparison across spots A/B/C serves as a partial position check. The limitation goes into REPORT.md.

**D-025 Evaluated pipeline = live pipeline.** Any motion gate before the fall classifier is fitted inside each LOSO training fold, and the full live decision chain (gate + classifier + 2-of-3 rule) is what gets evaluated; otherwise the gate is dropped.

**D-026 Tests.** A pytest suite grows from Phase 1 onwards (`tests/`).

**D-027 Layout correction.** From the operator's sketch (`docs/setup/layout_library_sketch.jpg`): path1 runs ALONG the link (x ≈ −1.5, y 1.2→4.0), path2 runs ACROSS it (y ≈ 2.55, x −2→+2); PROJECT_CONTEXT had them swapped. Mattress M x −0.5..1.5, y 2.9..3.8. Coordinates live only in `config/position_map.yaml` (version 2) and are read through `pipeline/positions.py`. `meta.json` files are not edited (they store names only).

**D-028 Subjects S5 and S6.** Recorded on 2026-10-22 in the same library set-up from a separate checkout at `e765966`. Until the user says recording is finished, `data/raw` is not touched, the raw audit is not re-run and no dataset is built. Afterwards: re-run the Phase 0 audit, update expected counts, and use **6 LOSO folds, one per subject S1–S6** (confirmed by the user on 2026-10-22). Empty-room takes are dealt to folds take by take. The S5/S6 recording checkout is created by the user at e765966 and is left alone.

**D-029 TX build-default power = 5 dBm (2026-10-22, user).** In firmware v2.1, `CONFIG_TX_POWER_QDBM` defaults to 20 (5 dBm), the same as the NVS-saved boot power used for every recording (D-017). Before this, the default was 8 (2 dBm), so an NVS erase would silently have changed the radio of the study. The saved NVS value still overrides the default. Built (TX v2.1 SHA-256 893dbf15…, `results/firmware/BUILDS.md`), **not flashed**.

**D-030 USB autosuspend off for the receivers (2026-10-22, user).** `setup/linux/99-wifi-csi-usb-power.rules` sets `power/control=on` for RX1 (Espressif USB-Serial-JTAG 303a:1001) and RX2 (CH343 1a86:55d3), one suspected contributor to the RX1 USB drops (W3). Written by Claude, installed by the user (needs sudo).

**D-031 Set-up drift check for later subjects (2026-10-22, user).** When S5/S6 are finished, the raw audit compares each new take's RSSI median per receiver with the 22 Oct baseline for the same activity and position (and empty room with empty room). A difference of more than 3 dB is flagged as a sign that the set-up moved. Flags are reported; they do not by themselves exclude a take.
*Calibration (2026-10-22, `results/audit/rssi_drift_calibration.log`, from the committed baseline table only):* within the 22 Oct set-up, the per-take rule already flags 8/37 S4 takes and 4/22 S3 takes (body shadowing, up to +12 dB on RX2 at spot B), while the per-subject median shift stays ≤ 1.2 dB. So the **per-subject median (and an empty-room take, if recorded) is the set-up-moved indicator**; per-take flags are listed for inspection only.
