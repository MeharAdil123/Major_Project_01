# Features f2 (`ml/features.py`, FEATURES_VERSION = "f2")

One feature vector per window (2, 3 or 4 s). Input per receiver: gain-normalised HT-LTF amplitude `X[T,114]` at 100 Hz, sanitised phase `P[T,114]`, RSSI `rssi[T]` (from `pipeline/preprocess.py` v2). Every per-RX feature exists twice (`rx1_…`, `rx2_…`), plus 5 cross-receiver features. **83 features: 33 static, 50 dynamic.**

**Why two groups (D-024).** Recording position is confounded with activity: falls and lying only happen on the mattress (M), sit/stand at chairs A/B, walking on the paths. Body shadowing changes the received level and the channel *shape* depending on where the person is (spot A → RX1, spot B → RX2; `docs/analysis/phase2_signal_inspection.md` §3). The static channel shape also shifted between the morning (S1–S4) and afternoon (S5/S6) sessions (D-033). So **static** features can classify *where* rather than *what*, and are session-sensitive. **Dynamic** features describe how the channel *changes over time*, which is what an activity does. Every model is reported with all features and dynamic-only; dynamic-only is the default for the event task.

**Never features:** missing-packet share, loss, gap length, low-scale (−6 dB) packet share. All of them depend on position (body shadowing), so they would leak it.

| Group / subgroup | Features (per RX unless marked) | What it is | Why it should separate classes |
| --- | --- | --- | --- |
| static / shape | `band0..7_mean` | mean gain-normalised amplitude in 8 equal sub-carrier bands | the body's position and posture reshape the multipath profile (frequency-selective fading); mostly *where* the body is |
| static / rssi_level | `rssi_mean`; cross: `xrx_rssi_diff` | received power level; RX1 − RX2 difference | body shadowing of one link (A → RX1, B → RX2); position, partly posture (lying low vs standing) |
| static / pca_shape | `pca_evr1..3`, `pc1_load_q0..3` | explained-variance ratio of the first 3 principal components over time; share of PC1's loading in 4 carrier quarters | whether one movement pattern dominates, and *which part of the band* it affects (geometry-dependent) |
| dynamic / temporal | `sd_mean, sd_median, sd_p90, sd_max`, `diff_mean, diff_p90` | temporal std of each carrier (relative to its mean) and mean \|change per 10 ms\|, summarised over carriers | still postures (sit, stand, lie, empty) vary little; walking and transitions vary a lot |
| dynamic / motion | `motion_mean, motion_p90, motion_max, motion_argmax` | the onset detector's motion signal inside the window: 0.25 s std of PC1–3; `argmax` = where in the window it peaks (0..1) | events are short bursts (high max, peaked); walking is sustained (high mean); still states are low |
| dynamic / bandpower | `pc1_logpower`, `pc1_frac_0.3_1Hz, _1_3Hz, _3_8Hz, _8_20Hz`, `pc1_peak_hz` | spectrum of PC1 (Hann window): total power above 0.3 Hz, share per band, dominant frequency | Doppler-like: breathing / sway < 1 Hz, walking gait 1–3 Hz, a fall's impact puts power above 3 Hz |
| dynamic / corr | `sc_corr` | mean \|correlation\| between carriers' fluctuations | one large movement drives the whole band coherently; noise is uncorrelated |
| dynamic / rssi_var | `rssi_std` | RSSI variation within the window | movement near a link modulates the received power |
| dynamic / phase | `ph_cvar_w`, `ph_cvar_p90`, `dph_w`, `dph_p90`, `ph_pc1_logpower` | sanitised phase: circular variance over time per carrier, mean \|phase change per 10 ms\|, PC1 power of the phase deviation. Weights = squared mean carrier amplitude, so faded carriers (2π-slip prone, D-036) count little; `p90` uses only carriers above the median weight | phase responds to path-length change (motion contrast 1.85 / 2.04 vs amplitude 2.09 / 2.58 on event takes, Phase 2) and complements amplitude |
| dynamic / cross (cross-RX only) | `xrx_sd_logratio`, `xrx_motion_logratio`, `xrx_phase_logratio`, `xrx_motion_corr` | log ratio RX1/RX2 of temporal std, motion and phase variance; correlation of the two motion signals | which link the movement disturbs more, and whether both see the same movement. Phase is never compared *across* receivers (not phase-coherent); only each RX's own variance is |

Ablation subgroups (Phase 4): shape, rssi_level, pca_shape, temporal, motion, bandpower, corr, rssi_var, phase, cross. Receiver ablations use the `rx1_` / `rx2_` prefixes (cross features need both RX). "Amplitude only" = all features minus the `phase` subgroup and `xrx_phase_logratio`.

Tests: `tests/test_features.py` (shapes for 2/3/4 s, unique names, groups, no loss-type features, dynamic features rise with motion, batch = single).
