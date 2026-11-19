# RX setup and first link test (E0)

**Setup:** the TX runs standalone on a power bank or adapter. RX1 and RX2 are connected to the laptop and stream CSI to it.

| Board | MAC | Link to laptop | Firmware file | Fixed port name |
| --- | --- | --- | --- | --- |
| RX1 (Sixspan #1) | 28:84:85:85:5E:2C | **Native USB** | `csi_rx_RX1_FLASH_AT_0x0.bin` | `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:85:5E:2C-if00` |
| RX2 (Sixspan #2) | 28:84:85:48:D7:DC | **UART port** (CH343), 2 Mbaud | `csi_rx_RX2_FLASH_AT_0x0.bin` | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C38144809-if00` |

Laptop tool: `rx_check.py`. It reads both receivers, shows live numbers and scores E0.
All files were built with ESP-IDF v5.5.5 and compile without warnings. The decoder and record layout are tested on the PC. **Nothing has run on the boards yet.**

## 0. Prepare (every new terminal)

```bash
alias espy=~/.espressif/python_env/idf5.5_py3.12_env/bin/python
cd ~/Downloads
RX1=/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:85:5E:2C-if00
RX2=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C38144809-if00
ls -l $RX1 $RX2
```

Both lines must show a link (`-> ../../ttyACM…`). Close any open miniterm: only one program can use a port at a time.

## 1. Flash RX1 (native USB)

```bash
espy -m esptool --chip esp32s3 -p $RX1 write_flash 0x0 csi_rx_RX1_FLASH_AT_0x0.bin
```

Check that the flashing output shows **MAC 28:84:85:85:5E:2C** and ends with "Hash of data verified".

## 2. Flash RX2 (UART port)

```bash
espy -m esptool --chip esp32s3 -p $RX2 write_flash 0x0 csi_rx_RX2_FLASH_AT_0x0.bin
```

Check that the flashing output shows **MAC 28:84:85:48:D7:DC** and ends with "Hash of data verified".

## 3. Place the boards for E0

- **TX:** power it from a power bank or adapter, patch antenna on, about **1 m** from the receivers and facing them.
- **RX1 and RX2:** omni antennas upright, side by side, both still connected to the laptop.
- **RX LEDs:** a short **green** blink every second means TX packets are arriving. **Red** means none arrived. **Purple** means the radio didn't start.

## 4. Run the check (60 s)

```bash
espy rx_check.py --seconds 60 --save ~/csi_runs/e0_first
```

You'll see one line per second for each receiver: packets/s, % at 40 MHz (HT40), RSSI, CSI length and loss. Then an **E0 summary**:

| Check | Pass |
| --- | --- |
| rate | ≥ 190 packets/s on each RX |
| loss | < 2 % |
| HT40 | ≥ 95 % of packets at 40 MHz. **This is the open question from the TX** |
| TX settings match | 0 frames with another radio_id |
| no drops on board/link, no corrupt frames | all 0 |
| seen by both | ≥ 95 % of packets received by both RX1 and RX2 |

At 1 m, RSSI will be very high (around −20 to −30 dBm). That's expected for a bench test; we tune the power in E1.

## If something fails

- **"RX1 not found" / "RX2 not found":** check `ls -l /dev/serial/by-id/`. If the cable or port moved, use `--rx1 PORT` or `--rx2 PORT`.
- **RX2 shows CRC errors or 0 packets, but its LED blinks green:** the 2 Mbaud UART speed may be too fast for this link. Tell me, and I'll send a slower RX2 build.
- **HT40 is 0 %** (everything at 20 MHz): the classic-ESP32 TX isn't really sending at 40 MHz. We'd switch both sides to HT20 (one setting each).
- **A red LED on both receivers:** check that the TX is powered and blinking.

## Send back

The whole terminal output of step 4, especially the E0 summary. Also keep the `~/csi_runs/e0_first` folder: it holds the raw data.
