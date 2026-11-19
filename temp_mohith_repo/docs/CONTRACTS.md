# Interface contracts (frozen 2026-10-21, 23:00)

The four tracks only depend on these formats, never on each other's internals.
Change a format only after telling everyone; bump the version string.

```
 Track A                Track B                    Track C                  Track D
 record_session.py ──►  build_dataset.py   ──►     ml/train_final.py ──►    app/engine.py + live_app.py
 Format 1               Format 2                   Format 3                 (reads Format 3 + live serial)
 data/raw/<sid>/        data/processed/*.npz       models/<task>/           dashboard
                        pipeline/preprocess.py  ◄──────── shared by B (offline) and D (live) ───────┘
```

## Labels

| Kind | Labels | Take length | Notes |
| --- | --- | --- | --- |
| state | `empty`, `sit`, `stand`, `walk`, `lie` | 30 s | a state that lasts; classified from every 2 s window |
| event | `fall`, `sit_down`, `stand_up`, `bend_pick` | 10 s, cue at 3 s | a transition of 1–3 s; only the window around the movement is used |

`fall` is the target; `sit_down`, `stand_up` and `bend_pick` are look-alike movements the detector must *not* call a fall.

## Format 1: raw take (Track A → B)

`data/raw/<session_id>/RX1.bin, RX2.bin, meta.json`

- `RXn.bin`: the raw serial byte stream from receiver n (wire protocol v2, `docs/firmware/wire_protocol_v2.md`). Decode with `host/csiwire.py`.
- `session_id` = `<YYYYMMDD>_<subject>_<take_id>_<activity>[_rN]`.
- `meta.json`:

```json
{
  "session_id": "20261022_P1_T01_sit", "protocol": "p1", "plan": "protocol/plan_subject.csv",
  "take_id": "T01", "kind": "state", "activity": "sit", "position": "A",
  "subject": "P1", "setting": "same_room", "layout": "layout_A", "operator_position": "O",
  "tx_power_dbm": 5, "duration_s": 30, "cue_s": null,
  "start_local": "2026-10-22T09:41:10", "instruction": "Sit on the chair at spot A...",
  "valid": true, "check": {"RX1": {"rate": 197.9, "max_gap_ms": 15.0, "ok": true}, "RX2": {...}},
  "notes": ""
}
```
- `subject` is `none` for empty-room takes. `valid: false` takes are ignored by the dataset builder. Rejected takes live in `data/raw/_rejected/`, which is never used.

## Shared preprocessing (`pipeline/preprocess.py`, version `v1`)

Only our TX's packets are kept. The tool uses HT-LTF amplitude on the 114 used carriers (−58..−2, +2..+58) and aligns RX1 and RX2 by TX sequence number. It fills missing packets by linear interpolation and divides each packet by its mean amplitude (gain removal). Then it averages 200 → 100 Hz and cuts 2 s windows (200 samples).
A window is rejected if any receiver misses more than 10 % of its packets or has a gap over 100 ms.

## Format 2: windows (Track B → C)

`data/processed/windows_state.npz` and `windows_event.npz`:

| Key | Shape / type | Meaning |
| --- | --- | --- |
| `X` | float16 [N, 2, 200, 114] | gain-normalised amplitude, [RX1, RX2] × time (100 Hz) × sub-carrier |
| `rssi` | float16 [N, 2, 200] | RSSI per sample |
| `y` | str [N] | label |
| `session_id`, `subject`, `position` | str [N] | **use `session_id` / `subject` to split, never random windows** |
| `t_start` | float32 [N] | window start within its take (s) |
| `miss_frac` | float32 [N, 2] | fraction of interpolated packets |
| `classes`, `preproc_version`, `fs`, `used_sc`, `synthetic` | — | metadata |

State windows: every 1 s, skipping the first and last second. Event windows: 5 windows centred on the movement peak after the cue (−0.3, −0.15, 0, +0.15, +0.3 s). `data/processed/index.csv` lists windows kept and rejected per take.


## Format 2 v2 (2026-10-22, D-042) — replaces the v1 windows above

`data/processed/windows_<len>s.npz` for len = 2, 3, 4 s (3 s default):

| Key | Shape / type | Meaning |
| --- | --- | --- |
| `X` | float16 [N, 2, T, 114] | gain-normalised amplitude, anti-alias decimated to 100 Hz (T = 100 × len) |
| `P` | float16 [N, 2, T, 114] | sanitised phase (rad) |
| `rssi` | float16 [N, 2, T] | RSSI |
| `y`, `source` | str [N] | window label; `state` / `event` / `event_pre` / `event_post` |
| `session_id`, `subject`, `position`, `take_id`, `activity`, `kind` | str [N] | ids (**split by subject; never random windows**) |
| `t_start` | float32 [N] | window start in take time (s from the first packet) |
| `miss_frac`, `max_gap` | [N, 2] | missing share and longest gap per RX (gate inputs; never features) |
| `preproc_version`, `features_version`, `onset_version`, `dataset_version`, `win_s`, `gate_max_miss`, `gate_max_gap`, `used_sc`, `fs`, `synthetic` | — | metadata |

`data/features/features_<len>s.csv`: `session_id, subject, take_id, activity_label, window_label, position, t_start, rx1_miss, rx2_miss, source, kind`, then the 83 f2 features (`docs/FEATURES.md`). Per-take and per-window indexes: `data/processed/index_<len>s.csv`, `windows_<len>s_index.csv`; event intervals: `onsets.csv`.

## Format 3: models (Track C → D)

`models/<task>_rf/model.joblib` + `model_meta.json` (`task`, `classes`, `features_version`, `preproc_version`, `synthetic`, `trained_at`, top features, extra keys such as `live_motion_threshold`).
`results/state_metrics.json`, `results/event_metrics.json`, `results/*_confusion.png`, `results/summary.json`.

The only call the live app makes:

```python
from ml.predict import Predictor
p = Predictor("models")
out = p.predict(X, rssi)    # X [2,200,114], rssi [2,200]
# {"label": "sit", "confidence": 0.82, "probs": {...}, "motion": 0.013, "fall_prob": 0.04, "uncertain": false}
```
A CNN or any other model can replace the random forest if it is wrapped to keep this call identical.


## Format 3 v2 and Predictor p2 (2026-10-23, D-050/D-052) — replaces the v1 model format above

`models/<task>/model.joblib` + `model_meta.json` for task = `presence` (logistic regression), `state` (extra trees), `events` (SVM-RBF), `fall_alarm` (calibrated binary SVM, D-051), plus `models/env_baseline.json` (empty-room reference for the live environment check).
`model_meta.json` keys: `task, model, classes, best_params, n_train, loso{macro_f1_mean, macro_f1_std, macro_f1_per_fold, pooled, source}, features_version, preproc_version, onset_version, window_s, fs, featset, feature_names, synthetic, trained_at, trained_on, git_commit, python, sklearn, limitations`, and `alarm{theta, k, n, cooldown_s}` (events / fall_alarm).

```python
from ml.predict import Predictor          # PREDICTOR_VERSION "p2"
p = Predictor("models")
out = p.predict(X, rssi, P)               # one 4 s window from pipeline/preprocess.py v2: X, P [2, 400, 114], rssi [2, 400]
# {"label", "confidence", "probs", "motion", "fall_prob", "uncertain",               (v1 keys)
#  "presence_prob", "state", "state_probs", "event", "event_probs"}                  (added)
p.alarm   # {"theta": 0.5, "k": 2, "n": 3, "cooldown_s": 10.0, ...}: alarm when >= k of the last n windows have fall_prob >= theta
```

## Engine state (Track D internal, for the UI)

See the docstring in `app/engine.py`: `status` (`ok|degraded|no_signal|error`), `label`, `label_smoothed` (majority of last 3 windows), `confidence`, `uncertain`, `probs`, `motion`, `fall_prob`, `alert` (`FALL` when 2 of the last 3 windows have fall_prob ≥ 0.6, 10 s cooldown), and `rx` health.

## Evaluation rules (no leakage)

1. Never split windows randomly. Neighbouring windows overlap and look alike, so random splits inflate accuracy.
2. The main result is **leave-one-subject-out**: test on a person the model never saw. Empty-room takes are dealt to folds take by take.
3. Report per-class precision, recall, F1, the confusion matrix, presence sensitivity and specificity, fall sensitivity, and the false-alarm share.
4. Every result says that it comes from one room, one layout, 6 volunteers (S1–S6), and simulated falls.
