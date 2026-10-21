# Track B: Signal processing and dataset (owner: Sujal)

**Goal:** turn raw takes into clean, leakage-safe windows (Format 2) and explain the signal processing with figures.

**Owns:** `pipeline/preprocess.py` (shared with the live engine; interface frozen, version `v1`), `pipeline/build_dataset.py`, figures in `results/signal/`.
**Input:** Format 1 (`data/raw/...`). Tonight use `data_synth/raw` (`scripts/pipeline.sh synth`).
**Output:** Format 2 (`data/processed/windows_state.npz`, `windows_event.npz`, `index.csv`).

## Tonight (on synthetic data and ~/csi_runs from Mohith)
1. `scripts/pipeline.sh synth` runs end to end on your laptop.
2. Make `pipeline/plots.py`: for one take, plot (a) raw amplitude heatmap, (b) after gain normalisation, (c) after 100 Hz decimation, (d) motion energy over time with the detected event peak. These figures go into the report and explain each processing step.
3. Check the event peak detection on synthetic event takes (`index.csv` column `peak_s` should be ~3.5–5 s).
4. Optional, only if 1–3 are done: a phase-sanitising function (remove the linear slope and offset across sub-carriers) as a **separate** feature output. Do not change `X`.

## Tomorrow
- After each subject's data arrives: `scripts/pipeline.sh dataset`; check `index.csv` (rejected windows, peaks) and send `windows_*.npz` to Mehar (USB/shared drive).
- Look at 1 take per class with your plots; flag strange takes to Mohith.
- 12:00: final dataset build with all takes; freeze it (copy with a timestamp).

## Done when
- `windows_state.npz` + `windows_event.npz` from the real data, < 10 % windows rejected, event peaks within 1–5 s after the cue.
- Processing figures for one take per class in `results/signal/`.

## Rules
- Do not change the output format or the meaning of `X` without telling Mehar and Nihar (bump `PREPROC_VERSION`).
- Never write raw data into the repo.

## Claude Code prompt
> Read docs/CONTRACTS.md, pipeline/preprocess.py and pipeline/build_dataset.py. Write pipeline/plots.py that, for a given take folder, saves 4 figures (raw heatmap, gain-normalised heatmap, decimated heatmap, motion energy with the detected event peak) into results/signal/<session_id>/. Use only functions from preprocess.py and build_dataset.py so the plots show exactly what the pipeline does. Test on data_synth/raw. Do not change the Format 2 output.
