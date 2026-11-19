# TX setup: ESP-WROOM-32U NodeMCU board (classic ESP32)

Goal: get the transmitter working as a standalone device. It does three things and is checked in three steps:

| Step | What it proves | Pass |
| --- | --- | --- |
| **T-A0** antenna check | The radio really uses the patch antenna (U.FL) | Removing the antenna drops the signal by **≥ 15 dB** |
| **T-FW** flash the TX firmware | The board transmits 200 packets/s at HT40, MCS0, 2 dBm | `HELLO` shows `"radio_ok":true`, `"rate_cfg":"ESP_OK"`, `"bw":2` |
| **T0** 60 s self-test | It keeps up without errors | `STATS`: rate 190–210/s, `fail`/`nomem` not increasing, `late` < 1 % of `seq` |

Files (all built with ESP-IDF v5.5.5; compiled and image layout verified; **not yet run on hardware**):

- `A0_esp32_FLASH_AT_0x0.bin`: antenna check for the **classic ESP32 TX**
- `A0_esp32s3_FLASH_AT_0x0.bin`: the same check for the **S3 receivers** (used later)
- `csi_tx_esp32_FLASH_AT_0x0.bin`: the **TX firmware**
- `csi_tx_source.zip`, `a0_antenna_check_v3_source.zip`: source code, for rebuilding or changing settings

---

## 0. One-time: connect the board

The NodeMCU board has **one** micro-USB or USB-C port, connected to a USB-to-UART chip (CP2102 or CH340). There is no "native USB" choice to make, unlike the S3 boards.

**Ubuntu:** plug in, then run:
```bash
lsusb | grep -iE "10c4|1a86"
ls /dev/ttyUSB*
```
- `10c4:ea60` means CP2102, and `1a86:7523` means CH340. The port is normally **`/dev/ttyUSB0`**. Note `ttyUSB`, not `ttyACM`.
- If `ls` shows nothing: `brltty` must be removed (`sudo apt-get remove -y brltty`) and you must be in `dialout` (both were done on the first laptop). Also try another cable.

**Windows:** Device Manager → Ports shows "Silicon Labs CP210x … (COMx)" or "USB-SERIAL CH340 (COMx)". If it shows as an unknown device, install the driver: Silicon Labs "CP210x VCP driver" or WCH "CH341SER". Note the **COM** number.

## 1. T-A0: antenna check on the TX

Screw the **patch antenna** on, and put a phone hotspot 2–3 m away.

**Ubuntu** (with ESP-IDF already installed; the `.bin` is in Downloads):
```bash
. ~/esp/esp-idf-v5.5.5/export.sh
cd ~/Downloads
esptool.py --chip esp32 -p /dev/ttyUSB0 -b 460800 write_flash 0x0 A0_esp32_FLASH_AT_0x0.bin
python -m serial.tools.miniterm /dev/ttyUSB0 115200
```

**Windows** (Python + esptool installed as before):
```
cd %USERPROFILE%\Downloads
python -m esptool --chip esp32 -p COM5 -b 460800 write_flash 0x0 A0_esp32_FLASH_AT_0x0.bin
python -m serial.tools.miniterm COM5 115200
```

If flashing cannot connect: hold **BOOT** (sometimes labelled IO0), tap **EN** (reset), release BOOT, and retry.
Opening miniterm may reset the board. That is normal: the test then starts from the beginning.

Run the test as before:
1. Note the **MAC** and **Flash** lines. The LED should light for 3 s. That confirms the LED pin, which is GPIO2.
2. Keep still for 5 or more scans (`strongest now: …`), then press **BOOT**.
3. **Within 10 s, unscrew the patch antenna** at the RP-SMA end, never at the U.FL.
4. Wait about 30 s and read the **VERDICT**.
5. Exit with **Ctrl + ]**, then screw the antenna back on.

On this board the LED is single-colour, so it only shows on/off. **Read the verdict on screen.**

Expected: **"U.FL / EXTERNAL antenna"**. The WROOM-32U has no PCB antenna, so with the antenna off the signal should collapse (or networks are "lost").
If it says PCB or inconclusive, check the pigtail is clicked fully onto the U.FL, and that the RP-SMA genders match (the centre pin must touch).

## 2. T-FW: flash the TX firmware

**Ubuntu:**
```bash
cd ~/Downloads
esptool.py --chip esp32 -p /dev/ttyUSB0 -b 460800 write_flash 0x0 csi_tx_esp32_FLASH_AT_0x0.bin
python -m serial.tools.miniterm /dev/ttyUSB0 115200
```
**Windows:**
```
python -m esptool --chip esp32 -p COM5 -b 460800 write_flash 0x0 csi_tx_esp32_FLASH_AT_0x0.bin
python -m serial.tools.miniterm COM5 115200
```

You should see a `HELLO` line within a second, then one `STATS` line per second. In the `HELLO` line, check:

| Field | Must be | If not |
| --- | --- | --- |
| `"radio_ok"` | `true` | Send me the lines; the radio did not start |
| `"rate_cfg"` | `"ESP_OK"` | The PHY rate/HT40 was not forced, so frames go out at 1 Mbps. Send me the line |
| `"channel"` / `"second"` | `11` / `2` (2 = secondary below) | — |
| `"bw"` | `2` (= HT40) | `1` means the driver fell back to HT20 |
| `"tx_power_dbm"` | `2.00` | — |

LED: **solid** while starting, then **slow blink (1 per second)** = transmitting normally. **Fast blink** = radio problem.

## 3. T0: 60-second self-test

Leave miniterm running for 60 s and look at the `STATS` lines:

| Field | Pass |
| --- | --- |
| `rate` | 190–210 packets/s |
| `fail`, `nomem` | stay at 0, or stop increasing |
| `late` | under 1 % of `seq` (for example under 120 after 60 s) |
| `seq` | grows by about 200 each second |

## 4. TX power command (for E1 later)

With miniterm open, type and press Enter:
```
power 5
status
```
- `power <dBm>` accepts 2–20. The reply is `OK power asked … set …`. The next `STATS` lines show the new `tx_power_dbm`.
- The setting is **not saved**: unplugging or resetting returns to 2 dBm.
- Every packet also carries the power used, so the receivers record it automatically.

## 5. Standalone use

Unplug from the laptop and power the board from a **USB power bank or wall adapter**, using the same port. It starts transmitting by itself in about 1 second (the slow blink).
If the LED stops blinking after a while on a power bank, the bank has switched itself off at low current. Use a wall adapter or a bank with an "always on" mode.

## Send back

1. The A0 output: MAC, Flash, the final table and the VERDICT.
2. The first `HELLO` line from the TX firmware.
3. About 5 `STATS` lines taken after 60 s.
4. What the LED did (solid → slow blink?).

## Settings are fixed in the firmware

Channel 11, HT40 with the secondary below, MCS0 long GI, 200 packets/s, 32-byte payload, start-up power 2 dBm, LED on GPIO2.
To change any of them, edit `idf.py menuconfig` → "CSI transmitter" in `csi_tx_source.zip` and rebuild (`idf.py set-target esp32`, then `idf.py build`).
