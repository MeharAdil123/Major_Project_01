# Phase 1 — firmware review, builds, recorder fixes (2026-10-22)

Nothing was flashed. No serial port was opened (sysfs was only read). The v2.1 patches are on branch `cc/phase1` and are proposals until you approve flashing.

## 1. Review of `firmware/tx` and `firmware/rx` against `wire_protocol_v2.md`

| Item | Spec | Code | Verdict |
| --- | --- | --- | --- |
| Channel / bandwidth | ch 11, HT40, secondary below | TX `esp_wifi_set_channel(11, BELOW)` + `set_bandwidth(HT40)`; RX same | ✔ |
| PHY rate | HT40 MCS0 long GI, not 802.11b | TX `esp_now_set_peer_rate_config(BCAST, {HT40, MCS0_LGI})`, checked at boot (`rate_cfg` in HELLO) | ✔ |
| Packet rate | 200 Hz | `esp_timer` period 5000 µs → task notify; late wake-ups counted, no burst catch-up | ✔ |
| TX payload | 24 B header in 32 B | identical packed struct in TX and RX (`tests/test_wire_contract.py`) | ✔ |
| radio_id | 0xCBD36978 | same fingerprint string on TX and RX; CRC-32 recomputed in a test = 0xCBD36978 | ✔ |
| CSI config | L-LTF + HT-LTF (+STBC2), no merge, no smoothing (D-010) | `lltf_en, htltf_en, stbc_htltf2_en = true; ltf_merge_en, channel_filter_en = false` | ✔ |
| Record header | 48 B, fields as in the doc | packed struct + static assert; field order and types equal `host/csiwire.py` (test) | ✔ |
| Frame + CRC | A5 5A, type, len ≤ 2048, CRC-16/CCITT-FALSE over type..payload | `link.c crc16_ccitt` == Python `binascii.crc_hqx` (test, check value 0x29B1) | ✔ |
| Filtering | keep only our TX | MAC filter (Kconfig TX MAC) + magic search; radio mismatch flagged, not dropped | ✔ |
| Queueing | CSI callback must not block | static item, `xQueueSend(…, 0)`, depth 64 (≈ 52 KB), drops counted (`q_drop`) | ✔ |
| Writer | separate task | `csi_wr` pinned to core 1, priority 5 | ✔ |
| Error handling | — | init uses `ESP_ERROR_CHECK` (abort → reboot loop on failure); USB link stops waiting after a timed-out write | ✔ (see W3) |
| NVS power save | `power <dBm> save` survives reboot | `nvs_set_i8("pwr_qdbm")` + commit; read back and range-checked at boot; `power default` erases | ✔, but see F2 |

Build reproducibility: rebuilding the **unchanged v2 source** (commit e765966) with the installed toolchain gives images **bit-identical** to `releases/v2/` (SHA-256 below). So the boards run exactly the reviewed code.

## 2. Findings → fixes

| # | Issue | Severity | Fix (v2.1, on branch) | Status |
| --- | --- | --- | --- | --- |
| F1 | RX2's UART driver (and RX1's USB-Serial-JTAG driver) is installed from `app_main`, so **its interrupt runs on core 0 next to the Wi-Fi task**. This is the plausible cause of RX2's extra 1–1.5 % loss (D-012). | M | `link_init()` now runs in a short task pinned to core 1; the interrupt is allocated on the installing core. HELLO reports `link_core: 1`. | built, **not flashed**, effect unmeasured |
| F2 | TX build-default power is **2 dBm** (`TX_POWER_QDBM=8`); the 5 dBm used for every take lives only in NVS. Any NVS erase (`erase_flash`, or `nvs_flash_init` hitting NO_FREE_PAGES) would silently change the radio of the study. | M | Kconfig default 20 (= 5 dBm, D-017). The NVS value still overrides it. | built, not flashed |
| F3 | No TX liveness signal: a stuck TX task or a stopped timer gives silence with no reboot and no reason. | M | Task watchdog on the transmit task (5 s, panic → reboot). Receivers then see the seq restart, which the host already splits on. | built, not flashed |
| F4 | After a power cut or reboot nobody can tell why a board restarted. | L | `reset` (poweron/brownout/task_wdt/…) and `uptime_s` added to the HELLO of TX and RX. Wire format unchanged. | built, not flashed |
| F5 | TX power cut during a take is detected only after the take. | M | Host side: the recorder now auto-rejects takes with no CSI on either RX, and aborts on a silent port (recorder bugs 1 and 3). The RX LED already shows red when no TX frames arrive. | done + tested |
| W3 | RX1 native USB dropped twice on 22 Oct. The firmware side is already defensive (it stops waiting when the host does not read). Possible host causes: cable or hub, and USB autosuspend (global setting = 2 s on this laptop; `cdc_acm` normally holds the device awake while the port is open, so this is unlikely but not excluded). | M | Host: the recorder reconnects by `/dev/serial/by-id`. Phase 5 engine: the same. Optional: a udev rule to disable autosuspend for 303a:1001 (needs sudo; I will ask before doing it). | recorder done; engine in Phase 5 |
| F6 | Note on F3: `CONFIG_ESP_TASK_WDT_PANIC=y` also turns any idle-task starvation (≥ 5 s) into a reboot. v2 showed no such warnings in the bench logs I have seen, but the TX UART was not logged during recording. | L | Accept, or set `CHECK_IDLE_TASK` off if you prefer. | open |
| D | Docs: `csi_wire.h` and the RX header comment pointed to `tools/rx_check.py`; the wire-protocol doc said "ordering decoded in Phase 5". | L | Updated. | done |

Not changed on purpose: wire format (version byte stays 2), CSI config, rate, channel, queue sizes, LED colours.

## 3. ESP-IDF toolchain

`export.sh` fails only because `riscv32-esp-elf-gdb` (a debugger) is missing. Every compiler IDF v5.5.5 needs is installed: xtensa-esp-elf 14.2.0_20260121, riscv32-esp-elf 14.2.0_20260121, esp32ulp-elf 2.38, esp-rom-elfs 20241011, and system cmake 3.28.3 / ninja 1.11.1.
- **The proper repair** (downloads the missing tools, needs internet; not run):
  `cd ~/WiFi_CSI_Final/esp/esp-idf-v5.5.5 && ./install.sh esp32,esp32s3`
- Workaround used here, no download: `scripts/fw_build.sh tx|rx1|rx2 OUTDIR` puts the installed compilers on PATH and calls `idf.py` with an out-of-tree build dir and sdkconfig. It never flashes.

## 4. Builds
All six builds (v2 rebuilt from e765966, and v2.1) finish with **0 warnings and 0 errors**. The v2 rebuilds are bit-identical to `releases/v2`. Table and hashes: `results/firmware/BUILDS.md`.

## 5. Recorder (`host/record_session.py` v1.1)

| Bug | Fix | Test (`tests/test_record_session.py`, simulated ports) |
| --- | --- | --- |
| 1: 0-CSI take could be kept with `k` | `check_take` returns `has_csi`. With < 10 CSI records on any RX the take is rejected automatically, with no keep option | `test_bug1_zero_csi_is_rejected_automatically` |
| 2: `q` at keep/redo prompt kept the take | Prompts accept only listed keys and re-ask otherwise. `q` = quit, and the take is moved to `_rejected` | `test_bug2_*` (2 tests) |
| 3: dead serial reader → silent empty takes | The reader catches the error and stores it. The take loop checks every 10 ms for a dead reader or 2.5 s of silence, aborts the take (→ `_rejected`, note "aborted: …"), and offers reconnect by by-id name; the take is then redone | `test_bug3_*` (3 tests, "die" and "silent" modes) |
| 4: file size used as an emptiness test | Only decoded CSI records count; STATS-only files are detected | `test_bug4_stats_only_file_is_not_a_take` |
| 5: `meta.json` written before the keep/redo answer | Takes are recorded into `data/raw/_incoming/<sid>/`; `meta.json` is written only after the decision, then the folder is atomically renamed to `data/raw/<sid>/` (keep) or `data/raw/_rejected/<sid>/`. Ctrl+C at the prompt leaves the take in `_incoming` (ignored by the dataset builder; the next run lists it) | `test_bug5_interrupt_at_prompt_leaves_take_out_of_raw` |

Format 1 is unchanged: same folder name, same `meta.json` keys. The only new location is `data/raw/_incoming/`, which starts with `_` and is therefore already ignored by `build_dataset.py`.

**Note for today's S5/S6 session:** it runs the old recorder from commit e765966, so bugs 1–5 still apply there. A `valid:false` take with empty notes (like T29), or a kept take with 0 CSI, can appear again. The post-recording audit will catch both.
