# Phase 0 audit — 2026-10-22

Read-only audit of the repository and the dataset recorded on 22 Oct. No code was changed except for one new read-only script (`scripts/audit_raw.py`). Every number below comes from a command run on 2026-10-22 between 14:30 and 14:40 IST. The logs are listed in §5.

Severity: **H** = gives wrong results or loses data if left alone · **M** = weakens the evaluation or the demo · **L** = cosmetic or a small risk.

---

## 1. Dataset check (`data/raw`, read-only)

Command: `python scripts/audit_raw.py --decode --csv results/audit/raw_takes.csv` → `results/audit/raw_audit.log`.
The script opens files for reading only. It also decodes every `RXn.bin` with `host/csiwire.py` instead of trusting `meta.json`.

| Subject | Takes | fall | sit_down | stand_up | bend_pick | walk | stand | sit | lie | empty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 37 | 8 | 8 | 9 | 4 | 3 | 2 | 2 | 1 | |
| S2 | 25 | 5 | 6 | 5 | 2 | 2 | 2 | 2 | 1 | |
| S3 | 22 | 5 | 5 | 5 | 2 | 2 | 1 | 1 | 1 | |
| S4 | 37 | 8 | 8 | 9 | 4 | 3 | 2 | 2 | 1 | |
| none | 4 | | | | | | | | | 4 |
| **Total** | **125** | 26 | 27 | 28 | 12 | 10 | 7 | 7 | 4 | 4 |

**Matches PROJECT_CONTEXT §6 exactly.**

Verified:
- Every folder has `RX1.bin`, `RX2.bin` and `meta.json`, and nothing else. The only stray file is `data/raw/.gitkeep`.
- Folder names match the Format 1 pattern and agree with `meta.subject/take_id/activity/session_id`.
- Every take has a `check` block with records > 0 on both RX.
- The decoded CSI record count equals `meta.check.records` for **all 250 files**.
- Across all files: 0 CRC-rejected frames, 0 packets with an unexpected `csi_len`, 100 % HT40, one TX boot segment per take (no TX reboot inside a take), and TX power 5 dBm on every take.
- Durations are 10 s for all events, 30 s for states, and 120 s for B00.
- Link quality from `meta.check`: RX1 loss median 2.15 % (max 18.1 %, S3_T43_sit at A); RX2 loss median 6.65 % (max 35.3 %, S2_E58_bend_pick at B). Body shadowing is visible as described in PROJECT_CONTEXT.

Unexpected or worth a decision:

| # | Finding | Sev | Proposal |
| --- | --- | --- | --- |
| D1 | `20261022_S1_T29_walk` has **`valid: false`** with empty `notes`. Its check failed only on the strict 180/s rule (RX2 167.8/s, 16.3 % loss, max gap 35 ms); it passes the relaxed D-017 rule. No other S1 T29 exists. Most likely the recorder was stopped at the keep/redo prompt (meta is written with `valid=ok` *before* the prompt, see R5). `build_dataset.py` **silently skips it**, so S1 would train on 2 walks, not 3. | M | You decide: keep it (I'd recommend that, because it passes D-017). I will not edit its `meta.json`. Instead I'll add an override list `protocol/take_overrides.csv` (session_id, valid, reason) that the dataset builder reads. |
| D2 | `none/B01` is kept three times: `B01_empty`, `_r2`, `_r4` (`_r3` is in `_rejected`). These are the three 30 s empty repeats of `plan_empty_short.csv`, not redos, so `_rN` does not mean "redo" here. | L | Treat them as 3 independent empty takes (as PROJECT_CONTEXT says). Document this. |
| D3 | 15 folders carry `_rN` and no (subject, take_id) is kept twice, apart from B01. | — | OK |
| D4 | 35 takes say "kept by operator despite failed check". The recorder applies only the strict rule (`MIN_RATE=180` on both RX). D-017's relaxed rule is not coded anywhere. | L | Record the relaxed rule in the decision log. The per-window quality gate (Phase 3) is the real filter. |
| D5 | One take breaks D-017's "no gap > 100 ms": `S2_E47_sit_down_r3` RX2 max gap 105 ms. | L | Leave it to the window gate. Report it. |
| D6 | **Position is confounded with activity**: fall and lie only at M; sit and stand only at A/B; walk only on the paths; bend_pick, sit_down and stand_up at A/B/C. A model can partly tell "where" instead of "what" from static features (band means, RSSI). | **H** (for honest claims) | Phase 3/4: report a "dynamic-only" feature ablation (no static band means, no RSSI). State the confound as a limitation. |

**v1 dry run on real data** (output to the scratchpad, not a deliverable; log `results/audit/v1_dryrun_real.log`): with the current gate (≤ 10 % missing, gap ≤ 20 packets on *both* RX), **383 of 1377 windows (27.8 %) are rejected**. Three takes lose every window: S1_T06_walk, S1_T22_sit and S3_T43_sit. Four more lose ≥ 75 %: S1_T11_lie, S1_T03_sit, S1_T01_stand_r2 and S2_T03_sit. The 10 % threshold is close to RX2's median loss, so the gate thresholds are a Phase 3 decision (see P4).

---

## 2. Module by module

### `host/csiwire.py` — frame decoder
Matches `wire_protocol_v2.md` (sync, type, len, CRC-16/CCITT-FALSE, 48-byte header, imag-first int8, HT-LTF reorder 0..63,−64..−1 → −64..63). It decoded all 250 real files with 0 CRC errors and counts equal to the recorder's.
- R1 (L): `iter_frames.last_errors` is stored on the function object (global state, not thread-safe). It is only read by `load()`. Return it explicitly when the decoder is next touched.

### `pipeline/preprocess.py` (v1) — the shared frozen interface
Matches CONTRACTS (114 carriers, align by seq, linear fill, per-packet mean normalisation, pair average, 2 s windows, gate 10 % / 20 packets).
- P1 (M): **no anti-alias filter** before 200→100 Hz. The pair average is only a 2-tap boxcar (≈ −3 dB at 50 Hz, so it does not stop 50–100 Hz from folding down). The phase plan (Phase 3) asks for a real low-pass → `PREPROC_VERSION` bump.
- P2 (M): `USED_SC` (114 carriers) is still the textbook layout, **never verified on real data**. Phase 2 checks it.
- P3 (L): no phase channel. Phase 3 adds sanitised phase.
- P4 (M): the gate is "all RX must pass". With RX2 at a 6.65 % median loss and up to 35 % at spot B, a whole class can vanish for one subject. Options for Phase 3: per-RX thresholds, a higher miss limit with an explicit interpolation-fraction report, or keeping windows where one RX is good and masking the other. These need your choice.
- P5 (L): offline passes `hdr`, so FIRST_WORD_INVALID values become NaN → missing. Live (`records_from_arrays` without `hdr`) does not. This has no effect today, because the flag only touches the first two L-LTF values and v1 uses HT-LTF only. It must be unified if L-LTF is ever used.

### `pipeline/build_dataset.py` — Format 1 → Format 2
- B1 (H): **every event window is labelled with the event**. Five windows shifted only ±0.3 s around the motion peak are kept, and no pre-cue or post-action windows. The phase plan (Phase 3) replaces this with overlap-based labels. The 5 near-identical windows per take also inflate per-window counts.
- B2 (M): the cue is placed at grid index `cue_s × 200`, but grid index 0 is the first sequence number heard by **both** RX, not the recording start. The offset is a few packets normally, and more if a receiver missed the first packets. Map the cue through `tx_time_us` / the first seq per RX instead.
- B3 (M): `valid: false` takes are skipped with only a line in index.csv (see D1).
- B4 (L): window length, hop and edge-skip are module constants. The phase plan wants window length as a parameter (2/3/4 s).

### `ml/features.py` (f1, 45 features)
- F1 (H, honesty): 8 static band means + RSSI mean/std per RX encode **position**, which is confounded with activity (D6).
- F2 (L): band powers are computed on PC1 only. `xrx_sd_ratio` is the only cross-RX feature.
- No `miss_frac`/loss features ✔ (phase-plan rule).

### `ml/train.py` — LOSO random forest
- LOSO grouping is correct: empty takes are dealt round-robin to the 4 subjects (project rule 6) ✔. No random splits ✔.
- T1 (M): no hyper-parameter search at all (a fixed RF). Fine as a baseline; Phase 4 adds nested search.
- T2 (M): only per-fold accuracy, no per-fold macro-F1 and no mean ± std; no per-take fall count.
- T3 (H): **the evaluated fall detector is not the deployed one.** LOSO scores the event RF on every window. Live, `Predictor` only runs it when `motion ≥ live_motion_threshold`. That threshold is the 5th percentile of fall motion, fitted on *all* data after LOSO (leaks the test subject into a deployed parameter, and is never evaluated).
- T4 (M): train/serve mismatch. The event model sees windows centred on the motion peak, but live windows arrive at any alignment (every 0.5 s).
- T5 (L): if a fold has fewer than 2 classes, its predictions stay as empty strings and are still scored.

### `ml/predict.py` — Format 3 interface
Matches CONTRACTS (input `[2,200,114]`, output dict, version check against PREPROC/FEATURES versions) ✔. Window shape is hard-coded through `pp.WIN`, so variable window length means an interface version bump.

### `host/record_session.py` — recorder (used all day)
All four known bugs are confirmed in the code:
- R2 (H) bug 1: `check_take` sets `ok=False` on < 10 records, but `k` still keeps the take → 0-CSI takes can be kept.
- R3 (H) bug 2: at the keep/redo prompt, any key other than `r`/`x` (including `q`) **keeps** the take and continues.
- R4 (H) bug 3: `PortReader.run` has no exception handling. A `SerialException` kills the thread silently, and later takes get an empty file for that RX.
- R5 (M) new: `meta.json` is written with `valid=ok` **before** the keep/redo prompt. If the program is stopped at the prompt (Ctrl+C), a failed take stays in `data/raw` with `valid:false` and empty notes. This probably explains D1.
- R6 (L): `rate = records / nominal duration` (not the measured span); `check_take` does not exclude RADIO_MISMATCH packets; the relaxed D-017 rule is not encoded.

### `host/rx_check.py` — link check
Verified on hardware before. Not re-run (it needs boards; opening the TX port resets it).

### `host/csi_inspect.py` — signal inspection
Runs on synthetic data (T1 below) and recovers the built-in layout, gaps and gain step correctly.
- I1 (H, rule 1): **its default output folder is inside the run folder** (`RUN/inspect…`). Pointed at `data/raw/<take>` it would write into raw data. In Phase 2 I will always pass `--out results/signal/...`, and propose changing the default to refuse paths under `data/raw`.

### `app/engine.py` — live/replay engine
- E1 (H): **stale window reported as `ok`** (found by reading the code; Phase 5 adds a test). When one serial port dies, `SerialSource.run` raises and stops (no reconnect). Its buffer keeps its last 800 packets, so `hi` freezes, and for ~3 s the engine re-classifies the **same old window with status `ok`**. After that it says `degraded` ("too many missing packets"), never `no_signal`, even though `rx.rate` = 0. Fix in Phase 5: drop stale buffers by packet age, `no_signal` when rate = 0, reconnect loop.
- E2 (M): replay at `--speed 4` did not reach the second take within 16 s (T5 below). The per-packet Python loop probably cannot keep up. 1× speed was not tested yet. Check in Phase 5.
- E3 (L): smoothing votes and fall votes are not reset when the replay switches take.
- Matches the CONTRACTS engine-state dict otherwise (status, label_smoothed by majority of 3, 2-of-3 fall rule, 10 s cooldown).

### `app/live_app.py`
Never run under Streamlit (an infinite `while True` loop in the script body; a starter). Missing almost everything the phase plan lists for Phase 5 (heatmaps, phase, health, model info, panels).

### `scripts/pipeline.sh`
Works for `synth` (it runs the same commands as T2–T4). It writes `data_synth/`, `models_synth/` and `results_synth/` into the repo (git-ignored). Uses `python3`, not the venv, unless `PY` is set.

### `firmware/` (full review in Phase 1)
Read only. Matches the wire protocol (48-byte packed header with static assert, CRC-16 identical to the host, radio_id fingerprint string identical on TX and RX). Notes for Phase 1:
- W1 (M): RX2's UART driver is installed from `app_main` → its ISR lands on **core 0 together with Wi-Fi**. The writer task is already pinned to core 1. This supports the D-012 suspicion.
- W2 (M): the TX has no watchdog and no host-visible alive signal when unplugged from the PC. The LED code exists (solid on, then 1 Hz OK, 5 Hz error) but its behaviour on the board is unconfirmed.
- W3 (L): RX1's USB link drops frames instantly after one timed-out write (`s_stalled`). That is intended, but a host reconnect is not signalled.
- `releases/v2/*.bin` (six firmware images, 4.9 MB) **are committed to git**, which conflicts with a literal reading of project rule 4 ("never commit `.bin`"). That rule targets raw CSI. See the open question in STATUS.

### Docs vs reality
- `docs/CONTRACTS.md` says "3 volunteers" (now 4) and "2 s windows" (to become a parameter). It needs a v2 note in Phase 3.
- **The decision-log path disagrees**: the project rules say `docs/decisions/DECISIONS.md`, but the phase plan says `docs/DECISIONS.md`. Neither exists yet; the register lives only in PROJECT_CONTEXT §8.
- `docs/PROJECT_STATE.md`, `TEAM_PLAN.md` and `tracks/*` describe the 21 Oct state and are superseded by `docs/context/PROJECT_CONTEXT.md`.
- `host/requirements.txt` uses `>=` (not pinned). The venv also has pandas 3.0.6 and scipy 1.18.1, which are not listed.

---

## 3. Tests that exist and whether they pass

There is **no unit-test suite** (no pytest, no `tests/` with asserts). The only checks are the synthetic generators plus the pipeline. All are SYNTHETIC; their numbers test the code only.

| Test | Command | Result |
| --- | --- | --- |
| T1 | `tests/synthetic/make_synthetic_run.py` → `host/csi_inspect.py --out <scratch>` | PASS: recovers 114 used carriers, L-LTF "upper 20 MHz" placement, the 65 ms gap and 1 gain-change candidate, as built in |
| T2 | `tests.synthetic.make_synthetic_dataset --subjects 3` | PASS: 76 takes |
| T3 | `pipeline.build_dataset` on T2 | PASS: 1168 state + 180 event windows |
| T4 | `ml.train` on T3 | PASS (runs). SYNTHETIC LOSO numbers not reported as results |
| T5 | engine replay (SYNTHETIC model and takes), 4× speed, 16 s | Runs with no errors, but see E2 |
| T6 | v1 `build_dataset` on **real** data → scratchpad | Runs; 994 windows kept / 383 rejected (§1) |
| — | `app/live_app.py` under Streamlit | not run |
| — | `host/rx_check.py`, `record_session.py` | need boards; not run |

Missing tests that the phase plan asks for (Phase 1/3/5): decoder round-trip, alignment, gap fill, labelling, feature shapes, simulated-port recorder tests, and live-vs-offline consistency.

---

## 4. Rule check (project rules, `docs/PROJECT_RULES.md`)
- Raw data untouched ✔ (the audit only reads). `_rejected/` was listed by name only.
- No board was opened, flashed or reset ✔.
- Synthetic outputs went to the scratchpad and are labelled SYNTHETIC ✔.

## 5. Logs
- `results/audit/raw_audit.log`, `results/audit/raw_takes.csv` — dataset audit
- `results/audit/synthetic_tests.log` — T1–T5 (SYNTHETIC)
- `results/audit/v1_dryrun_real.log` — T6

---

## 6. Resolutions at Gate 0 (2026-10-22)
D1 → D-018 (`config/take_overrides.csv`). Decision-log path → D-019. `releases/**/*.bin` stay tracked → D-020. I1 → fixed in Phase 1 (D-022). P4 → diagnosis first (D-023). D6/F1 → D-024. T3 → D-025. Layout: PROJECT_CONTEXT had path1/path2 swapped → corrected (D-027). New subjects S5 and S6 → D-028. See `docs/decisions/DECISIONS.md`.
