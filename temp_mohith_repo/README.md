# WiFi-CSI HAR: camera-free activity sensing with Wi-Fi CSI

Camera-free human activity recognition with Wi-Fi Channel State Information (CSI). One ESP32 transmitter broadcasts 200 packets/s. Two ESP32-S3 receivers measure the channel (CSI) of every packet and stream it to a laptop, which recognises:
- **presence** (empty / occupied);
- **states** (sit, stand, walk, lie);
- **events** (fall, sit_down, stand_up; bend_pick as a fall look-alike).

A live dashboard shows the result every 0.5 s.

**Status (2026-10-23, v1.0):** complete. 202 takes from 6 volunteers were recorded in one room on 22 Oct 2026 and evaluated leave-one-subject-out. Final models and the live dashboard were tested on the boards. Results: [`results/REPORT.md`](results/REPORT.md). Decisions: [`docs/decisions/DECISIONS.md`](docs/decisions/DECISIONS.md). Final status: [`docs/STATUS.md`](docs/STATUS.md).

## Results in brief
Leave-one-subject-out, 6 folds, 4 s windows, dynamic features (`results/REPORT.md` §1–8):

| Task | Final model | Macro-F1 (mean ± std over subjects) |
| --- | --- | --- |
| presence (empty / occupied) | logistic regression | 0.698 ± 0.065 |
| state (sit / stand / walk / lie) | extra trees | 0.572 ± 0.115 |
| events (fall / sit_down / stand_up / bend_pick / none) | SVM-RBF | 0.539 ± 0.054 |
| fall alarm (calibrated SVM, ≥ 2 of 3 windows with P ≥ 0.5) | — | 21 of 42 falls; alarms on 8 of 109 look-alike movements |

**Live test (`results/REPORT.md` §10):**
- The system ran end to end on the boards: 0.5 s steps, receiver reconnect, environment check, logging.
- Walking across the link was recognised.
- Accuracy did not carry over to a new day: presence on the empty room was fragile, the fall gave no alarm, and walking gave 2 false alarms.

The LOSO numbers above are the evaluation. **Limits:** one room and layout, 6 volunteers, falls simulated on a mattress at one spot, no video ground truth, not clinically validated.

## System

```
TX (ESP32, ch 11 HT40, 200 packets/s) ─► RX1 + RX2 (ESP32-S3, CSI) ─USB─► laptop
  host/record_session.py      labelled takes (plan CSV)          data/raw/<take>/            Format 1
  pipeline/build_dataset.py   align, clean, gate, windows        data/processed/*.npz        Format 2
                              + features (ml/features.py, f2)    data/features/*.csv
  ml/evaluate.py + scripts/phase4_*.py   leave-one-subject-out model comparison   results/phase4/
  ml/train_final.py           final models on all subjects       models/<task>/              Format 3
  app/engine.py + app/live_app.py        live inference + Streamlit dashboard     logs/live_*.jsonl
```
`pipeline/preprocess.py` is shared by the offline and live paths. Formats and interfaces: [`docs/CONTRACTS.md`](docs/CONTRACTS.md). Features: [`docs/FEATURES.md`](docs/FEATURES.md).

## Hardware

| Role | Board | MAC | Antenna | Link to PC |
| --- | --- | --- | --- | --- |
| TX | ESP32 NodeMCU, ESP-WROOM-32U | 20:9B:A9:68:F3:F0 | 8 dBi patch, V-pol | standalone on a USB power adapter; serial only for flashing and commands |
| RX1 | ESP32-S3-N16R8 (RF path moved to U.FL) | 28:84:85:85:5E:2C | 6 dBi omni, vertical | native USB |
| RX2 | same as RX1 | 28:84:85:48:D7:DC | 6 dBi omni, vertical | UART bridge (CH343), 2 Mbaud |

Radio: channel 11, HT40 (secondary below), MCS0 long GI, ESP-NOW broadcast with a 32-byte payload (magic, sequence number, TX time, radio id, TX power). TX power 5 dBm (stored on the board). Room layout: [`config/position_map.yaml`](config/position_map.yaml), sketch [`docs/setup/layout_library_sketch.jpg`](docs/setup/layout_library_sketch.jpg). Step-by-step board guides: [`docs/setup/`](docs/setup/).

**Check each U.FL antenna connector by hand before a session.** A badly mated connector made RX2 almost blind to motion in the live test (D-060).

## 1. Setup (Ubuntu 24.04, Python 3.12)

```bash
python3 -m venv ../hostenv
../hostenv/bin/pip install -r requirements.txt     # torch from https://download.pytorch.org/whl/cpu
```
```bash
sudo usermod -aG dialout $USER                      # serial ports (log out and in again)
```
USB autosuspend off for the receivers: [`setup/linux/README.md`](setup/linux/README.md).

Firmware (prebuilt images, flash at 0x0, checksums in `releases/v2/SHA256SUMS`):
```bash
alias espy=~/.espressif/python_env/idf5.5_py3.12_env/bin/python
espy -m esptool --chip esp32   -p /dev/ttyUSB0 write_flash 0x0 releases/v2/csi_tx_v2_esp32_FLASH_AT_0x0.bin
espy -m esptool --chip esp32s3 -p /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:85:5E:2C-if00 write_flash 0x0 releases/v2/csi_rx_v2_RX1_FLASH_AT_0x0.bin
espy -m esptool --chip esp32s3 -p /dev/serial/by-id/usb-1a86_USB_Single_Serial_5C38144809-if00 write_flash 0x0 releases/v2/csi_rx_v2_RX2_FLASH_AT_0x0.bin
```
Building from source (ESP-IDF v5.5.5): `firmware/tx` (target esp32), `firmware/rx` with `sdkconfig.rx1` / `sdkconfig.rx2` (target esp32s3); see [`docs/setup/`](docs/setup/) and `scripts/fw_build.sh`.

**RF hygiene (D-032):** during recording and live use, switch the laptop's Wi-Fi and Bluetooth off and put phones in airplane mode.

## 2. Check the link
```bash
../hostenv/bin/python host/rx_check.py --seconds 60
```
Expect about 190–200 packets/s per receiver, 100 % HT40, RSSI about −36 to −39 dBm (22 Oct levels).

## 3. Record
Protocol and durations: [`docs/PROTOCOL.md`](docs/PROTOCOL.md). One command per block (spoken instructions via `spd-say` if installed):
```bash
../hostenv/bin/python -m host.record_session --plan protocol/plan_empty.csv --subject none --setting same_room --layout layout_library --operator-position O --tx-power 5
```
```bash
../hostenv/bin/python -m host.record_session --plan protocol/plan_subject_lib.csv --subject S1 --setting same_room --layout layout_library --operator-position O --tx-power 5
```
Takes go to `data/raw/<date>_<subject>_<take>_<activity>/` (RX1.bin, RX2.bin, meta.json). **Raw data is read-only** ([`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md)); corrections go in `config/take_overrides.csv`.

## 4. Pipeline (one command per step)
All steps go through `scripts/pipeline.sh`, run from the repo root:

| Step | Command | Output | Time (i3-7020U) |
| --- | --- | --- | --- |
| Raw-data audit (read-only) | `scripts/pipeline.sh audit` | counts, decode, RSSI drift | 7 s |
| Dataset (2, 3, 4 s windows) | `scripts/pipeline.sh dataset` | `data/processed`, `data/features` | 4 s alone: 6.5 min (earlier builds under load: 11–41 min per length) |
| Model comparison (LOSO, all tracks) | `scripts/pipeline.sh phase4` | `results/phase4/` | ~7 h, resumable |
| Final models | `scripts/pipeline.sh train` | `models/` | 38 s |
| Live = offline check | `scripts/pipeline.sh consistency` | `results/phase5/consistency.log` | 3 min |
| Unit tests | `scripts/pipeline.sh test` | 93 tests | 35 s |
| **Reproduction from raw data** | `scripts/pipeline.sh reproduce` | `results/reproduction/` | 11 min |

`reproduce` does the following:
- verifies the raw files against `results/audit/raw_sha256.txt`;
- runs the audit;
- rebuilds the 4 s dataset from `data/raw` and retrains the final models, both in a scratch folder;
- compares both with the committed `data/features` and `models/`;
- runs the live = offline check and the tests.

It never overwrites the committed outputs. Result on 2026-10-23 (`results/reproduction/compare.log`): rebuilt features identical (max difference 0), retrained models give identical labels and probabilities on all 2401 windows, live = offline identical. The full model comparison (`phase4`, ~7 h) is not part of it. Evaluation rules: leave-one-subject-out only, nested search, empty-room takes dealt to folds take by take (project rule 6).

## 5. Live dashboard
```bash
scripts/pipeline.sh demo                          # boards (Wi-Fi + Bluetooth off)
```
```bash
scripts/pipeline.sh replay "*S6_E2*"              # replay recorded takes, no boards (in-sample demo)
```
Workflow:
1. Start with the room empty and run the 60 s **environment check**. It compares the room with the training empty rooms and warns if predictions are unreliable.
2. Use the **Test markers** to log what is being done.

The engine runs in its own process and writes predictions and health (never raw CSI) to `logs/live_*.jsonl`. Analysis of a marked session:
```bash
../hostenv/bin/python scripts/phase5_live_analysis.py logs/live_<time>.jsonl
```

## Repository layout
```
firmware/{tx,rx}/   ESP-IDF firmware        releases/v2/   prebuilt images      tools/a0_antenna_check/
host/               serial decoding, link check, recorder, CSI inspection
pipeline/           preprocessing (shared offline/live), onset detection, labels, dataset builder
ml/                 features (f2), classical/MiniRocket/deep models, LOSO evaluation, final training, Predictor
app/                live engine, engine process, environment check, Streamlit dashboard
scripts/            pipeline.sh (entry point), reproduction, phase analyses
config/             layout, take overrides, expected dataset counts
protocol/           recording plans (CSV)
tests/              unit tests; tests/synthetic/ = SYNTHETIC data generators for tests only
results/            REPORT.md, phase results and logs (logs are kept locally, not in git)
docs/               PROJECT_RULES, CONTRACTS, FEATURES, PROTOCOL, AUDIT, decisions/, setup/, firmware/, analysis/, context/, history/
data/, models/      recordings and trained weights (local only, not in git)
```

## Privacy
Raw CSI recordings stay on the local machine; they are not committed or uploaded anywhere. Live logs contain predictions only.

## Acknowledgements
AI assistance (Claude, by Anthropic) was used during this project for code generation and documentation. The project team is responsible for the design decisions, the hardware set-up, data collection, validation of the results and the conclusions drawn from them.
