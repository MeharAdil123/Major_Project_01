# Project state — WiFi-CSI HAR

As of 2026-10-21. A mirrored copy was kept in the team's planning notes.

**Bottom line:** the RF chain works. TX → RX1 + RX2 → PC runs at about 195–198 packets/s per receiver, with 100 % HT40 and about 97–98 % of packets seen by both receivers. Firmware v2 is on all boards. E1 is deferred until the room is set up. Next: Phase 5 (CSI decoding and inspection) on the recordings already saved.

## 1. Phase status

| Phase | Status |
| --- | --- |
| 0 Research and requirements | Done |
| 1 Hardware selection | Decided (D-006 → D-006b → D-006c) |
| 2 Architecture and repo | This repo, consolidated 2026-10-21 |
| 3 Development environment | Ubuntu laptop flashes all boards. ESP-IDF `export.sh` needs `./install.sh esp32,esp32s3` before rebuilding |
| 4 Bring-up and acquisition | A0 ✅, TX ✅, RX ✅, E0 ✅ (with D-011, D-012). E1–E4 open |
| 5 CSI decoding and inspection | In progress: decoder + `csi_inspect.py` written, tested on synthetic data; real runs pending |
| 6 Dataset | Protocol p1 + recorder ready; collection 2026-10-22 09:30 |
| 7 Baselines | Features + random forest + LOSO evaluation implemented (synthetic test only) |
| 11 Real-time | Live engine + Streamlit starter implemented (replay-tested on synthetic) |
| 8–10, 12–13 | Scoped for the 22 Oct review: fall detection (simulated falls) in; breathing, counting, calibration, through-wall marked future work |

## 2. Board register

| Board | Role | MAC | Host link | A0 (median RSSI drop with antenna removed) | Firmware |
| --- | --- | --- | --- | --- | --- |
| ESP-WROOM-32U NodeMCU (ESP32-D0WD-V3 rev 3.1) | TX | 20:9B:A9:68:F3:F0 | USB-UART `/dev/ttyUSB0` (opening it resets the board) | PASS −21 dB (strongest −44 dB) | csi_tx v2, saved boot power 5 dBm |
| Sixspan YD S3-N16R8 #1 (repaired) | RX1 | 28:84:85:85:5E:2C | native USB | PASS −19 dB | csi_rx v2 (rx1) |
| Sixspan YD S3-N16R8 #2 (repaired) | RX2 | 28:84:85:48:D7:DC | UART (CH343, serial 5C38144809), 2 Mbaud | PASS −19 dB | csi_rx v2 (rx2) |
| YD "odd" board (repaired) | Spare | AC:27:6E:A4:4E:30 | — | not re-tested | — |

## 3. Test results

**TX self-test (T0):** 199.4–200.6 packets/s over 240 s+, 0 send errors, 0 late slots, steady heap. HELLO read-back: channel 11, secondary below, bw HT40, `rate_cfg ESP_OK` (MCS0 LGI forced), radio_id 0xCBD36978. `power N save` verified across a power cycle.

**Bench link tests** (TX about 1 m from both RX, 60 s each, `host/rx_check.py`):

| Run | TX power | RX1 rate / loss / RSSI | RX2 rate / loss / CRC rejects / RSSI | Seen by both |
| --- | --- | --- | --- | --- |
| e0_second | 2 dBm | 198.2/s / 0.93 % / −59 dBm | 197.3/s / 1.37 % / 0.12 % / −56 dBm | 98.5 % |
| e0_v2 | 5 dBm | 198.5/s / 0.75 % / −43 dBm | 194.6/s / 2.62 % / 0.14 % / −48 dBm | 97.1 % |
| e0_swap (RX positions and antennas swapped) | 5 dBm | 197.8/s / 1.08 % / −39 dBm | 195.7/s / 2.13 % / 0.27 % / −39 dBm | 97.6 % |

All runs: 100 % HT40, CSI 384 B per packet (L-LTF 128 B + HT-LTF 256 B), 0 board queue or link drops, 0 radio_id mismatches.

**Findings**
- The classic-ESP32 TX really transmits HT40 (the open question from D-006b is closed).
- RX2 loses about 1–1.5 % more than RX1. The swap test shows this is board-side, not position or antenna. Suspected cause: the UART interrupt sharing core 0 with Wi-Fi.
- RSSI at about 1 m and 2 dBm (−55 to −60 dBm) is much lower than the earlier model predicted. Expect a higher operating power at the real 4.7 m distance; E1 decides.
- Movement near the boards shows as synchronous RSSI excursions on both RX (e0_swap, 29–33 s).

## 4. Decision register (recent)

| ID | Decision | Rationale | Reconsider if |
| --- | --- | --- | --- |
| D-006b | TX = classic ESP32 WROOM-32U; RX = S3 | U.FL-only module for the TX | — |
| D-006c | RX = the two repaired Sixspan YD boards; RX2 over UART | A0 passes after the repair; identical RX modules | RX2 link problems persist |
| D-007 | ESP-NOW broadcast with forced PHY (MCS0, HT40) | Both RX hear the same frame; documented API | — |
| D-008' | Separate TX and RX builds; RX1/RX2 via sdkconfig.rx1 / sdkconfig.rx2 | Different chips and links | — |
| D-010 | Raw CSI: LTF merge off, channel filter off, L-LTF + HT-LTF + STBC-HTLTF2 on | Smoothing can be added later, not removed | — |
| D-011 | UART link: CRC-rejected frames < 0.5 % accepted (USB must be 0) | The CRC keeps damaged frames out | Reject rate > 0.5 % |
| D-012 | RX2 loss limit 3 % (RX1 2 %) | About 196 packets/s left, far above motion bandwidth | Loss > 3 % or gaps > 100 ms. Optional fix: UART ISR on core 1 |
| D-013 | Review scope (22 Oct 14:00): presence, sit/stand/walk/lie, simulated fall; one room, one layout | One morning of data; honest claims only | More recording time |
| D-014 | Protocol p1: state takes 30 s, event takes 10 s with cue at 3 s; 2 s windows at 100 Hz (1 s hop states; 5 shifted windows per event) | Diversity of takes beats length; events last 1–3 s | Real data shows events longer than the window |
| D-015 | Evaluation: leave-one-subject-out; never random window splits | Overlapping windows leak | — |
| D-016 | Baseline model: hand features + random forest; CNN only if better on LOSO | Small data, interpretable, fast | CNN clearly better |

## 5. Open items

1. Phase 5: run `host/csi_inspect.py` on e0_second, e0_v2, e0_swap; confirm the empty sub-carriers and L-LTF placement on real data (see docs/analysis/phase5_csi_inspection.md).
2. E1 when the room is ready: real positions, TX power sweep, plywood loss. Then E2 (beamwidths), E3 (empty-room stability), E4 (sensitivity map).
3. Confirm the TX status LED (GPIO2).
4. Fix the ESP-IDF install on the laptop (`./install.sh esp32,esp32s3`).
