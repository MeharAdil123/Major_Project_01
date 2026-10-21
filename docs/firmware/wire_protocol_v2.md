# csi_rx wire protocol v2

Firmware: `firmware/rx/main/csi_wire.h`, `firmware/rx/main/link.c`. Host: `host/rx_check.py`.

## Transport

| Receiver | Link | Port | Speed |
| --- | --- | --- | --- |
| RX1 | Native USB (USB-Serial-JTAG) | `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_<MAC>-if00` | n/a |
| RX2 | UART0, GPIO43 TX / GPIO44 RX, via the board's CH343 | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_<serial>-if00` | 2 000 000 baud, 8N1 |

Only binary frames go over these links. On RX2 the ESP-IDF console is disabled.

## Frame

All integers are little-endian.

| Bytes | Field |
| --- | --- |
| 2 | sync `A5 5A` |
| 1 | type: `0x01` HELLO (JSON), `0x02` STATS (JSON, every 1 s), `0x10` CSI |
| 2 | payload length (≤ 2048) |
| n | payload |
| 2 | CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over type, length and payload |

The host slides forward one byte on a bad CRC and resyncs on the next `A5 5A`. Damaged frames are dropped and counted (`CRC errors`).

## CSI record (type 0x10): 48-byte header + `csi_len` bytes of int8 CSI

| Off | Type | Field | Meaning |
| --- | --- | --- | --- |
| 0 | u8 | version | 2 |
| 1 | u8 | rx_id | 1 or 2 |
| 2 | u16 | flags | bit 0 seq valid · 1 radio_id mismatch · 2 first_word_invalid · 3 smoothing · 4 not_sounding · 5 aggregation · 6 STBC · 7 SGI · 8 LDPC |
| 4 | u32 | seq | TX sequence number; restarts at 0 when the TX reboots |
| 8 | u64 | tx_time_us | TX clock at send |
| 16 | u64 | rx_time_us | RX clock in the CSI callback |
| 24 | u32 | rx_ctrl_ts | RX MAC timestamp (µs, wraps) |
| 28 | u32 | radio_id | from the TX payload (CRC32 of the radio settings; 0xCBD36978 for ch11/HT40/MCS0/200 Hz/32 B) |
| 32 | u16 | mac_seq | 802.11 sequence number |
| 34 | i8 | rssi | dBm |
| 35 | i8 | noise_floor | dBm |
| 36 | i8 | tx_power_qdbm | TX power for this frame, 0.25 dBm units |
| 37 | u8 | rate | non-HT rate code |
| 38 | u8 | sig_mode | 0 non-HT, 1 HT |
| 39 | u8 | mcs | |
| 40 | u8 | cwb | 0 = 20 MHz, 1 = 40 MHz |
| 41 | u8 | channel | primary |
| 42 | u8 | secondary_channel | 0 none, 1 above, 2 below |
| 43 | u8 | reserved | |
| 44 | u16 | sig_len | bytes incl. FCS |
| 46 | u16 | csi_len | bytes of CSI that follow (384 measured at HT40) |

CSI bytes are int8 pairs, imaginary part first, then real, per subcarrier. Measured layout at HT40 with the secondary below and no STBC: 384 B = L-LTF 128 B (64 subcarriers) + HT-LTF 256 B (128 subcarriers). Subcarrier ordering is decoded in Phase 5.

## TX payload (first 24 bytes of each ESP-NOW frame from csi_tx)

`magic u32 "CSI1" (0x31495343) | seq u32 | tx_time_us u64 | radio_id u32 | rate_hz u16 | tx_power_qdbm i8 (offset 22) | reserved u8`, then zero padding to 32 bytes.
