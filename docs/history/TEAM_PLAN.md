# Team plan: 21 Oct night → 22 Oct 14:00 review

**Show at 14:00:** a live camera-free room monitor (empty/occupied, sit/stand/walk/lie, fall alert) on the real boards. Also results measured on people the model never saw, and a clean repo with the full pipeline.
**Marked experimental / future work:** through-wall (no second room tomorrow), breathing rate, counting people, calibration for new rooms, sleep.

## Tracks (no cross-dependencies: each works only against docs/CONTRACTS.md)

| Track | Owner | Input → Output | Brief |
| --- | --- | --- | --- |
| A Hardware + recording + integration | Mohith | boards → Format 1 raw takes; live hardware | `docs/tracks/TRACK_A_hardware_recording.md` |
| B Signal processing + dataset | Sujal | Format 1 → Format 2 windows + processing figures | `docs/tracks/TRACK_B_signal_processing.md` |
| C Models + evaluation | Mehar | Format 2 → Format 3 models + metrics | `docs/tracks/TRACK_C_machine_learning.md` |
| D Live demo + dashboard + docs | Nihar | Format 3 + live stream → dashboard, README | `docs/tracks/TRACK_D_live_demo_frontend.md` |

Tonight everyone works on **synthetic data** (`scripts/pipeline.sh synth`), so nobody waits for anybody.
Tomorrow the same code runs on real data.

## Timeline

| Time | A (Mohith) | B (Sujal) | C (Mehar) | D (Nihar) |
| --- | --- | --- | --- | --- |
| Tonight → 00:30 | GitHub repo; csi_inspect on e0_swap; recorder dry run | pipeline runs; processing plots | report + ablation scripts | dashboard on replay; README |
| 09:00–09:30 | room set-up, TX power, checks | help set-up; tape marks | help set-up | photo of layout; help |
| 09:30–10:30 | **recording** (operator) | subject P1, then builds dataset after each subject | subject P2 | subject P3 |
| 10:30–11:00 | extra takes / 4th subject | dataset build v1 | training on v1 | replay demo with real takes |
| 11:00–12:00 | spare takes; help C | final dataset 12:00 | LOSO + ablation | dashboard polish |
| 12:00–13:00 | merge branches | figures for report | final models + results | real model in dashboard |
| 13:00–13:30 | live rehearsal on boards (A + D) | report: method | report: results | README results |
| 13:30–13:50 | final push, tag `v1.0-review` | — | — | backup replay ready |

Subjects: Sujal, Mehar, Nihar (P1–P3); Mohith operates. If time allows, a second round with Mohith as P4 (another operator takes over).

## Git workflow

- `main` is protected by habit: only Mohith merges.
- Each person works on their branch: `track-b`, `track-c`, `track-d` (Mohith: `track-a` or `main`).
- Each track owns different files (see briefs), so merges don't conflict. Shared files (`pipeline/preprocess.py`, `ml/predict.py`, `app/engine.py`, `docs/CONTRACTS.md`): change only after telling the group.
- Commit small and often: `git add <your files>; git commit -m "track-b: ..."; git push`.
- **Never commit `data/`, raw `.bin` files, or model `.joblib` files** (git-ignored). Raw data goes person to person on a USB stick.

## Tomorrow's RF hygiene

During recording, phones on airplane mode or outside the room, and laptops other than the recorder off Wi-Fi or out of the room. They share the 2.4 GHz band and add packets and motion.
