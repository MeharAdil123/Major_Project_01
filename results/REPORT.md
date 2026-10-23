# WiFi-CSI HAR: Phase 4 results (final, 2026-10-23)

All numbers come from scripts run on 2026-10-22/23 on the 202 real takes (S1–S6). Logs and result files are referenced next to each table. Nothing here is synthetic.

## Scope and limits (read first)
- **One room** (library hall), **one layout** (`config/position_map.yaml` v2), **6 volunteers** (S1–S6), one TX and two RX boards, channel 11 HT40, 5 dBm.
- **Falls were simulated on a mattress** by healthy volunteers, and **all 42 falls happened at the same spot (M)**. The data cannot show fall detection anywhere else.
- **No video ground truth.** Event timing comes from the audio cue plus a motion-onset detector (`pipeline/onset.py` o2), validated only by proxies.
- **Not clinically validated.** This is not a medical device.
- **Position confound:** activity and position are linked (lie/fall only at M, sit/stand at A/B, walk on the paths), and recognition depends on where a movement happens relative to the two links (§5).
- **Session effect (D-033):** S1–S4 were recorded in the morning and S5/S6 in the afternoon, after a TX re-aim. The static channel shape differs by 3.4 / 4.4 dB RMS between the sessions. **S5 and S6 are cross-session folds**: their test data come from a session that is under-represented in training (only one other afternoon subject in each training set).
- **Small data:** 2401 windows of 4 s from 202 takes. Per class and subject there are often fewer than 10 event takes; bend_pick has 113 windows in total.

## 1. Protocol
- **Evaluation:** leave-one-subject-out, 6 folds (S1…S6). The 7 empty-room takes are dealt to folds take by take. Every hyper-parameter search is nested: GroupKFold(3) over the training subjects, scored by macro-F1. Scalers are fitted inside the training folds.
- **Tasks:**
  - presence: empty vs occupied, all windows;
  - state: sit / stand / walk / lie, from state takes plus the pre/post-action windows of event takes;
  - events: fall / sit_down / stand_up / bend_pick / none, where "none" is every non-event window.
- **Metric:** macro-F1 per fold, then mean ± std over the 6 folds. Deep models: mean over 3 seeds per fold.
- **Window length:** chosen by a rule fixed before looking (`scripts/phase4_choose_window.py`): the mean over the three tasks of the best Track A model with dynamic features. 2 s: 0.533 · 3 s: 0.582 · **4 s: 0.603** → **4 s** (`results/phase4/chosen_window.json`). The tasks differ: events and presence are best at 4 s, state is slightly best at 3 s (LightGBM 0.580 vs extra trees 0.572 at 4 s).
- **Input:**
  - Track A: features f2, default **dynamic-only** (50 features; D-024).
  - Track B: 16 band channels (8 sub-carrier bands × 2 RX) at 100 Hz, window mean removed.
  - Track C: 32 channels (amplitude + amplitude-weighted phase bands) at 50 Hz, window mean removed.

## 2. Model comparison at 4 s (`results/phase4/comparison_<task>.csv`, `selection.log`)

**Events** (5 classes):

| Track | Model | Macro-F1 | S1 | S2 | S3 | S4 | S5* | S6* | Fall F1 (window) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B | MiniRocket (NumPy re-impl.) | **0.572 ± 0.062** | 0.509 | 0.668 | 0.645 | 0.531 | 0.559 | 0.520 | 0.464 (sens 0.434) |
| A | SVM-RBF (dynamic) | 0.539 ± 0.054 | 0.501 | 0.590 | 0.577 | 0.448 | 0.595 | 0.520 | 0.521 (sens 0.552) |
| A | SVM-RBF (all features) | 0.530 ± 0.081 | 0.396 | 0.621 | 0.540 | 0.457 | 0.549 | 0.617 | — |
| A | XGBoost (dynamic) | 0.523 ± 0.084 | 0.509 | 0.593 | 0.566 | 0.396 | 0.636 | 0.441 | 0.560 |
| A | LightGBM / extra trees / HistGB / RF | 0.505 / 0.502 / 0.495 / 0.486 | | | | | | | |
| A | k-NN / logistic regression | 0.463 / 0.437 | | | | | | | |
| C | best deep: CNN-BiLSTM / 1-D CNN / ABLSTM | 0.344 / 0.332 / 0.327 | | | | | | | |
| C | other deep (ResNet-1D, TCN, CNN-LSTM, THAT, GRU, BiLSTM, LSTM) | 0.323 … 0.264 | | | | | | | |

\* cross-session folds (afternoon session).

**State** (4 classes): extra trees **0.572 ± 0.115** · MiniRocket 0.568 ± 0.079 · extra trees (all features) 0.564 · LightGBM 0.561 · THAT 0.546 ± 0.166 (best deep) · RF 0.541. Per fold for extra trees: S1 0.434, S2 0.538, S3 0.640, S4 0.422, S5* 0.688, S6* 0.708.

**Presence** (2 classes): MiniRocket **0.729 ± 0.178** (S3 0.474, S4 0.487, the others 0.83–0.90) · logistic regression 0.698 ± 0.065 (sensitivity 0.855, specificity 0.828) · SVM-RBF 0.697 ± 0.072. The tree models rarely predict "empty" (specificity 0.07–0.47): a still person and an empty room look alike in dynamic features, and static features do not transfer across sessions (logistic regression with all features: 0.641).

**Deep models (Track C).**
- Sizes: 19k (GRU) to 127k (THAT) parameters.
- Budget, the same for all: ≤ 30 epochs, early stopping on an inner validation subject (patience 6), AdamW 1e-3, augmentation on training windows only, 3 seeds. Seed std ≤ 0.03.
- **They overfit:** training loss falls to ~0.2 while the inner-validation loss rises from about epoch 3. The best epoch has a median of 5–9 (`results/phase4/track_c/<task>/*_curves.png`, fold S1, seed 0). On events, every deep model under-predicts the four event classes (recall 0.1–0.4).
- Hyper-parameters were not tuned after seeing test folds.

**Time:** fit/train time is in the comparison CSVs. Per-window latency on this laptop (`results/phase4/latency.log`): f2 features 133 ms (67 ms after caching the per-receiver PCA, outputs bit-identical; a full Predictor call ≈ 125 ms); MiniRocket transform 41 ms batched, **326 ms for a single window**. Classifier prediction is < 1 ms (Track A) and ~1 ms (deep). The live engine steps every 500 ms.

## 3. Selection rule (`scripts/phase4_select.py`, `results/phase4/selection.json`)
Rule (PROMPT 4.2), adapted from 4 to 6 folds: the simplest model whose macro-F1 is within one std of the best **and** that wins or ties (within 0.02) the best on **≥ 5 of 6 folds** (75 %, as 3 of 4).
- **Events → MiniRocket.** No simpler model passes: SVM-RBF wins or ties on 3/6 folds, XGBoost 2/6. Same result with a 4-of-6 reading.
- **State → extra trees (dynamic).** It is the best; MiniRocket ties on 3/6.
- **Presence → MiniRocket.** It is the best mean, but with the largest spread (± 0.178). The rule measures "within one std" with the best model's own std, so its instability does not count against it. Logistic regression is much more stable (± 0.065).

## 4. Fall detection per take, live decision chain (`results/phase4/pertake/svm_rbf__*__4s.json/.csv`)
Run with **SVM-RBF** (the best Track A event model). The same chain could not yet be run for MiniRocket, because its ridge head gives no probabilities (open item).
- **Chain:** every gate-passing 4 s window, hop 0.5 s, over **all** event and state takes of the test subject, in time order. Alarm when ≥ 2 of the last 3 windows have P(fall) ≥ 0.6, with a 10 s cooldown. No motion gate (D-025). Independent of the onset detector.

| Features | Falls detected | Falls with detected onset | Look-alike takes with alarm | State takes with alarm | Alarm latency after onset (median) |
| --- | --- | --- | --- | --- | --- |
| dynamic | **18 of 42** | 18 of 41 (the 1 undetected-onset fall: no alarm) | 9 of 109 (sit_down 5/43, stand_up 4/46, bend_pick 0/20) | 5 of 51 (7 alarms in 0.45 h; 6 of them in walk takes) | 2.05 s |
| all | 15 of 42 | 15 of 41 | 8 of 109 | 3 of 51 | 1.73 s |

- Falls detected per fold (dynamic): S1 1/8, S2 2/5, S3 3/5, S4 3/8, S5* 3/8, S6* 6/8.
- θ sweep, **analysis only** (θ = 0.6 was fixed beforehand): θ 0.3 → 28/42 falls, 17 look-alike alarms; θ 0.9 → 7/42, 3.
- Window-level fall vs rest (pooled): F1 0.52, sensitivity 0.55.
- **Bottom line: about 4 falls in 10 are caught, with an alarm on about 1 in 12 look-alike movements.** This is far from a usable fall detector and is reported as such.

## 5. Ablations (same folds; best Track A model per task; `results/phase4/ablations/`)

**Events, SVM-RBF, 4 s:**

| Set | Macro-F1 | Set | Macro-F1 |
| --- | --- | --- | --- |
| dynamic (reference) | 0.539 ± 0.054 | static only | **0.353** ± 0.062 |
| all features | 0.530 ± 0.081 | amplitude + phase (dynamic) vs amplitude only | 0.539 vs 0.535 |
| RX1 only (dynamic) | 0.384 | RX2 only (dynamic) | 0.403 |
| − motion | **0.474** | − bandpower | 0.494 |
| − rssi_var | 0.506 | − phase | 0.527 |
| − cross-RX | 0.529 | − temporal | 0.542 |
| − corr | 0.547 | gate 15 % instead of 20 % | 0.572 (on 2253 windows) |

**State, extra trees:** dynamic 0.572 · all 0.564 · static 0.469 · **RX1 only 0.429 · RX2 only 0.615** · amplitude only 0.569 · state takes only (no pre/post windows) 0.553 · gate 15 % 0.526.
**Presence, logistic regression:** dynamic 0.698 · all 0.641 · static 0.560 · RX1 0.589 · RX2 0.637 · amplitude only 0.659 · gate 15 % 0.681.

Readings:
- **Both receivers matter for events** (0.54 vs ~0.39–0.40 with one RX).
- **Motion and band-power features carry most of the event information.**
- **Phase adds little on events** (+0.004) but helps presence (+0.04).
- **Static features alone are weak and add nothing on top of dynamic ones** (D-024 confirmed).
- The window length effect is in §1.

**Position check** (`results/phase4/position_check.log`; SVM-RBF dynamic, per-window recall). sit_down: A 0.76, B 0.25, C 0.34. stand_up: A 0.55, B 0.40, C 0.27. At B and C, 16–22 % of these windows are taken for a fall. **The same movement is recognised far better at spot A (next to RX1).** Recognition depends on position relative to the links, so the fall results (all at M) do not generalise to other places in the room.

## 6. Gate 4 decision (D-050)
**Final models: events → SVM-RBF, state → extra trees, presence → logistic regression; 4 s windows; dynamic-only f2 features.**
The selection rule (§3) picked MiniRocket for events and presence. **Those rule picks stay recorded here**; two departures were made, with these reasons (`docs/decisions/DECISIONS.md` D-050):
- **Events, SVM-RBF instead of MiniRocket.** Falls were declared the target before the run, and MiniRocket is worse on that class: window-level fall F1 0.464 vs 0.521, sensitivity 0.434 vs 0.552. The live alarm needs calibrated probabilities, which MiniRocket's ridge head does not give. Its transform takes 326 ms per single window on this laptop.
- **Presence, logistic regression instead of MiniRocket.** Stability across subjects: MiniRocket 0.729 ± 0.178 with S3 0.474 and S4 0.487; logistic regression 0.698 ± 0.065, no fold below 0.587.

## 7. Fall alarm experiment (D-051; `scripts/phase4_fall_chain.py`, `results/phase4/fall_chain/`, log `results/phase4/fall_chain.log`)
- **Model:** a binary fall-vs-rest SVM-RBF (dynamic f2) with Platt (sigmoid) calibration. Calibration is fitted on leave-one-subject-out splits of the training subjects only.
- **Per outer fold:** the threshold θ (0.30–0.95) and the rule k-of-n (1-of-2, 2-of-3, 2-of-4) are chosen from INNER leave-one-subject-out stream predictions on the five training subjects. The goal is the most falls detected, subject to look-alike alarms ≤ 9/109 and walking alarms ≤ 45.4 per hour. The setting is then applied unchanged to the held-out subject. No tuning on test subjects.

| | Current chain (5-class SVM, θ 0.6, 2-of-3) | New chain (calibrated binary SVM, per-fold settings) |
| --- | --- | --- |
| Falls detected | 18 of 42 | **21 of 42** |
| Look-alike takes with an alarm | 9 of 109 | 8 of 109 |
| Walking alarms | 6 in 0.132 h (45.4 per hour) | 4 (30.3 per hour) |
| Empty/still-take alarms | 1 in 0.314 h (3.2 per hour) | **2 (6.4 per hour)** |
| Median alarm latency after onset | 2.05 s | 1.99 s |
| Per fold: falls / look-alike alarms | S1 1/8 · S2 2/5 · S3 3/5 · S4 3/8 · S5* 3/8 · S6* 6/8 | S1 2/8, 1 · S2 2/5, 0 · S3 4/5, 1 · S4 3/8, 1 · S5* 5/8, 1 · S6* 5/8, 4 |
| Chosen settings | fixed | S1 θ 0.60 1-of-2 · S2 0.60 1-of-2 · S3 0.50 2-of-3 · S4 0.60 2-of-3 · S5 0.45 2-of-3 · S6 0.50 1-of-2 |

**Adopted:** the new chain detects more falls with no increase in look-alike or walking alarms, so it meets the adoption rule set before the run. Caveats:
- the gain is small (+3 of 42) on few takes;
- empty/still alarms, which are not part of the adoption rule, rose from 1 to 2;
- S6 has 4 look-alike alarms.

**Final alarm settings** (the same selection on all six subjects' outer-LOSO predictions, `results/phase4/fall_chain/final_settings.json`): **θ = 0.5, 2-of-3, 10 s cooldown**. On those predictions this single setting gives 18/42 falls, 7/109 look-alike alarms, 30.3 walking and 6.4 still alarms per hour. These are in-sample for the setting; the unbiased estimate of the procedure is the per-fold column above.

## 8. Final models (Format 3, `models/`; `ml/train_final.py`, log `results/phase4/train_final.log`)
Trained on all six subjects plus the 7 empty-room takes. Hyper-parameters come from the same grids, chosen by GroupKFold(3) over the six subjects. The LOSO scores in each `model_meta.json` are the evaluation results above, not scores of the refitted models.

| Task | Model | Params | Training windows | File size | LOSO macro-F1 |
| --- | --- | --- | --- | --- | --- |
| presence | logistic regression | C = 1 | 2401 | 3 KB | 0.698 ± 0.065 |
| state | extra trees (300 trees) | max_features 0.3, min_samples_leaf 1 | 1134 | 10 MB | 0.572 ± 0.115 |
| events | SVM-RBF | C = 10, γ = 0.01 | 2401 | 540 KB | 0.539 ± 0.054 |
| fall_alarm | SVM-RBF + Platt calibration | C = 1, γ = 0.01; θ 0.5, 2-of-3 | 2401 | 548 KB | chain: 21/42 falls (§7) |

Interface: `ml/predict.py` Predictor **p2**, `predict(X, rssi, P)` (D-052). An environment baseline for the live start-up check is in `models/env_baseline.json`: the 7 training empty-room takes, 262 windows; their static profiles differ by 3.2 dB median RMS among themselves.
Smoke test on real windows: `results/phase4/predictor_smoke.log` (in-sample, for interface checking only).
