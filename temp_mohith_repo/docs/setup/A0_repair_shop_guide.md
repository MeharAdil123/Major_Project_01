# A0 external-antenna check: complete flow on any computer

**Purpose:** prove whether an ESP32-S3 board's radio uses its **external antenna (U.FL)** or its **printed PCB antenna**. Use it before and after the repair shop moves the antenna-select part.

**File:** `a0_antenna_check_v2_FLASH_AT_0x0.bin`, one file that is flashed at address **0x0**.
It was built with ESP-IDF v5.5.5 for ESP32-S3 with 16 MB flash, and the image layout was verified.

---

## 0. Before you start

- A USB-C cable that **carries data**. One that works for phone file transfer is a good bet.
- The board, with its antenna screwed on.
- **A reference Wi-Fi source:** turn on a **phone hotspot** and put the phone **2–3 m** from the board. Don't move it, or yourself, during the test.
- Use the board's **native USB** port, not the UART port:
  - **Windows:** Device Manager → Ports shows **"USB Serial Device (COMx)"** or **"USB JTAG/serial debug unit"**. The other port shows as **CH343 / USB-Enhanced-SERIAL** (that's the UART; don't use it).
  - **Linux:** `lsusb` shows `303a:1001 Espressif` for native USB, or `1a86:55d3` for the UART.
  - **Mac:** the native port appears as `/dev/cu.usbmodem…`.
  - Put a sticker next to the native USB port once you've found it.

## 1. Flash it: Option A, a browser, nothing to install (recommended)

Works in **Chrome or Edge** on Windows, Mac or Linux. Firefox and Safari won't work.

1. Open **https://espressif.github.io/esptool-js/**
2. In the **Program** section, set Baudrate to **460800**, then click **Connect** and choose the native USB port.
   - If it fails to connect: **hold BOOT, tap RST, release BOOT**, then click Connect again.
3. In the table, set Flash Address to **0x0** and choose the file `a0_antenna_check_v2_FLASH_AT_0x0.bin`.
4. Click **Program**. Wait for 100% and a "Leaving… / hard reset" message.
5. Click **Disconnect**.
6. In the **Console** section, set Baudrate to **115200**, click **Start** (or Connect), and choose the same port.
   - Scan lines appear every few seconds. If you joined late, just wait for the next scan line. Avoid pressing RST, because that briefly drops the USB link.

## 1. Flash it: Option B, Python esptool (if a browser doesn't work)

```bash
pip install esptool pyserial
esptool.py --chip esp32s3 -p PORT write_flash 0x0 a0_antenna_check_v2_FLASH_AT_0x0.bin
python -m serial.tools.miniterm PORT 115200
```

`PORT` is `COM5` (or similar) on Windows, `/dev/ttyACM0` on Linux, or `/dev/cu.usbmodem…` on Mac. Exit miniterm with **Ctrl+]**.

## 1. Flash it: Option C, our own Ubuntu laptop (full ESP-IDF, already installed)

```bash
cd ~/a0_antenna_check && . ~/esp/esp-idf-v5.5.5/export.sh
idf.py -p /dev/ttyACM0 flash monitor          # exit with Ctrl+]
```

Note: the laptop still has v1 source. To get v2, unzip `a0_antenna_check_v2_source.zip` over it, then run `idf.py build` before flashing. The verdict logic is the same; v2 only ignores weak networks and shows a live reading.

---

## 2. Run the test

1. **At start-up the LED shows red, then green, then blue.** No LED at all is OK; it doesn't affect the test.
2. The screen prints the MAC and `Flash 16 MB`. Note the **MAC**.
3. **Phase A (antenna ON):** keep still. Each scan prints `strongest now: <name> <RSSI> dBm`, and the hotspot should be the strongest. After **at least 5 scans**, press **BOOT**.
4. The LED turns **white**. **Within 10 s, unscrew the antenna at the SMA end, not the tiny U.FL.**
5. **Phase B (antenna OFF):** wait about 30 s. A table and a **VERDICT** appear, and the LED changes colour.
6. To repeat: screw the antenna back on, then press **BOOT**, which restarts phase A.

## 3. Read the result

| What you see | Meaning |
| --- | --- |
| `strongest now` drops by **15 dB or more** when unscrewed (e.g. −40 → −62) and stays down. **VERDICT: U.FL / EXTERNAL antenna. Good.** LED green. | ✅ The external antenna is in use. |
| Signal changes by only **0 to ±5 dB**. **VERDICT: PCB antenna.** LED red. | ❌ Still the PCB antenna. The fix isn't done. |
| **Inconclusive** (−15 to −5 dB) or "Only N networks". LED yellow. | Repeat with the hotspot at 2–3 m and nobody moving. |

Brief jumps of ±5–10 dB when a hand comes near the board are normal. Judge the value **after** your hand has moved away.

---

## 4. What to ask the repair technician

- These modules have **both** a printed PCB antenna **and** a U.FL connector. The radio is currently routed to the **PCB antenna**, as A0 showed with a median change of 0 dB.
- **Ask:** move the RF-path selector (usually a **0 Ω resistor** or solder bridge on **three small pads, in a "<" shape, next to the U.FL connector**) from the **PCB-antenna position** to the **U.FL position**.
- If no selector is visible outside the metal shield, it may be **under the shield**. Lifting the shield needs hot air and carries a risk of damaging the module. **Decide with them whether it's worth it.** The alternative is buying **ESP32-S3-WROOM-1U** boards, which have U.FL only.
- Don't let them overheat the U.FL connector. It's rated for only about 30 plug/unplug cycles, so unplug it as rarely as possible.
- **Check on the spot:** run A0 on each board **before** and **after** the change, with the same place, the same hotspot position and the same antenna. Pass means a drop of **15 dB or more** and **VERDICT: EXTERNAL**.

## 5. Boards (fill in at the shop)

| Board | Module marking | MAC | A0 before | A0 after |
| --- | --- | --- | --- | --- |
| TX (odd one) | | | PCB (AC:27:6E:A4:4E:30, if confirmed) | |
| RX1 (Sixspan) | | | PCB (28:84:85:85:5E:2C, if confirmed) | |
| RX2 (Sixspan) | | 28:84:85:48:D7:DC | not run | |
