# Phase 5: CSI decoding and inspection

Tools: `host/csiwire.py` (decoder library) and `host/csi_inspect.py` (figures + report).
Test data: `tests/synthetic/make_synthetic_run.py` writes a fake run with known features (synthetic, not a measurement).

## What the decoder assumes (and where it comes from)

ESP-IDF v5.5.5, `docs/en/api-guides/wifi.rst`, section "Wi-Fi Channel State Information", column
*secondary channel below, HT, 40 MHz, non-STBC*: total 384 bytes.

| Bytes | Field | Values | Sub-carrier index (documented) |
| --- | --- | --- | --- |
| 0–127 | L-LTF | 64 | 0..63 |
| 128–383 | HT-LTF | 128 | 0..63, then -64..-1 |

Each value is 2 × int8: **imaginary first, then real**. With `FIRST_WORD_INVALID` set, the first 2 values are invalid (set to NaN).
The decoder reorders HT-LTF to -64..63.

Two things the documentation leaves open, which `csi_inspect.py` measures instead of assuming:
1. **Which HT-LTF carriers are really empty.** The 802.11n HT40 standard uses -58..-2 and +2..+58 (114 carriers, pilots ±11, ±25, ±53). The ESP-IDF table text says -57..+57. The report prints the measured empty set and whether it matches the standard.
2. **Where the 64 L-LTF bins sit in the 40 MHz band.** The table only says "0~63". The tool tests four placements by correlating the mean L-LTF amplitude profile with the HT-LTF profile and prints the winner (or "inconclusive").

## Figures

1. `1_heatmap.png`: per receiver, |H| (dB) over time × sub-carrier: raw, and relative to the static channel with the per-packet gain removed (±3 dB colour scale). RSSI under each.
2. `2_channel.png`: mean |H| per sub-carrier with 10–90 % band, empty carriers, pilots; L-LTF per bin; L-LTF vs HT-LTF on one axis; raw phase of 5 consecutive packets.
3. `3_quality.png`: packets per second, gaps between packets (100 ms limit, D-012), RSSI vs CSI power with steps > 2 dB (red = gain-change candidate: CSI power and RSSI disagree), CSI power vs RSSI scatter.

The gain-change rule is a heuristic: a step in total CSI power that RSSI does not show (or the other way round) suggests the receiver's automatic gain control changed. It is not a confirmed AGC readout.

## Run

```bash
~/WiFi_CSI_Final/hostenv/bin/python host/csi_inspect.py ~/csi_runs/e0_swap
~/WiFi_CSI_Final/hostenv/bin/python host/csi_inspect.py ~/csi_runs/e0_swap --t0 25 --t1 37
```
Outputs go to `RUN/inspect/` (or `RUN/inspect_T0-T1/`) and stay local.

## Verified so far

- On synthetic data (2026-10-21): recovers the built-in HT40 empty set, L-LTF placement, the 60 ms gap, the 4 dB gain step (1 candidate, at 45 s), loss 1.08 % / 2.28 %, 10 CRC rejects, and the 29–33 s motion. This tests the software only.
- On real recordings: pending.
