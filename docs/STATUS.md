# STATUS — 2026-10-22 ~18:45 IST · Phase 2 done · **waiting at Gate 2**

## Phase 1 (closed, commit b5eb4c0)
Firmware review + v2.1 (built, not flashed), recorder bugs 1–5 fixed, S5/S6 audit (202 takes = `config/dataset_expected.yaml`), RF hygiene D-032. Details: `docs/firmware/REVIEW_phase1.md`, `results/audit/`.

## Phase 2: what was done (branch `cc/phase2`)
Signal inspection on all 202 real takes (read-only). Full report: **`docs/analysis/phase2_signal_inspection.md`**. Decisions: D-034 … D-038 in `docs/decisions/DECISIONS.md`.
- **Empty carriers:** 802.11n layout confirmed on 396/404 receiver-takes (114 used) → `USED_SC` unchanged, no PREPROC bump.
- **L-LTF:** upper 20 MHz; not used.
- **AGC:** no RSSI-linked gain steps. Per-packet −6.1 dB scale shifts, equal on all carriers, on 188/202 (RX1) and 201/202 (RX2) takes. Normalisation removes them; the share is reported per take and never a feature.
- **Phase:** raw phase is random (2.8 rad); sanitised phase is stable (0.13–0.16 rad) and responds to motion (contrast 1.85 / 2.04 vs amplitude 2.09 / 2.58). 2π slips near deep fades → amplitude-weighted phase features in Phase 3.
- **Body shadowing:** spot A → RX1 loss 4.6 %; spot B → RX2 −44 dBm, 7 % loss (up to 35 %). Position confound confirmed.
- **Event timing:** the old 200 Hz frame-difference peak is unreliable (ratio 1.23). The new onset/end detector `pipeline/onset.py` (o1) detects 95 %, 85 % inside [cue, cue+4 s], RX agreement median 0.21 s.
- **Walking-start falls:** 7 keep, 3 exclude (S2_E57, S5_E39, S6_E39).
- `host/csi_inspect.py` was run with its new default output (`results/signal/<sid>/`); nothing was written under `data/`.

## Verified results (logs, all in `results/signal/` unless stated)
`inspect_<sid>.log` · `phase2_signal.log` + `phase2_summary.json` + `phase2_takes.csv` + `low_scale_per_take.csv` · `phase2_figures.log` · `phase2_peaks.log` · `onset_validation.log` + `onset_takes.csv` · `body_shadowing.log` · `results/audit/pytest_phase2.log` (tests).
Figures: `class_*.png` (9), `onset_*.png` (4 × 10 takes), `phase_raw_vs_sanitised.png`, `csi_scaling.png`, `body_shadowing.png`.

## Open problems
1. 8 event takes have no detectable action (bend_pick ×5 at A/C, stand_up ×2 at C, one fall). They give no event windows in Phase 3 and will be reported.
2. There is no video ground truth; onset validation rests on proxies (RX agreement, overlays).
3. The sanitised phase has 2π slips near fades (~3 % of packets); mitigated by amplitude weighting, not removed.
4. `/home/mohith/rec_s5` worktree: user removes it.

## Next step
Waiting for your "go" at Gate 2. Then Phase 3: D-023 gate diagnosis first (the three zero-window takes have 18–21 % loss on one RX), preprocess v2 (anti-alias, phase channel, parameterised windows), labelling from onset o1, features f2 (static vs dynamic groups), datasets for 2/3/4 s windows.
