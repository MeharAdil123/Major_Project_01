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
| D-016 | Keep the random forest unless a CNN is clearly better on LOSO. *(Phase 4 replaces this with the selection rule of phase plan 4.2.)* |
| D-017 | Record on ch 11 at 5 dBm with a relaxed keep rule: RX1 ≥ 180/s (≥ 165 at spot A), RX2 ≥ 160/s (≥ 150 at spot B), no gap > 100 ms. Not coded in the recorder (which applies 180/s on both); recorded here so it is not lost. |

## Gate 0 decisions (2026-10-22, user)

**D-018 Take overrides.** `20261022_S1_T29_walk` (`valid:false`, empty notes) is used. Overrides live in the version-controlled `config/take_overrides.csv` (`session_id, use, reason`); raw `meta.json` files are never edited. The dataset builder must apply this file and log every override.

**D-019 Decision log location.** This file, `docs/decisions/DECISIONS.md`. Phase plan and STATUS updated.

**D-020 What "never commit .bin" means.** Project rule 4 (`docs/PROJECT_RULES.md`) covers recorded data and trained artefacts (`data/**`, raw `RXn.bin` recordings, `.npz`, models). Firmware images in `releases/**/*.bin` stay tracked. The rule was clarified accordingly.

**D-021 Archive plan.** The moves proposed in Phase 0 STATUS are approved and will be applied in Phase 6.

**D-022 csi_inspect output.** Default output `results/signal/<session_id>/`; any output path inside `data/raw` is refused.

**D-023 Quality gate procedure.** In Phase 3, first diagnose why S1_T06_walk, S1_T22_sit and S3_T43_sit lose every window despite low loss (gap counting, seq wrap, RX alignment); fix bugs before touching thresholds. Then report rejected % per take for missing-packet limits of 10 / 15 / 20 % with a 100 ms max gap.

**D-024 Position confound is first-class.** Features are split into static/shape (band means, RSSI levels, PCA shape) and dynamic/motion (temporal variation, band power, motion energy, derivatives). Every Phase 4 model is reported with all features and with dynamic-only; the event task defaults to dynamic-only unless it loses clearly. A sit_down/stand_up comparison across spots A/B/C serves as a partial position check. The limitation goes into REPORT.md.

**D-025 Evaluated pipeline = live pipeline.** Any motion gate before the fall classifier is fitted inside each LOSO training fold, and the full live decision chain (gate + classifier + 2-of-3 rule) is what gets evaluated; otherwise the gate is dropped.

**D-026 Tests.** A pytest suite grows from Phase 1 onwards (`tests/`).

**D-027 Layout correction.** From the operator's sketch (`docs/setup/layout_library_sketch.jpg`): path1 runs ALONG the link (x ≈ −1.5, y 1.2→4.0), path2 runs ACROSS it (y ≈ 2.55, x −2→+2); PROJECT_CONTEXT had them swapped. Mattress M x −0.5..1.5, y 2.9..3.8. Coordinates live only in `config/position_map.yaml` (version 2) and are read through `pipeline/positions.py`. `meta.json` files are not edited (they store names only).

**D-028 Subjects S5 and S6.** Recorded on 2026-10-22 in the same library set-up from a separate checkout at `e765966`. Until the user says recording is finished, `data/raw` is not touched, the raw audit is not re-run and no dataset is built. Afterwards: re-run the Phase 0 audit, update expected counts, and use **6 LOSO folds, one per subject S1–S6** (confirmed by the user on 2026-10-22). Empty-room takes are dealt to folds take by take; with 7 empty takes every fold gets at least one. The S5/S6 recording checkout is created by the user at e765966 and is left alone.

**D-029 TX build-default power = 5 dBm (2026-10-22, user).** In firmware v2.1, `CONFIG_TX_POWER_QDBM` defaults to 20 (5 dBm), the same as the NVS-saved boot power used for every recording (D-017). Before this, the default was 8 (2 dBm), so an NVS erase would silently have changed the radio of the study. The saved NVS value still overrides the default. Built (TX v2.1 SHA-256 893dbf15…, `results/firmware/BUILDS.md`), **not flashed**.

**D-030 USB autosuspend off for the receivers (2026-10-22, user).** `setup/linux/99-wifi-csi-usb-power.rules` sets `power/control=on` for RX1 (Espressif USB-Serial-JTAG 303a:1001) and RX2 (CH343 1a86:55d3), one suspected contributor to the RX1 USB drops (W3). Installed by the user (needs sudo).

**D-031 Set-up drift check for later subjects (2026-10-22, user).** When S5/S6 are finished, the raw audit compares each new take's RSSI median per receiver with the 22 Oct baseline for the same activity and position (and empty room with empty room). A difference of more than 3 dB is flagged as a sign that the set-up moved. Flags are reported; they do not by themselves exclude a take.
*Calibration (2026-10-22, `results/audit/rssi_drift_calibration.log`, from the committed baseline table only):* within the 22 Oct set-up, the per-take rule already flags 8/37 S4 takes and 4/22 S3 takes (body shadowing, up to +12 dB on RX2 at spot B), while the per-subject median shift stays ≤ 1.2 dB. So the **per-subject median (and an empty-room take, if recorded) is the set-up-moved indicator**; per-take flags are listed for inspection only.

**D-032 RF hygiene (2026-10-22, user).** During recording **and** live use, the laptop's own Wi-Fi and Bluetooth are switched off (and phones are in airplane mode, as in the morning session). Evidence from the user's link check before S5: with the laptop radios on, RX2 lost 41.5 % at strong RSSI (≈ −38 dBm); with them off, RX1 −36.4 dBm 1.1 % loss and RX2 −38.1 dBm 4.7 % loss. The live dashboard (Phase 5) shows this rule in its start-up check, and the README states it.

**D-033 Dataset after S5/S6 (2026-10-22).** 202 takes: S1 37, S2 25, S3 22, S4 37, S5 37, S6 37, none 7 (fall 42, sit_down 43, stand_up 46, bend_pick 20, walk 16, stand 11, sit 11, lie 6, empty 7). Verified by decoding all 404 files (`results/audit/raw_audit_s5s6.log`); the counts live in `config/dataset_expected.yaml` and the audit checks them. S5/S6 were recorded in the afternoon after a TX re-aim. RSSI shows no drift (per-subject median shift S5 RX1 +0.0 / RX2 −1.0 dB, S6 −0.5 / −1.0 dB, afternoon empty +1.0 / −0.5 dB). But the static channel profile shifted between morning and afternoon (empty takes: 3.4 / 4.4 dB RMS across sessions vs 0.8 / 1.2 dB within the afternoon; `results/audit/empty_compare.log`). This is a session effect that coincides with the subject split S1–S4 vs S5/S6, and it goes into the limitations. The afternoon empty takes are `B01_empty_r5/_r6/_r8`.

## Phase 2 decisions (2026-10-22; evidence: `docs/analysis/phase2_signal_inspection.md`)

**D-034 Event onset/end detector o1** (`pipeline/onset.py`) replaces `build_dataset.motion_energy` for event timing. The motion signal is gain-normalised amplitude → anti-alias FIR + decimation to 50 Hz → PCA (PC1–3) → 0.25 s sliding std; each RX is divided by its pre-cue baseline; the combined signal is the max over RX. An action is a peak ≥ 3× in [cue, cue+4 s]; the interval uses hysteresis (2× pre-cue on the onset side, max(2, 1.5× post-action level) on the end side), merges strong bursts within 1.5 s, and clips an onset before the cue. Validation on 151 event takes: detected 0.95, inside the window 0.85, RX1/RX2 onset difference median 0.21 s. Phase 3 labels event windows from this interval (user, Gate 2 notes).

**D-035 CSI scaling steps.** About 6 dB per-packet scale shifts exist on both receivers (ESP-IDF automatic CSI scaling). Firmware stays unchanged (no `manu_scale`). Per-packet gain normalisation removes them. The low-scale fraction is reported per RX per take (`results/signal/low_scale_per_take.csv`) and is **never a feature**: it depends on position (spot B).

**D-036 Phase features.** Sanitised phase = unwrap across carriers + remove each packet's least-squares line (standard method; an unwrap-free variant was noisier and rejected). Phase 3 adds dynamic phase features (temporal variance, derivative), weighted by carrier amplitude so faded carriers prone to 2π slips count little. Phase is never compared across receivers. Kept or dropped by the Phase 4 ablation.

**D-037 USED_SC verified.** 114 HT-LTF carriers (−58..−2, +2..+58) are confirmed on 396/404 receiver-takes (the rest are take-specific fades). No `PREPROC_VERSION` change for the carrier set. L-LTF (upper 20 MHz) is not used.

**D-038 Takes that do not start still** (10 walking-start falls). All are used for state windows, with pre-cue windows labelled **walk**. For event windows, the 7 with a clean onset after the cue are kept; S2_E57, S5_E39 and S6_E39 (motion runs into the cue) are excluded. Proposed by the user; the list was confirmed at Gate 2 (pending "go").

**D-024 (addendum).** The static feature group contains RSSI levels and the static amplitude shape (band means, PCA shape); body shadowing confirmed both depend on position.

## Phase 3 decisions (2026-10-22)

**D-039 Preprocessing v2 and quality gate** (`PREPROC_VERSION = "v2"`). Each window is processed from its raw grid packets plus 0.25 s margins: per-packet gain normalisation, anti-alias FIR + decimation 200 → 100 Hz, and a sanitised-phase channel (unit phasor filtered, gap-filled through its phasor). Offline and live see identical windows; a test checks this. Window length is a parameter (2/3/4 s; 3 s default). The gate is ≤ 20 % missing and longest gap ≤ 20 packets (100 ms) on both RX. Evidence (D-023, `results/dataset/gate_diag.log`): the three zero-window takes have no bug (gap counts agree, no duplicates or wraps, alignment clean). They have 18–22 % scattered loss on one RX. On 3 s windows the rejected share is 21.5 % / 9.8 % / 3.9 % for 10 / 15 / 20 %, and 10 % would remove 67 % of S1's windows. The gap rule never rejects alone. The 15 % gate is kept as a sensitivity check (filter on `rx1_miss`/`rx2_miss` in the feature CSV).

**D-040 Labelling** (`pipeline/labels.py`). Onset o2 (end may run to cue + 6 s; detections < 0.6 s flagged). Event label when overlap ≥ 50 % of min(interval, window). Pre-action windows (ending ≥ 0.3 s before the onset) get the start posture: stand, or sit for stand_up, or walk for walking-start falls. Post-action windows (starting ≥ 0.3 s after the end) get the end posture (sit / stand / lie / stand). Windows in between are dropped. Post-action windows are kept, flagged `source=event_post`, because they add postures at positions the state takes never cover (e.g. sitting at C), which weakens the position confound. Phase 4 reports state results with and without them. Takes not usable for event training give no event windows: no detection (8), short (< 0.6 s), onset clipped, and the D-038 exclusions. All of them stay in the per-take evaluation, which runs the live decision chain over every event take, independent of the onset detector.

**D-041 Features f2** (`ml/features.py`, `docs/FEATURES.md`): 83 features, 33 static and 50 dynamic, with 10 subgroups for ablations. Amplitude-weighted phase features. No loss-type features.

**D-042 Format 2 v2.** `data/processed/windows_<len>s.npz` (X and P float16 [N,2,T,114], rssi, y, source, ids, miss_frac, max_gap, t_start, version strings) and `data/features/features_<len>s.csv`. Contract updated in `docs/CONTRACTS.md`. `ml/train.py`, `ml/predict.py` and `app/engine.py` still use the v1 interface until Phases 4/5 rewrite them.

**D-043 Phase 4 packages (2026-10-22).** Installed in the venv: `xgboost-cpu 3.4.1` (the `xgboost` wheel would pull a large NVIDIA NCCL library this laptop does not need), `lightgbm 4.7.0`, `torch 2.14.1+cpu`. numpy 2.5.4, scipy 1.18.1 and scikit-learn 1.9.1 are unchanged. Not installed: `aeon` (a pip dry-run shows it would downgrade numpy to 2.3.5 and scipy to 1.17.1 through numba) and `sktime` MiniRocket (also needs numba). Track B therefore uses a NumPy re-implementation of MiniRocket (`ml/minirocket.py`), labelled as such in every result.

**D-044 Gate 3 not stopped (2026-10-22).** The user asked to stop at Gate 3 only if the loss-tolerance test, labelling or the dataset summary showed something unexpected. None did (`results/dataset/summary.log`; STATUS has the details), so Phase 4 started directly.

**D-045 Phase 4 stays on the Linux laptop (2026-10-22, user).** The planned move to a MacBook was cancelled: the laptop hotspot did not appear on the Mac, and the Mac's USB networking does not bind on Linux (`cdc_ncm … bind() failure`). The archive had been copied to the user's phone (size verified, 710,328,320 bytes) but is not used; the user removes it from the phone. `docs/setup/MIGRATE_TO_MAC.md` and `~/WiFi_CSI_Final/transfer/` stay for a later move. GitHub cannot carry the recordings (project rule 4). Phase 4 runs here: Intel i3-7020U (2 cores / 4 threads), 7 GB RAM, so runs are long and staged.

## Phase 4 (2026-10-23; evidence `results/REPORT.md`, `results/phase4/`)

**D-046 Window length 4 s**, by the rule fixed in advance (`scripts/phase4_choose_window.py`): mean best-model macro-F1 over the three tasks, dynamic features. 2 s 0.533 / 3 s 0.582 / 4 s 0.603. The user expected 3 s; the rule chose 4 s (outside the 0.005 tie margin).

**D-047 Selection rule for 6 folds.** "Wins or ties on ≥ 3 of 4 folds" becomes ≥ 5 of 6 folds (75 %), with a tie meaning within 0.02 macro-F1 of the best on that fold. A 4-of-6 reading is reported too and gives the same picks. Results: events → MiniRocket, state → extra trees, presence → MiniRocket. Final choice made with the user at Gate 4.

**D-048 Deep models reported as run.** All 10 overfit under the fixed budget (train loss ↓, inner-validation loss ↑ from about epoch 3). They were not re-tuned after seeing results.

**D-049 Per-take bug fix.** `phase4_pertake.py` reported `falls_detected_among_onset_missed` wrongly: an object-typed bool column was inverted with `~`. Fixed and rerun. The headline numbers were unaffected. The old JSONs are kept as `*.superseded_bug_onset_missed`.

## Gate 4 (2026-10-23, user decision)

**D-050 Final models (4 s windows, dynamic-only features f2).** Events → **SVM-RBF**, state → **extra trees** (the rule's pick), presence → **logistic regression**. Two departures from the selection rule (D-047), recorded with their reasons; the rule's picks stay in `results/REPORT.md` for transparency:
1. *Events: SVM-RBF instead of MiniRocket.* Falls were declared the target before the run (phase plan: "Report fall detection separately", D-013/D-025), and MiniRocket is worse on exactly that class: window-level fall F1 0.464 vs 0.521, fall sensitivity 0.434 vs 0.552. The live alarm needs calibrated probabilities (P(fall) ≥ θ); MiniRocket's ridge head gives none. Its single-window transform also takes 326 ms on this laptop vs < 1 ms for SVM prediction on f2 features (133 ms).
2. *Presence: logistic regression instead of MiniRocket.* Stability across subjects: MiniRocket's mean (0.729) hides two collapsed folds (S3 0.474, S4 0.487; std 0.178), while logistic regression is 0.698 ± 0.065 with no fold below 0.587. Presence errors are expensive in a monitor (a false "empty" hides a person). Logistic regression is also the simplest model and its probabilities are directly usable.

**D-051 Bounded fall-alarm experiment before retraining (user).** A binary fall-vs-rest SVM with Platt-calibrated probabilities (calibration fitted on training subjects only). Per outer fold, the alarm threshold and k-of-n rule (1-of-2, 2-of-3, 2-of-4) are chosen from INNER leave-one-subject-out stream predictions on the training subjects only. The objective is maximum falls detected per take, subject to look-alike false alarms ≤ 9/109 and walking alarms/hour ≤ the current chain's. The settings are applied unchanged to the held-out subject. It is adopted only if it detects more falls with no increase in look-alike or walking false alarms; otherwise the current chain (5-class SVM, θ 0.6, 2-of-3) stays. There is no tuning on test subjects.

**D-051 result (2026-10-23): adopted.** New chain 21/42 falls vs 18/42, look-alike alarms 8/109 vs 9/109, walking alarms 30.3 vs 45.4 per hour. Empty/still alarms 6.4 vs 3.2 per hour (2 vs 1 alarm; not part of the adoption rule). Final settings from all six subjects' outer-LOSO predictions: θ = 0.5, 2-of-3, 10 s cooldown. `results/REPORT.md` §7.

**D-052 Predictor interface p2 (frozen-interface change).** `Predictor.predict(X, rssi)` becomes `predict(X, rssi, P)`: f2 features need the sanitised phase. All v1 output keys stay (`label, confidence, probs, motion, fall_prob, uncertain`); added: `presence_prob, state, state_probs, event, event_probs`. Models live in `models/{presence,state,events,fall_alarm}/` (no `_rf` suffix). `fall_prob` comes from `fall_alarm` when present. The alarm rule settings are in `Predictor.alarm`; the rule runs in the engine. Feature extraction now caches the per-receiver PCA within one call: identical outputs (max difference 0.0 on 40 real windows), 128 → 67 ms per window.

## Phase 5 (2026-10-23)

**D-053 Engine v2** (`app/engine.py`). It uses the same preprocess v2 / f2 / Predictor p2 as training, and the adopted alarm (≥ 2 of the last 3 windows with fall_prob ≥ 0.5, 10 s cooldown). A receiver silent > 1 s never yields a prediction (`degraded`; both silent → `no_signal`), fixing audit E1. Serial sources reconnect by `/dev/serial/by-id` token. BLAS is limited to one thread: on this 2-core laptop, multi-threaded BLAS made steps 533 ms median / 1.7 s p90 with the dashboard running, vs 251 / 336 ms with one thread. Live step interval in the running dashboard: median 0.50 s, p90 0.64 s (`results/phase5/step_timing.log`). Logs hold predictions and health only (`logs/live_*.jsonl`), never raw CSI.

**D-054 Live = offline, verified.** `app/consistency.py` replays a take packet by packet through Buffer/Engine on a simulated clock and rebuilds each window offline at the same TX sequence. Result: bit-identical on 378 windows of 12 real takes, including the high-loss ones, with max differences of exactly 0 in X, P, RSSI and all probabilities (`results/phase5/consistency.log`). It is also a unit test on a synthetic take (`tests/test_engine.py`).

**D-055 Environment check** (`app/envcheck.py`). 60 s of empty room vs `models/env_baseline.json`, checked on dynamic-feature shift (median |z| ≤ 2, ≤ 30 % outside the training 5–95 % range), presence "occupied" ≤ 20 % and fall-threshold crossings ≤ 5 %. The static profile difference is shown as information only. Thresholds were set before validation. Validation (`results/phase5/envcheck.log`): 7/7 empty takes pass (baseline leave-one-take-out; the presence model is in-sample); 7/8 takes with a person present are flagged; 1 miss (S5_T01_stand_r2, a person standing still, occupied share exactly at the 20 % limit). Thresholds were not changed after seeing this. The labelled calibration routine is proposed only (`docs/analysis/calibration_proposal.md`).

**D-056 Replay is in-sample.** The final models were trained on all recorded takes, so the replay demo is a system demo, not a test. The dashboard says so in replay mode; test results are the LOSO numbers in `results/REPORT.md`.

**D-057 Engine in its own process for the dashboard (2026-10-23).** `app/engine_proc.py` starts `python -m app.engine_proc` and talks over a local authenticated socket. Reason: with Streamlit in the same process, live steps came every ~1.45 s; the engine alone steps every 0.50 s. Engine code is unchanged. Live test conditions, results and the RX2 diagnosis: `results/phase5/live_library/TEST_CONDITIONS.md`.

**D-058 Environment-check log: every completed run (2026-10-23).** `app/engine.py` wrote only the first completed environment check per session to the live log (a `_env_logged` flag that was never reset). In the library session 3 the check ran 5 times and only the first was logged. Now each `start_env_check` increments `env_runs`, and each completed run is logged once as `env` with `run: <n>`. Test `tests/test_engine.py::test_every_completed_env_check_is_logged` (3 runs → 3 log entries). The live log is not a frozen interface (not in `docs/CONTRACTS.md`), so there is no version bump; the engine logic and predictions are unchanged.

**D-059 Walk path naming confirmed (2026-10-23, user).** path1 = vertical (along the link, x −1.5), path2 = horizontal (across the link, y 2.55), as in `config/position_map.yaml` v2. A statement earlier the same day ("path 1 = horizontal") was withdrawn. Diagnostic takes E03 and F01 were labelled "path1" but walked on the horizontal line (= path2); this is recorded in TEST_CONDITIONS.md and their meta.json files are left as recorded.

**D-060 RX2 fault and Gate 5 closed (2026-10-23).** The morning's live failure was traced to a poorly mated U.FL connector at RX2: RSSI +4 dB and motion features at the 0th–5th percentile, with RX1 normal. It was fixed by re-mating it (swap test, then swap back to the 22 Oct pairing): on walk path2, RX2 sits at the 72nd–97th percentile. The final live test (11:40–11:53) is reported as a functional test with its failures (no fall alarm, 2 false alarms while walking, presence fragility on empty rooms, vertical walk mostly "empty"). By the user's decision there is no further testing. LOSO stays the evaluation. Evidence: `results/phase5/live_library/TEST_CONDITIONS.md`.

## Phase 6 (2026-10-23)

**D-061 Archive and assistant-independent repository (user, final plan).** The Gate 0 archive plan (D-021) and the later items were applied (`../_archive/ARCHIVE_LOG.md`). Files written for an AI assistant (session rules, phase prompt, per-person prompt briefs, handover bundle) were moved to `../_archive/20261023/`. The project rules are now `docs/PROJECT_RULES.md`, written for human maintainers, and references to the old rule file point there. "PROMPT" references now read "phase plan". No code or script depends on an assistant. Git history was not rewritten. The README acknowledges AI assistance for code and documentation; the team is responsible for design, data collection and validation. Also moved within the repo: synthetic generators to `tests/synthetic/`, `requirements.txt` to the repo root, early planning docs to `docs/history/`. `ml/train.py` (v1) was archived; its fold test now checks `ml.evaluate.assign_folds`.

**D-062 Reproduction (Phase 6).** `scripts/pipeline.sh reproduce` (`scripts/reproduce.sh`):
1. Checks every raw file against `results/audit/raw_sha256.txt`.
2. Runs the audit.
3. Rebuilds the 4 s dataset from `data/raw` and retrains the final models, both into a scratch folder.
4. Compares them with the committed features and models (`scripts/reproduce_check.py`).
5. Runs the live = offline check and the unit tests.

It never overwrites committed outputs. The ~7 h model comparison (`scripts/pipeline.sh phase4`) is documented, not re-run. `ml/train_final.py` gained a `--models` option (default unchanged).
