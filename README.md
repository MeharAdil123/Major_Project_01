# WiFi-CSI HAR: privacy-preserving through-wall activity sensing

Camera-free human sensing with Wi-Fi Channel State Information (CSI). One ESP32 transmitter broadcasts known packets; two ESP32-S3 receivers measure the channel (CSI) of every packet and stream it to a host PC.

**Status (2026-10-21):** RF chain verified on the bench (about 196–198 packets/s per receiver, 100 % HT40). The full pipeline (recording → dataset → model → live dashboard) is implemented and tested on synthetic data; real data collection is on 2026-10-22. Full state: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md). Team plan: [`docs/TEAM_PLAN.md`](docs/TEAM_PLAN.md).

## Pipeline

```
TX (ESP32, 200 packets/s) ─► RX1 + RX2 (ESP32-S3, CSI) ─► laptop
  host/record_session.py   labelled takes            data/raw/<take>/        (Format 1)
  pipeline/build_dataset.py  align, clean, windows   data/processed/*.npz    (Format 2)
  ml/train.py               features + random forest, leave-one-subject-out  models/, results/ (Format 3)
  app/engine.py + live_app.py  live inference + dashboard
```
Formats: [`docs/CONTRACTS.md`](docs/CONTRACTS.md). Recording protocol: [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r host/requirements.txt
scripts/pipeline.sh synth      # test everything on synthetic data (no hardware)
scripts/pipeline.sh dataset    # real takes -> windows
scripts/pipeline.sh train      # windows -> models + results
scripts/pipeline.sh demo       # live dashboard on the boards
```

## Hardware

| Role | Board | MAC | Antenna | Link to PC |
| --- | --- | --- | --- | --- |
| TX | ESP32 NodeMCU, ESP-WROOM-32U (classic ESP32) | 20:9B:A9:68:F3:F0 | 8 dBi patch, V-pol | None (standalone on a power bank); USB-UART only for flashing and commands |
| RX1 | YD-style ESP32-S3-N16R8 (Sixspan, RF path moved to U.FL) | 28:84:85:85:5E:2C | 6 dBi omni, vertical | Native USB |
| RX2 | Same as RX1 | 28:84:85:48:D7:DC | 6 dBi omni, vertical | UART port (CH343), 2 Mbaud. Its native USB is faulty |

## Radio settings

Channel 11, HT40 (secondary channel below), MCS0 long GI, 200 packets/s ESP-NOW broadcast with a 32-byte payload (magic, sequence number, TX time, radio_id, TX power). The TX boot power is stored on the board (currently 5 dBm).

## Repository layout

```
firmware/tx/                 csi_tx: TX firmware (ESP-IDF v5.5.5, target esp32)
firmware/rx/                 csi_rx: RX firmware (target esp32s3); sdkconfig.rx1 / sdkconfig.rx2 select the link
host/rx_check.py             reads RX1+RX2, live view, E0 checks, --save raw streams
host/csiwire.py              decoder for saved runs (wire protocol v2, CSI layout)
host/csi_inspect.py          Phase 5 figures: heatmaps, channel shape, quality checks
host/record_session.py       labelled recording of takes (plan CSV -> data/raw)
host/tests/                  synthetic run/dataset generators for testing
protocol/                    recording plans (CSV)
pipeline/                    preprocessing (shared offline/live) and dataset builder
ml/                          features, training + evaluation, Predictor interface
app/                         live engine and Streamlit dashboard
scripts/pipeline.sh          one entry point for all steps
docs/analysis/               Phase 5 notes
docs/tracks/                 per-person work briefs
tools/a0_antenna_check/      A0 antenna-path test (esp32 and esp32s3)
releases/v2/                 prebuilt merged images, flash at 0x0 (see SHA256SUMS)
docs/setup/                  TX / RX / A0 step-by-step guides
docs/firmware/               wire protocol v2
docs/PROJECT_STATE.md        phase status, board register, test results, decisions
```

## Quick start (Ubuntu)

```bash
alias espy=~/.espressif/python_env/idf5.5_py3.12_env/bin/python    # ESP-IDF v5.5.5 Python
espy -m esptool --chip esp32   -p /dev/ttyUSB0 write_flash 0x0 releases/v2/csi_tx_v2_esp32_FLASH_AT_0x0.bin
espy -m esptool --chip esp32s3 -p /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:85:5E:2C-if00 \
     write_flash 0x0 releases/v2/csi_rx_v2_RX1_FLASH_AT_0x0.bin
espy -m esptool --chip esp32s3 -p /dev/serial/by-id/usb-1a86_USB_Single_Serial_5C38144809-if00 \
     write_flash 0x0 releases/v2/csi_rx_v2_RX2_FLASH_AT_0x0.bin
espy host/rx_check.py --seconds 60 --save ~/csi_runs/my_run
```

## Building from source (ESP-IDF v5.5.5)

```bash
. ~/WiFi_CSI_Final/esp/esp-idf-v5.5.5/export.sh      # first: ./install.sh esp32,esp32s3
cd firmware/tx && idf.py set-target esp32 && idf.py build
cd ../rx && idf.py -B build_rx1 -D SDKCONFIG=build_rx1/sdkconfig -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rx1" set-target esp32s3 build
cd ../rx && idf.py -B build_rx2 -D SDKCONFIG=build_rx2/sdkconfig -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rx2" set-target esp32s3 build
```

## Privacy

Raw CSI recordings stay on the local machine (`csi_runs/` is git-ignored) and are not uploaded anywhere.
