#!/usr/bin/env python3
"""Choose the window length from Track A (rule fixed before looking at the results, 2026-10-22).

score(window) = mean over tasks (events, state, presence) of the best Track A model's LOSO macro-F1
(mean over folds), dynamic feature set. Highest score wins; any window within TIE of the best counts
as a tie and the tie goes to 3 s (the expected default), then to the shorter window (lower latency).
Also records the best model per task at the chosen window (for ablations and the per-take chain).
Output: results/phase4/chosen_window.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIE = 0.005
A = ROOT / "results" / "phase4" / "track_a"


def best(task, tag, featset="dynamic"):
    rs = [json.loads(p.read_text()) for p in (A / task).glob(f"*__{featset}__{tag}.json")]
    if not rs:
        return None
    r = max(rs, key=lambda r: r["macro_f1_mean"])
    return dict(model=r["model"], macro_f1_mean=r["macro_f1_mean"], macro_f1_std=r["macro_f1_std"], n_models=len(rs))


def main():
    tasks = ("events", "state", "presence")
    table = {}
    for tag in ("2s", "3s", "4s"):
        b = {t: best(t, tag) for t in tasks}
        if all(b.values()):
            table[tag] = dict(per_task=b, score=sum(v["macro_f1_mean"] for v in b.values()) / len(tasks))
    if not table:
        sys.exit("no complete Track A results")
    top = max(v["score"] for v in table.values())
    tied = [t for t, v in table.items() if v["score"] >= top - TIE]
    chosen = "3s" if "3s" in tied else sorted(tied)[0]
    out = dict(rule=__doc__.strip().splitlines()[2:6], tie=TIE, table=table, tied=tied, chosen=chosen,
               best_model_per_task={t: table[chosen]["per_task"][t]["model"] for t in tasks})
    (ROOT / "results" / "phase4" / "chosen_window.json").write_text(json.dumps(out, indent=1))
    for t, v in table.items():
        print(t, round(v["score"], 4), {k: (x["model"], round(x["macro_f1_mean"], 3)) for k, x in v["per_task"].items()})
    print("chosen:", chosen, "best models:", out["best_model_per_task"])


if __name__ == "__main__":
    main()
