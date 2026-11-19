"""Explain why some recordings give no 4-s windows (the 202 vs 179 question).

Run from the project root (the folder with pipeline/ and data/):
    python explain_lost_recordings.py

Reads data/processed/index_4s.csv and data/processed/onsets.csv,
which pipeline/build_dataset.py writes when it builds the 4-s dataset.
"""
import csv
from collections import Counter
from pathlib import Path

candidates = [Path("temp_mohith_repo/data/processed"), Path("data/processed")]
proc = next((p for p in candidates if (p / "index_4s.csv").exists()), None)
if proc is None:
    found = sorted(Path(".").rglob("index_4s.csv"))
    if not found:
        raise SystemExit("index_4s.csv not found anywhere under this folder. "
                         "Rebuild it with:  python -m pipeline.build_dataset --win 4")
    proc = found[0].parent
print(f"reading {proc}\\index_4s.csv\n")
takes = list(csv.DictReader(open(proc / "index_4s.csv", newline="")))
onsets = {r["session_id"]: r for r in csv.DictReader(open(proc / "onsets.csv", newline=""))}

lost = [t for t in takes if int(t["kept"] or 0) == 0]
print(f"recordings: {len(takes)}, with at least one window: {len(takes) - len(lost)}, with none: {len(lost)}\n")


def reason(t):
    if t["used"] in ("False", "false", "0"):
        return "recording not used: " + (t["note"] or "failed take check")
    cand, gate, drop = int(t["candidates"]), int(t["rejected_gate"]), int(t["dropped_label"])
    if cand == 0:
        return "too short for a 4-s window"
    if gate == cand:
        return "quality gate (packet loss / gap) on every window"
    o = onsets.get(t["session_id"])
    if o and o.get("usable_for_event_training") in ("False", "false"):
        return "onset detector: " + (o.get("reason") or "interval not usable")
    if drop > 0:
        return "all gate-passing windows were transition windows"
    return "other"


rows = [(t["session_id"], t["subject"], t["activity"], reason(t)) for t in lost]
for r in sorted(rows, key=lambda r: (r[3], r[0])):
    print(f"{r[0]:<36} {r[1]:<3} {r[2]:<10} {r[3]}")

print("\nby reason:")
for k, v in Counter(r[3] for r in rows).most_common():
    print(f"  {v:>3}  {k}")
print("\nby activity:")
for k, v in Counter(r[2] for r in rows).most_common():
    print(f"  {v:>3}  {k}")
