# WiFi-CSI HAR — consolidated project context (as of 2026-10-22, 13:50 IST)

This file merges ~20 planning/handover notes written between 18 and 22 Oct 2026. Where older notes disagreed, the resolution is already applied here. **Facts marked (verified) come from pasted tool output. Everything else is a plan, an assumption or an open question — check it on the machine.**

---

## 1. Goal and scope

Camera-free human activity recognition (HAR) with Wi-Fi Channel State Information (CSI) from ESP32 boards.

- **In scope (D-013):** presence (empty vs occupied); states sit / stand / walk / lie; events **fall, sit_down, stand_up** (targets) and **bend_pick** (fall look-alike, negative class); a live monitor with uncertainty.
- **Out of scope / future work (say so openly):** through-wall sensing, breathing rate, people counting, automatic calibration to new rooms, sleep detection, clinical use.
- **Every claim states its limits:** one room, one layout, 4 volunteers, simulated falls on a mattress, not clinically validated.

## 2. Hardware (verified, decision D-006c)

| Role | Board | MAC | Host link | A0 antenna test |
| --- | --- | --- | --- | --- |
| TX | ESP-WROOM-32U NodeMCU (classic ESP32, target `esp32`), patch antenna 8 dBi V-pol | 20:9B:A9:68:F3:F0 | standalone on wall adapter; UART `/dev/ttyUSB0` only for commands (opening the port resets the board) | PASS (−21 dB median) |
| RX1 | YD "Sixspan" ESP32-S3-N16R8 #1 (target `esp32s3`), RF selector moved to U.FL, 6 dBi omni | 28:84:85:85:5E:2C | native USB-Serial-JTAG `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:85:5E:2C-if00` | PASS (−19 dB) |
| RX2 | YD Sixspan #2, same | 28:84:85:48:D7:DC | **UART via CH343 at 2 000 000 baud** (its native USB is faulty) `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C38144809-if00` | PASS (−19 dB) |
| Spare | YD "odd" S3 | AC:27:6E:A4:4E:30 | — | not re-tested |

## 3. Radio and firmware (verified on hardware 21 Oct)

- ESP-IDF **v5.5.5**, at `~/WiFi_CSI_Final/esp/esp-idf-v5.5.5`. **`export.sh` is broken** (missing riscv gdb). Flashing works via `~/.espressif/python_env/idf5.5_py3.12_env/bin/python -m esptool`. Fix before any rebuild: `./install.sh esp32,esp32s3` (needs internet).
- **TX firmware `csi_tx` v2** (`firmware/tx`): ESP-NOW broadcast every 5 ms (200 Hz), PHY forced to **HT40 MCS0 long GI**, channel 11, secondary channel below, 32-byte payload: magic `CSI1`, 32-bit seq, TX time, `radio_id` (CRC32 of the radio config), rate, TX power. UART commands: `power <2..20>`, `power <dBm> save` (NVS, survives reboot), `power default`, `status`. **Saved boot power = 5 dBm.** Status LED GPIO2 (behaviour not confirmed).
- **RX firmware `csi_rx` v2** (`firmware/rx`, separate RX1/RX2 builds): promiscuous mode, CSI callback, filter by TX MAC; L-LTF + HT-LTF + STBC-HTLTF2 on, merge/smoothing off (D-010 raw CSI); queue depth 64 to a writer task. Binary wire protocol v2 (`docs/firmware/wire_protocol_v2.md`): sync, type, length, payload, CRC-16/CCITT-FALSE; 48-byte header + CSI.
- **CSI = 384 bytes per packet**: L-LTF 64 sub-carriers (128 B) + HT-LTF 128 sub-carriers (256 B), int8, **imaginary byte first**; HT-LTF buffer order 0..63 then −64..−1, reordered to −64..63 in `host/csiwire.py`.
- HT40 confirmed: 100 % of packets at 40 MHz in every run.
- Known firmware/link weaknesses: RX2 loses ~1–1.5 % more than RX1 on the bench (suspect UART ISR sharing core 0 with Wi-Fi, D-012); RX1 native USB dropped twice today; TX had no watchdog/indicator when its power was cut.

### Open radio questions (must be checked on real data before trusting `USED_SC`)
- **Empty HT-LTF sub-carriers.** 802.11n HT40 expects data/pilots on −58..−2 and +2..+58 (114 carriers); empty: −64..−59, −1, 0, +1, +59..+63 (14). The ESP-IDF text suggests ±57. `pipeline/preprocess.py` v1 uses the 114. **Never verified on real data** (`host/csi_inspect.py` was written for this but not run on real takes).
- Where the 64 L-LTF bins sit inside the 40 MHz band (likely the primary/upper 20 MHz, since secondary is below).
- Whether AGC gain steps occur (CSI amplitude jumps); per-packet mean normalisation is the current mitigation.

## 4. Host and repository

- Ubuntu 24.04.4, Python 3.12.3, venv `~/WiFi_CSI_Final/hostenv` (`host/requirements.txt`: pyserial, numpy, matplotlib, streamlit, scikit-learn, joblib).
- Repo: `~/WiFi_CSI_Final/wifi-csi-har` (the working copy). An **old unpacked zip** `~/Downloads/wifi-csi-har_2026-10-21_v2` exists — not used; data is NOT there.
- GitHub: `github.com/mohithgowdam7/Major_Project` — **not pushed yet** (needs a personal access token; never store it in a file). `data/`, raw `.bin`, models `.joblib` are git-ignored and must stay off GitHub.
- Bench recordings (outside the repo): `~/csi_runs/e0_second`, `e0_v2`, `e0_swap`, `lib_empty`, `lib_person` (link checks; not training data).

### Code that exists (written 21 Oct; tested mostly on synthetic data)
| File | Role | Status |
| --- | --- | --- |
| `host/csiwire.py` | frame decoder → header array + complex L-LTF(64)/HT-LTF(128) | verified on synthetic + live link |
| `host/rx_check.py` | live link check, E0 gates, `--save` | verified on hardware |
| `host/record_session.py` | plan-driven recording → Format 1 | used all day 22 Oct (bugs below) |
| `host/csi_inspect.py` | heatmaps, empty carriers, quality figures | synthetic only |
| `pipeline/preprocess.py` (v1, shared offline/live) | keep our TX, |H| on 114 carriers, align RX1/RX2 by TX seq, linear gap fill, per-packet mean normalisation, 200→100 Hz pair average, 2 s windows, gate ≤ 10 % missing & longest gap ≤ 20 packets | synthetic only |
| `pipeline/build_dataset.py` | state windows every 1 s (skip first/last 1 s); event windows: motion-energy peak in [cue, cue+4 s], 5 windows shifted −0.3..+0.3 s | synthetic only |
| `ml/features.py` (f1, 45 features) | band means, temporal std, change rate, PC1 power + band shares, RSSI | synthetic only |
| `ml/train.py`, `ml/predict.py` | LOSO random forest (state) + fall vs not_fall; `Predictor("models").predict(X[2,200,114], rssi[2,200])` | synthetic only |
| `app/engine.py`, `app/live_app.py` | live/replay engine + Streamlit dashboard (amplitude + sanitised phase heatmaps, trends, fall banner) | live_app never run in Streamlit; engine replay-tested on synthetic |
| `scripts/pipeline.sh` | `synth`, `dataset`, `train`, `demo`, `replay` | synthetic only |

### Known bugs found on 22 Oct (`host/record_session.py`)
1. A take with **0 CSI records** on a receiver is only flagged "BAD", and pressing `k` keeps it → 36 empty takes were kept by mistake (later moved to `_rejected`).
2. Typing `q` at the keep/redo prompt **keeps** the take and continues instead of quitting.
3. When a USB serial port disconnects, the reader thread dies with `SerialException` and the session silently records nothing for that RX afterwards (no reconnect, no abort).
4. File size is not a valid emptiness test: with the TX off, RX files still contain status frames (> 1 kB, no CSI). Use the `meta.json` check block.

## 5. Data formats (CONTRACTS, frozen 21 Oct; v1)

- **Format 1 — raw take:** `data/raw/<YYYYMMDD>_<subject>_<take_id>_<activity>[_rN]/RX1.bin, RX2.bin, meta.json`. `meta.json` has session_id, protocol, plan, take_id, kind (state|event), activity, position, subject (S1..S4 or none), setting, layout, operator_position, tx_power_dbm, duration_s, cue_s, start_local, instruction (the spoken text, incl. fall direction), valid, check {RX1/RX2: records, rate, loss_pct, max_gap_ms, rssi_median, crc_rejected, ok | error}, notes. `_rN` = redo kept. Rejected takes in `data/raw/_rejected/` (never used).
- **Format 2 — windows (v1):** `data/processed/windows_state.npz`, `windows_event.npz`, `index.csv`: `X` float16 [N, 2, 200, 114], `rssi` [N,2,200], `y`, `session_id`, `subject`, `position`, `t_start`, `miss_frac` [N,2], metadata. Split by subject/session, never random windows.
- **Format 3 — models:** `models/<task>_rf/model.joblib` + `model_meta.json`; `results/*.json`, `*_confusion.png`. Live call: `Predictor("models").predict(X, rssi)` → {label, confidence, probs, motion, fall_prob, uncertain}.
- Engine state for the UI: status ok|degraded|no_signal|error, label, label_smoothed (majority of last 3), confidence, uncertain, probs, motion, fall_prob, alert (FALL when 2 of last 3 windows have fall_prob ≥ 0.6, 10 s cooldown), rx health.

Changing a format = bump the version string (PREPROC_VERSION / FEATURES_VERSION) and record it in the decision log.

## 6. The dataset recorded on 22 Oct 2026 (verified counts)

**Place:** a library hall (large room, tile floor, big glass windows, glass wall to an adjacent room, metal chairs). Layout name `layout_library`, `setting same_room`, plywood NOT used. TX power **5 dBm** for every take. Channel 11 HT40.

**Geometry (metres; origin = floor under TX; +y towards the receivers; operator sits behind the receivers on the RX2 side):**
TX (0, 0) h 0.9 · RX1 (−1.3, 4.5) h 1.0 · RX2 (+1.3, 4.5) h 0.5 · chair spots A (−0.9, 3.2), B (+1.0, 1.5), C (0, 1.2) · mattress M x −0.5..1.5, y 2.9..3.8 (falls and lie; in front of RX1/RX2, slightly toward RX2) · **path1 x = −1.5, y 1.2..4.0 (ALONG the link, vertical)** · **path2 y = 2.55, x −2..2 (ACROSS the link, horizontal)** · free walk = taped area x −2.2..2.2, y −0.3..4.8 · operator O ≈ (3.0, 5.0) · spotter ≈ (2.0, 3.3). Boards were mounted on metal chairs.

> **Correction 2026-10-22 (Gate 0, from the operator's sketch `docs/setup/layout_library_sketch.jpg`):** earlier versions of this file had path1 and path2 swapped. The values above are corrected. The machine-readable source is `config/position_map.yaml` (version 2); `meta.json` files are unchanged (they only store the names `path1`/`path2`).

**Protocol (D-014):** state takes 30 s; event takes 10 s with an audio cue ("beep" + "now") at 3 s; subject still before the cue, one action, still until the end. Plans: `protocol/plan_subject_lib.csv` (39 takes: fall 10 incl. 2 optional backward falls, sit_down 8, stand_up 9, bend_pick 4, walk 3 [path1, path2, free], stand 2, sit 2, lie 1; interleaved order), `protocol/plan_short.csv` (22 takes: fall 5, sit_down 5, stand_up 5, bend_pick 2, walk 2, stand/sit/lie 1), `plan_empty.csv` (120 s), `plan_empty_short.csv` (30 s). Fall directions are in the `instruction` text (forward via knees, left side, right side, from walking).

| Subject | Takes | fall | sit_down | stand_up | bend_pick | walk | stand | sit | lie | Plan |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 37 | 8 | 8 | 9 | 4 | 3 | 2 | 2 | 1 | full (backward falls skipped) |
| S2 | 25 | 5 | 6 | 5 | 2 | 2 | 2 | 2 | 1 | 3 takes full + short |
| S3 | 22 | 5 | 5 | 5 | 2 | 2 | 1 | 1 | 1 | short |
| S4 | 37 | 8 | 8 | 9 | 4 | 3 | 2 | 2 | 1 | full (backward falls skipped) |
| none | 4 empty | | | | | | | | | 120 s + 3 × 30 s |
| **Total** | **125** | **26** | **27** | **28** | **12** | **10** | **7** | **7** | **4** | |

All 125 have CSI on both receivers (checked via `meta.json` 13:24). Bad/redone takes are in `data/raw/_rejected/`.

**Link quality notes:** phones on → RX2 loss 14 %; with phones in airplane mode RX1 ~2–6 %, RX2 ~4–10 %, gaps mostly ≤ 60 ms. **Body shadowing:** at spot A RX1 RSSI drops (−36 → −46 dBm); at spot B RX2 loss rises up to 35 % (S2 E58/E59/E60, S3 E47/E48, RX2 13–35 % loss). After the TX power cycle at ~12:45 loss fell to ~1–2 % on both (S4). Empty-room RSSI ≈ −36 (RX1), −38 (RX2).

**Incidents:** USB cables pulled (~11:20); RX1 native USB died silently (~11:50 → S2 re-recorded); TX power cut (~12:40). None affect the kept takes.

**No video ground truth.** Event timing = cue time + motion peak.

**Usage plan:** the 14:00 review model used S1–S3 only. The full analysis should use **S1–S4 with leave-one-subject-out (4 folds)**.

**Demo room ≠ recording room.** No data from the demo room was recorded.

## 7. Protocol research findings (summary of a literature check, 22 Oct)

- 10 s event takes with a 3 s pre-cue baseline match published practice (FallDeFi 10 s per action).
- **2 s windows are too short for 3–4 s transitions.** RT-Fall uses 3 s around the end of the motion; recent CSI fall work uses 5 s. → Compare 2 / 3 / 4 s windows.
- **Do not label every window of a fall take as "fall"** — most of the take is still standing or lying. Label by overlap with the action interval (motion-peak based).
- Repetitions: published fall datasets use 5–100 falls per subject; we have 5–8. Report per-take ("falls detected k of 26") as well as per-window metrics, with per-fold spread.
- ESP32 caveats: AGC not exposed (amplitude normalisation needed); raw phase has per-packet CFO/SFO and random offsets → **only sanitised phase** (unwrap + remove linear slope/offset across sub-carriers) or temporal phase differences are meaningful; the two RX boards are not phase-coherent.
- Leakage: never random window splits; fit scalers/feature selection/hyper-parameters inside training folds only (nested). Random-split accuracy is known to inflate results by 15+ points.
- Decimation 200 → 100 Hz needs an anti-alias low-pass first.
- Environment change between rooms can collapse accuracy (reported 99 % → 12 % in one study) → the live demo in a new room needs at least an empty-room baseline and ideally a few labelled calibration takes.

## 8. Decision register (in force)

Full register with later decisions: `docs/decisions/DECISIONS.md`.


D-006c boards · D-010 raw CSI (no merge/smoothing) · D-011 UART CRC rejects < 0.5 % · D-012 RX2 loss limit 3 % (bench) · D-013 scope · D-014 protocol (state 30 s, event 10 s, cue 3 s) · D-015 LOSO evaluation · D-016 keep the random forest unless a CNN is clearly better on LOSO · D-017 record on ch 11 at 5 dBm with relaxed keep rule (RX1 ≥ 180/s, ≥ 165 at spot A; RX2 ≥ 160/s, ≥ 150 at spot B; no gap > 100 ms).

## 9. Still open (not done)

E1 power sweep and plywood loss, E2 beamwidths (fall-on-floor coverage unverified), E3 empty-room stability (fans, doors), E4 grid sensitivity map, re-run A0 on the spare, fix `export.sh`, RX2 UART ISR on core 1, TX LED behaviour, GitHub push, `docs/setup/` photos and host setup doc.
