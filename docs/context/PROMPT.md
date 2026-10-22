# Prompt for Claude Code — paste everything below the line

---

You are taking over the engineering of a Wi-Fi CSI human activity recognition (HAR) project on my Ubuntu laptop. The folder `~/WiFi_CSI_Final` is open. You may read and manage everything in it, within the rules in `CLAUDE.md`. I uploaded `claude_code_handover.zip`, containing `PROJECT_CONTEXT.md` (the full history, hardware, data and decisions), `CLAUDE.md` (standing rules) and this prompt.

**Goal:** turn the 125 labelled takes recorded today into a validated model and a live monitoring dashboard, with an honest evaluation and a clean, reproducible repository. Teach me as you go: for every major choice, explain the problem in a few lines, the options you considered, why you chose one, and how we verify it. I am an ECE student and must defend this work to a panel.

Work in the phases below. **At the end of each phase, stop, show me the evidence (commands run, key output, figures) and wait for my "go".** If something in this prompt is wrong once you see the real code or data, tell me and propose a fix rather than silently following the prompt.

## Phase 0 — Set up and audit (no code changes)

1. Unzip the handover into `~/WiFi_CSI_Final/wifi-csi-har/docs/context/`. Copy `CLAUDE.md` to `~/WiFi_CSI_Final/CLAUDE.md` if it is not already there.
2. Check `git status` in the repo. If anything is uncommitted, show me and commit it to a branch `cc/baseline` before you change anything.
3. Verify the data **read-only**: count takes per subject and activity from `data/raw/*/meta.json` (expected: S1 37, S2 25, S3 22, S4 37, none 4 = 125). Confirm every take has a `check` block with CSI records > 0 on both RX. Report anything unexpected (extra folders, missing `meta.json`, `_rN` duplicates of the same take_id). Do not touch `_rejected/`.
4. Map the whole `~/WiFi_CSI_Final` tree (sizes included). List what looks obsolete, duplicated or generated (old zips, `__pycache__`, `data_synth`, `models_synth`, stray scripts, build folders). **Propose** a target folder structure and a move-to-`_archive` list. Do not move anything yet.
5. Read all code in `host/`, `pipeline/`, `ml/`, `app/`, `scripts/`, `firmware/` and the docs. Produce `docs/AUDIT.md`: what each module does, whether it matches `docs/CONTRACTS.md`, bugs and risks found, and tests that exist and whether they pass (run them).

**Gate 0:** show me the data counts, the proposed structure and archive list, and `AUDIT.md`.

## Phase 1 — Firmware review (read and build only; nothing is flashed)

1. Review `firmware/tx` (classic ESP32) and `firmware/rx` (ESP32-S3) against `docs/firmware/wire_protocol_v2.md`: radio config (ch 11, HT40 below, MCS0 LGI, 200 Hz), CSI config (L-LTF + HT-LTF, no merge/smoothing), payload and header layout, CRC, queueing, error handling, NVS power save.
2. Check the known weaknesses in `PROJECT_CONTEXT.md` §3–4 (RX2 UART ISR on core 0, RX1 USB drop, no TX-alive indicator) and propose concrete fixes. Write them as patches on a branch, **not applied to boards**.
3. The ESP-IDF `export.sh` is broken. Tell me the exact repair command (`./install.sh esp32,esp32s3`). Ask before running it, since it downloads toolchains. Then build both targets and report warnings.
4. Fix the `host/record_session.py` bugs listed in `PROJECT_CONTEXT.md` §4: auto-reject takes with 0 CSI records on either RX; make `q` really quit; detect a dead serial reader, abort the take and offer reconnect. Add tests with simulated ports.

**Gate 1:** findings table (issue → severity → fix → status), build logs, test results. I decide whether any firmware gets flashed later.

## Phase 2 — Signal inspection on real data

Before any preprocessing decision, look at the real signal.

1. Run or fix `host/csi_inspect.py` on one take per class and on an empty take. Answer the three open questions with evidence: (a) which HT-LTF sub-carriers are actually empty (802.11n says 14 empty, 114 used; ESP-IDF docs hint ±57); (b) where the 64 L-LTF bins sit; (c) whether AGC gain steps appear. If `USED_SC` must change, say so and bump `PREPROC_VERSION`.
2. Phase: show raw phase versus **sanitised phase** (unwrap across sub-carriers, then remove the linear slope and offset per packet). Raw ESP32 phase carries random per-packet offsets and is not usable directly; the two receivers are not phase-coherent, so never compare phase across receivers. Show whether sanitised phase (and its time-derivative) visibly changes with motion. Decide with me whether phase features are worth including.
3. Quantify per take: loss %, longest gap, RSSI median, and the body-shadowing cases (spot A → RX1, spot B → RX2).
4. Figures go to `results/signal/` (amplitude heatmap, sanitised-phase heatmap, motion energy with cue and detected peak, for each class).

**Gate 2:** figures plus a short written interpretation, and the decision on `USED_SC` and phase.

## Phase 3 — Preprocessing and features (shared offline and live)

**Corrections to what I originally asked for:** raw CSI must not be converted to one giant CSV, because it is too large and loses structure. The pipeline is:

raw `.bin` (untouched) → decoded, aligned, cleaned arrays (`.npz`, Format 2) → **feature table CSV** (one row per window: identifiers, label and features) → models.

The CSV is the human-readable, model-agnostic feature dataset.

1. Preprocessing (`pipeline/preprocess.py`, one implementation used by both training and live):
   - keep only our TX's packets (radio_id)
   - align RX1/RX2 by TX sequence number
   - mark and fill short gaps
   - per-packet amplitude normalisation (AGC)
   - **anti-alias low-pass before decimating 200 → 100 Hz**
   - sanitised phase as a separate channel
   - a quality gate per window
   
   Keep the gate thresholds as parameters. Report how many windows each take loses, especially S2 E58–E60 and S3 E47/E48.
2. **Labelling (fix of the v1 design):** state takes are labelled windows. For event takes, find the action interval from the motion-energy peak in [cue, cue + 4 s]. Label a window with the event only if it covers enough of that interval (e.g. ≥ 50 % overlap). Windows before the cue are labelled with the pre-action state (`stand` for sit_down/fall/bend_pick, `sit` for stand_up). Windows after the action are labelled with the end posture or dropped, and you justify which. Never label all 10 s as "fall".
3. **Window length:** make it a parameter and build datasets for 2 s, 3 s and 4 s windows. Published fall work uses 3–5 s, and a sit_down lasts 3–4 s.
4. Features, version `f2` with one function per feature group, documented in `docs/FEATURES.md` (what it is, why it should separate the classes):
   - amplitude statistics
   - temporal variation and motion energy
   - PCA-based features (PC1 power, explained variance)
   - band power in 0.3–1 / 1–3 / 3–8 / 8–20 Hz (Doppler-like)
   - sub-carrier correlation
   - RSSI statistics
   - RX1/RX2 ratios
   - sanitised-phase variation features, only if Phase 2 showed they carry signal
   
   Do not use `miss_frac` or loss as features: loss correlates with body position and would leak.
5. Outputs:
   - `data/processed/windows_<len>s.npz`
   - `data/features/features_<len>s.csv`, with columns `session_id, subject, take_id, activity_label, window_label, position, t_start, rx1_miss, rx2_miss, <features…>`
   - `data/processed/index.csv`, listing windows kept and rejected per take with the reason
6. Unit tests for decoding, alignment, gap filling, labelling and feature shapes.

**Gate 3:** dataset summary (windows per class per subject, rejected %), example feature distributions per class, test results.

## Phase 4 — Models, comparison, selection

Use the **tasks** below. Hierarchical is fine if it helps.
- (a) **presence:** empty vs occupied
- (b) **state:** sit / stand / walk / lie
- (c) **events:** fall / sit_down / stand_up / bend_pick / none

Report fall detection separately as fall vs everything else.

1. **Evaluation protocol:** leave-one-subject-out over S1–S4 (4 folds). Hyper-parameter search is nested inside the training subjects. Report per fold and mean ± std.
   - **Primary metric:** macro-F1.
   - **Also report:** per-class precision, recall and F1; confusion matrices; presence sensitivity and specificity; fall sensitivity per window **and per take** ("falls detected k of 26"); false alarms on look-alike takes; latency per window.
2. **Models to compare.** Every model uses the same LOSO folds and the same labelled windows, and reports results the same way. There are three tracks:

   **Track A, classical models on the feature CSV.** Run all three window lengths.
   - logistic regression
   - SVM (RBF)
   - k-NN
   - random forest
   - extra trees
   - HistGradientBoosting
   - XGBoost and LightGBM, if they install cleanly

   **Track B, time-series models without deep learning.** These run on the windowed arrays and are strong on small datasets.
   - MiniRocket + ridge classifier (`sktime` or `aeon`)

   **Track C, deep models used in published CSI HAR work.** These run on the windowed arrays, in PyTorch on CPU. Take the architecture of each from the cited paper or the SenseFi benchmark code, scaled down to our data size, and state the parameter count of each.
   - 1-D CNN
   - LSTM, GRU, BiLSTM
   - CNN-LSTM and CNN-BiLSTM
   - attention-BiLSTM (ABLSTM style)
   - TCN
   - ResNet-1D
   - a small transformer (THAT style)

   **Rules for the deep track**, so the comparison is fair and honest:
   - Use the same LOSO outer folds as the other tracks.
   - Choose epochs and early stopping on an inner validation subject, never on the test subject.
   - Apply augmentation (time shift, amplitude scaling, noise, sub-carrier dropout) to training folds only.
   - Run 3 random seeds and report mean ± std.
   - Fix one compute budget for every deep model.
   - Show training and validation curves for one fold per model to check for overfitting.
   - Run deep models at the best window length from Track A only, unless I ask for more.

   For each model, report LOSO macro-F1 (mean ± std over folds), per-fold scores, falls detected per take, training time, inference time per window, and size. **Selection rule:** choose the simplest model whose LOSO macro-F1 is within one standard deviation of the best and which wins or ties on at least 3 of the 4 folds. Explain the choice to me against this rule.
3. **Ablations (same folds):**
   - RX1 only vs RX2 only vs both
   - amplitude only vs amplitude + phase
   - window length 2 / 3 / 4 s
   - feature groups removed one at a time
4. Select the final model with me, based on the evidence. Retrain it on all subjects and save it in Format 3 (`models/<task>/model.joblib` + `model_meta.json` with classes, versions, window length, features, LOSO scores, trained_at, `synthetic: false`). Keep `Predictor.predict` compatible, or version the interface and update the live engine.
5. Write `results/REPORT.md` with every number, figure and limitation: 1 room, 1 layout, 4 volunteers, simulated falls on a mattress, no video ground truth, not clinical.

**Gate 4:** comparison table, ablations, chosen model and its justification.

## Phase 5 — Live pipeline and dashboard

1. Engine (`app/engine.py`):
   - reads RX1 and RX2 by serial-by-id path (RX2 at 2 Mbaud)
   - uses the same `pipeline/preprocess.py` and feature code as training
   - sliding windows of the chosen length with a 0.5 s hop
   - predictions with confidence and an explicit **uncertain** state
   - smoothing (majority of the last 3)
   - fall alert rule (2 of the last 3 windows above threshold, 10 s cooldown)
   - per-RX health: rate, RSSI, age of the last packet, `no_signal` when the rate is 0
   - automatic reconnect when a port drops, which happened twice today
2. **Replay mode:** plays any recorded take at real speed, with its true label shown next to the prediction. This is the backup demo, and a correctness check that live and offline give the same predictions on the same data. Write that check as a test.
3. **Dashboard (Streamlit, or another tool if you justify it):**
   - room status, current activity, last event, confidence, fall banner
   - live amplitude heatmap for both RX
   - sanitised-phase heatmap
   - motion-energy and RSSI trends
   - packet rate and loss per RX
   - event history
   - model info (version, trained_at, LOSO scores)
   - a "How it works" panel (TX → room → RX1/RX2 → CSI → windows → features → model)
   - a limitations panel
   
   It must run without boards (replay) and with boards (live).
4. **Environment check and calibration:** the demo room differs from the library, and accuracy may collapse in a new room. Add a start-up step that records 60 s of empty room, compares its statistics with the training baseline, and shows "environment differs: predictions unreliable" when they diverge. Propose (do not build without asking) a short labelled calibration routine for new rooms.
5. Live predictions are logged (no raw CSI) to `logs/`.

**Gate 5:** replay demo running, the live-vs-offline consistency test passing, and screenshots.

## Phase 6 — Clean-up and documentation

1. Apply the approved folder structure, moving obsolete files to `_archive/`. Delete nothing.
2. Write:
   - a `README.md` a stranger can follow: hardware, flashing, install, record, process, train, evaluate, run the dashboard, with one command per step in `scripts/pipeline.sh` or a `Makefile`
   - `docs/DECISIONS.md` (merged decision register)
   - `docs/STATUS.md`
   - `docs/setup/host_linux.md`
3. Pin dependencies. A fresh clone plus `pip install -r requirements.txt` plus the README steps must reproduce the results from the raw data.
4. Make sure `.gitignore` excludes data, models and secrets. Prepare the commit; I will push to `github.com/mohithgowdam7/Major_Project` myself.

**Gate 6:** final tree, README, and a full run of the pipeline from raw data to report in one command, with its log.

## Things you must not do
- Edit or delete raw data.
- Flash boards or change TX power without my approval.
- Report numbers that did not come from a run in this session.
- Use random splits.
- Mix synthetic and real results.
- Upload data anywhere.
- Commit secrets.
- Delete files instead of archiving them.
- Skip a gate.
