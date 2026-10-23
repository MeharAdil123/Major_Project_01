# Phase 2 — signal inspection on real data (Gate 2, 2026-10-22)

All numbers come from scripts run on the 202 real takes on 2026-10-22, reading `data/raw` only. Outputs are in `results/signal/`.

| Script | Log | Tables / figures |
| --- | --- | --- |
| `host/csi_inspect.py` (1 take per class) | `results/signal/inspect_<sid>.log` | `results/signal/<sid>/{1_heatmap,2_channel,3_quality}.png, report.json` |
| `scripts/phase2_signal.py` (all takes) | `phase2_signal.log` | `phase2_takes.csv`, `phase2_summary.json`, `low_scale_per_take.csv` |
| `scripts/phase2_figures.py` | `phase2_figures.log` | `class_<activity>.png` (9), `phase_raw_vs_sanitised.png`, `csi_scaling.png`, `body_shadowing.png` |
| `scripts/phase2_peaks.py` (old vs smoothed peak) | `phase2_peaks.log` | `phase2_peaks.csv` |
| `scripts/phase2_onset.py` (new detector) | `onset_validation.log` | `onset_takes.csv`, `onset_<class>.png` (10 takes each) |
| body shadowing summary | `body_shadowing.log` | `body_shadowing.png` |

Class takes (lowest loss on the worse RX, `results/signal_selection.txt`): bend_pick S4_E25 · empty B01_r4 · fall S6_E21 · lie S4_T11 · sit S4_T03 · sit_down S4_E02 · stand S4_T01 · stand_up S5_E15 · walk S5_T16.

## 1. Open radio questions (PROJECT_CONTEXT §3)

**(a) Empty HT-LTF sub-carriers.** 396 of 404 receiver-takes show exactly the 802.11n HT40 layout: empty −64..−59, −1..+1, +59..+63, **114 used (−58..−2, +2..+58)**. The other 8 show 1–11 *extra* low carriers in one take each (e.g. 30..40). Those are deep fades of that take's channel, not structural nulls. The ±57 hint in the ESP-IDF text is wrong for this hardware.
→ **`USED_SC` stays as in v1. No `PREPROC_VERSION` bump for this.**

**(b) L-LTF placement.** In 402/404, the null bins are 0..5, 32, 59..63. 394 match "bin k = HT40 sub-carrier k", i.e. the **upper 20 MHz** (primary channel; the secondary is below). 9 are inconclusive and 1 shows another pattern, both in fading-heavy takes. L-LTF is therefore a 20 MHz subset of what HT-LTF already covers; v1 does not use it, and nothing here argues for adding it.

**(c) AGC / gain steps.** Per-packet CSI power does **not** follow RSSI: the slope of CSI power vs RSSI is −0.002 (RX1) / +0.004 (RX2) dB/dB, because the receiver already compensates gain. Instead, packets fall onto a second level **−6.1 dB** below the main one (median step −6.11 / −6.08 dB, p5–p95 −6.29…−5.92). The shift is **equal on all carriers** (spread 0.69 / 0.54 dB) and alternates packet by packet, not as steps in time. That is an amplitude halving: a per-packet scale shift, consistent with ESP-IDF's automatic CSI scaling (`manu_scale = false`).
- Takes affected: RX1 188/202, RX2 201/202. Median share of low-scale packets 1.5 % (RX1) / 2.9 % (RX2); p90 10 % / 26 %; max 39 % / 59 %. 27 takes have > 20 % on RX2. **All five worst are at spot B**, where RX2 is shadowed.
- Per take and RX: `results/signal/low_scale_per_take.csv`. Figure: `csi_scaling.png`.
- Handling (agreed): firmware unchanged; per-packet normalisation removes the shift; **the low-scale fraction is never used as a feature**. It tracks position (spot B), so it would leak.
- Side effect: low-scale packets carry half the int8 resolution, so they are noisier after normalisation. This is one reason why differences between consecutive 200 Hz packets are a poor motion signal (§4).

## 2. Phase

- **Raw phase is unusable:** temporal circular std 2.84 / 2.82 rad (median over takes; random phase ≈ 3). Each packet has its own slope (timing offset) and offset (CFO/PLL). See `phase_raw_vs_sanitised.png`.
- **Sanitised phase** (unwrap across carriers, then remove each packet's least-squares line) is stable: 0.16 / 0.13 rad. It changes visibly with motion in the class figures (e.g. `class_sit_down.png`, RX1 at 4.3–5.3 s).
- **Motion contrast** on 141 still-start event takes. The metric is the peak of a 1 s sliding spread in [cue, cue+4] divided by the pre-cue median, on 50 ms-smoothed signals:

  | Signal | RX1 median | share > 1.5 | RX2 median | share > 1.5 |
  | --- | --- | --- | --- | --- |
  | gain-normalised amplitude | 2.09 | 0.85 | 2.58 | 0.91 |
  | sanitised phase | 1.85 | 0.73 | 2.04 | 0.77 |
  | phase rate (Δ per 50 ms) | 1.47 | 0.48 | 1.61 | 0.55 |

  For walking vs standing state takes, the spread ratio is 1.9× (amplitude) and 1.5× (phase) on RX1, and 1.9× / 1.6× on RX2.
- **Caveat:** where a carrier band sits in a deep fade, unwrapping can slip by 2π, and the fitted line jumps between two values. This was seen on RX2 of S6_E21 after 8 s. Slope outliers occur on 2.9 % (RX1) / 3.5 % (RX2) of packets on average. I tested an unwrap-free variant (neighbour-product slope + amplitude-weighted line). It was **noisier** (0.28 / 0.40 rad vs 0.16 / 0.13), so it was rejected.
- **Decision (agreed):** include phase-based dynamic features in Phase 3 (temporal variance and derivative of sanitised phase), **weighted by carrier amplitude** so faded, slip-prone carriers count little. Keep the standard unwrap + least-squares sanitiser. Never compare phase across receivers (not phase-coherent). The amplitude-only vs amplitude + phase ablation in Phase 4 decides what stays in the final model.

## 3. Per-take quality and body shadowing

Per-take loss, longest gap and RSSI for all 202 takes: `results/audit/raw_takes_all.csv`. Medians by position (`body_shadowing.log`, `body_shadowing.png`):

| Position | n | RX1 RSSI | RX1 loss | RX2 RSSI | RX2 loss |
| --- | --- | --- | --- | --- | --- |
| empty | 7 | −37.0 | 1.6 % | −38.0 | 4.3 % |
| **A** (near RX1) | 51 | −37.0 (to −45) | **4.6 %** | −38.0 | 4.1 % |
| **B** (RX2 side) | 50 | −37.0 | 1.7 % | **−44.0** (to −51) | **7.0 %** (to 35 %) |
| C | 30 | −36.0 | 2.3 % | −38.0 | 3.0 % |
| M | 48 | −37.0 | 1.8 % | −39.0 | 4.3 % |
| path1 / path2 / free | 6 / 6 / 4 | −37 / −37 / −37.5 | 1.9 / 3.1 / 4.3 % | −38 / −39 / −39.5 | 7.5 / 5.5 / 5.2 % |

Named cases: S2_E58 (B) RX2 −48 dBm, 35.3 % loss · S2_E59 17.9 % · S2_E60 25.1 % · S3_E47 13.2 % · S3_E48 19.3 %.
The **position confound is confirmed**: RSSI level, loss and the low-scale fraction all depend on where the person stands. For D-024, the "static" feature group holds RSSI levels and the static amplitude shape (band means, PCA shape).

**Input to D-023 (Phase 3 gate diagnosis).** The three takes that lose every v1 window do not have low loss on both receivers. S1_T06_walk has RX2 21.5 %, S1_T22_sit RX2 19.4 %, S3_T43_sit RX1 18.1 %, so the v1 rule (≤ 10 % on both RX) rejects them as designed. Phase 3 still checks gap counting, seq wrap and alignment before thresholds are touched.

## 4. Event timing: new onset/end detector (`pipeline/onset.py`, version o1)

**Why the old one goes.** `build_dataset.motion_energy` (mean |Δ| between consecutive 200 Hz packets) barely rises above its own noise. Its peak-to-baseline ratio is 1.23 at the median, and no take exceeds 2. Its RX1 and RX2 peak times differ by 0.95 s at the median. For 38 % of event takes its peak is more than 1 s away from a smoothed detector's, which would put the event window in the wrong place (`phase2_peaks.log`). Example: S4_E02 sit_down, where the old peak is at 6.7 s and the visible transition at 4.3–5.3 s.

**New detector:**
1. Gain-normalised amplitude per RX.
2. Anti-alias FIR low-pass and decimation 200 → 50 Hz.
3. PCA over the take; the motion signal is the √ of the summed variance of PC1–3 in a centred **0.25 s** window.
4. Each RX is divided by its pre-cue baseline; the combined signal is the max over RX.
5. An action needs a peak ≥ 3× baseline in [cue, cue+4 s]. The interval runs while the signal is ≥ 2× the pre-cue level (onset side) and ≥ max(2, 1.5 × post-action level) (end side). Short dips (< 0.4 s) are closed, and strong bursts within 1.5 s are merged, so bend_pick = down + up. The window smear is corrected by half a window. An onset before the cue is clipped to the cue and flagged.

0.25 s was chosen over 0.5 s: detection 0.95 vs 0.93, inside window 0.85 vs 0.80, both RX detecting 86 vs 74. Unit tests: `tests/test_onset.py` (10, SYNTHETIC).

**Validation on all 151 event takes** (`onset_validation.log`; overlays of 10 takes per class spread over subjects: `onset_{bend_pick,fall,sit_down,stand_up}.png`):

| | value |
| --- | --- |
| action detected | 143/151 (0.95); still-start takes 0.94 |
| interval inside [cue, cue+4 s] | 0.85 (still-start 0.87) |
| RX1 and RX2 both detect | 86/151; only RX1 14, only RX2 43, neither 8 |
| \|onset RX1 − onset RX2\| (both detect) | median 0.21 s (p10 0.04, p90 1.24); ≤ 0.25 s: 53 %, ≤ 0.5 s: 73 % |

| Class | detected | reaction after cue (median, p10–p90) | duration (median, p10–p90) | peak ratio |
| --- | --- | --- | --- | --- |
| fall | 41/42 | 0.90 s (0.37–1.30) | 1.45 s (0.71–3.65) | 16.1 |
| sit_down | 43/43 | 0.91 s (0.67–1.28) | 1.55 s (0.84–2.35) | 15.3 |
| stand_up | 44/46 | 0.85 s (0.28–1.14) | 1.77 s (0.92–2.99) | 12.3 |
| bend_pick | 15/20 | 1.06 s (0.65–1.79) | 2.79 s (1.51–3.38) | 4.7 |

Not inside the window (23):
- **8 not detected** (peak < 3×): bend_pick ×5 (S5_E25, S6_E25 at A; S5_E33, S6_E18, S6_E33_r2 at C), stand_up ×2 at C (S1_E31, S5_E31), fall ×1 (S4_E32). These are weak movements far from both links.
- **4 with motion before the cue,** onset clipped: three walking-start falls (S2_E57, S5_E39, S6_E39) and S6_E08 sit_down (anticipation).
- **11 detected with a correct start but an end 0.01–1.62 s after cue+4 s** (S1_E18, S1_E23, S1_E24, S1_E33, S1_E38, S3_E57, S3_E60, S4_E07, S4_E18, S5_E34_r3, S6_E10).

Phase 3 labels event windows from this interval. Undetected takes give no event windows, and that is reported.

**Limits:** there is no video ground truth, so RX agreement and the overlays are proxies, not accuracy. Reaction times of ~0.9 s are plausible for an audio cue. bend_pick at spots A and C is the weakest class.

## 5. Takes that do not start still (instruction "Walk slowly toward the mattress…", 10 falls)

Pre-cue motion is relative to the global still baseline (median pre-cue level of the 141 still-start takes):

| Take | pre-cue motion | detected | onset after cue | duration | clean action after cue? |
| --- | --- | --- | --- | --- | --- |
| S1_E21_fall | 1.9× | yes (22×) | +0.90 s | 2.85 s | yes |
| S1_E39_fall | 2.0× | yes (16×) | +0.37 s | 3.17 s | yes |
| S2_E57_fall | 3.3× | yes (29×) | **clipped** (motion runs into the cue) | 3.55 s | **no** |
| S3_E57_fall | 1.7× | yes (25×) | +1.30 s | 3.65 s | yes |
| S4_E21_fall | 1.6× | yes (9×) | +0.39 s | 3.45 s | yes |
| S4_E39_fall | 0.9× | yes (13×) | +0.82 s | 3.07 s | yes |
| S5_E21_fall | 0.8× | yes (10×) | +0.19 s | 3.69 s | yes |
| S5_E39_fall | 3.5× | yes (7×) | **clipped** | 3.88 s | **no** |
| S6_E21_fall | 1.2× | yes (14×) | +0.98 s | 2.55 s | yes |
| S6_E39_fall | 1.7× | yes (16×) | **clipped** | 3.24 s | **no** |

Your proposal applied: all 10 are kept for state windows; for event-window training, **keep the 7 with a clean onset after the cue and exclude the 3 with clipped onsets** (S2_E57, S5_E39, S6_E39). Pre-cue windows of these 10 are labelled **walk**, not stand.

Among takes whose instruction says "still", eight have pre-cue motion of 3.6–8.0× the global still baseline. The top three (S2_E58, S2_E47_r3, S3_E47) are all spot-B takes with heavy RX2 loss. Their own pre-cue baseline is used, so detection is unaffected; they are listed for inspection.

## 6. Decisions for Gate 2
1. `USED_SC`: unchanged (114 carriers, verified). L-LTF: not used.
2. Scaling steps: firmware unchanged; per-packet normalisation; the low-scale fraction is reported and never a feature.
3. Phase: amplitude-weighted dynamic phase features in Phase 3; standard sanitiser; ablation in Phase 4.
4. Onset detector o1 replaces the 200 Hz frame-difference motion energy for labelling.
5. Walking-start falls: 7 kept for event windows, 3 excluded; pre-cue windows labelled walk.
6. The static feature group includes RSSI levels and static amplitude shape (position confound).
