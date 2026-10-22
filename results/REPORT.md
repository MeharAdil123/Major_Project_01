# WiFi-CSI HAR: Phase 4 results (draft for Gate 4, 2026-10-23)

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

**Time:** fit/train time is in the comparison CSVs. Per-window latency on this laptop (`results/phase4/latency.log`): f2 features 133 ms; MiniRocket transform 41 ms batched, **326 ms for a single window**. Classifier prediction is < 1 ms (Track A) and ~1 ms (deep). The live engine steps every 500 ms.

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

## 6. Open items for Gate 4
1. **Events:** adopt MiniRocket (rule result) or SVM-RBF? MiniRocket needs a probability head for the live alarm (e.g. logistic regression on its features, re-evaluated on the same folds and the per-take chain). Its single-window transform takes 326 ms on this laptop.
2. **Presence:** MiniRocket (rule; unstable folds) or logistic regression (stable, cheap)? Either way, presence of a still person needs an empty-room calibration in the new room (Phase 5).
3. **State:** extra trees (dynamic), as the rule says.
4. After the choice: retrain on all subjects, save in Format 3 (`models/<task>/model.joblib` + `model_meta.json`), and update `ml/predict.py`.
