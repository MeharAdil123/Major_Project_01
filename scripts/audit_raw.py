#!/usr/bin/env python3
"""Read-only audit of data/raw (Phase 0). Opens files for reading only; writes nothing under data/.

    python3 scripts/audit_raw.py [--raw data/raw] [--decode] > results/audit/raw_audit.log

Counts takes per subject x activity from meta.json, checks the `check` block (records > 0 on
RX1 and RX2), flags folders without meta.json, name/meta mismatches and _rN duplicates.
With --decode it also decodes every RXn.bin (host/csiwire.py) and counts CSI records itself.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402

NAME_RE = re.compile(r"^(\d{8})_(S\d|none)_([A-Z]\d{2})_([a-z_]+?)(?:_r(\d+))?$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--decode", action="store_true")
    ap.add_argument("--csv", type=Path, help="write a per-take table here")
    a = ap.parse_args()

    folders = sorted(p for p in a.raw.iterdir() if p.is_dir() and not p.name.startswith("_"))
    stray = sorted(p.name for p in a.raw.iterdir() if not p.is_dir())
    problems, rows = [], []
    counts = collections.Counter()
    by_subject = collections.Counter()
    seen = collections.defaultdict(list)
    for f in folders:
        mf = f / "meta.json"
        if not mf.exists():
            problems.append(f"{f.name}: no meta.json")
            continue
        m = json.loads(mf.read_text())
        nm = NAME_RE.match(f.name)
        if not nm:
            problems.append(f"{f.name}: folder name does not match the Format 1 pattern")
        else:
            _, subj, tid, act, _ = nm.groups()
            if (subj, tid, act) != (m.get("subject"), m.get("take_id"), m.get("activity")):
                problems.append(f"{f.name}: name vs meta mismatch "
                                f"({m.get('subject')}, {m.get('take_id')}, {m.get('activity')})")
        if m.get("session_id") != f.name:
            problems.append(f"{f.name}: meta.session_id = {m.get('session_id')}")
        seen[(m.get("subject"), m.get("take_id"))].append(f.name)
        counts[(m.get("subject"), m.get("activity"))] += 1
        by_subject[m.get("subject")] += 1
        if not m.get("valid", True):
            problems.append(f"{f.name}: valid=false")
        files = sorted(x.name for x in f.iterdir())
        if set(files) != {"RX1.bin", "RX2.bin", "meta.json"}:
            problems.append(f"{f.name}: files {files}")
        chk = m.get("check") or {}
        row = dict(session_id=f.name, subject=m.get("subject"), take_id=m.get("take_id"),
                   kind=m.get("kind"), activity=m.get("activity"), position=m.get("position"),
                   duration_s=m.get("duration_s"), tx_power_dbm=m.get("tx_power_dbm"),
                   notes=m.get("notes", ""))
        for rx in ("RX1", "RX2"):
            c = chk.get(rx)
            if not c:
                problems.append(f"{f.name}: no check block for {rx}")
                continue
            if "error" in c or not c.get("records", 0) > 0:
                problems.append(f"{f.name}: {rx} check {c}")
            row.update({f"{rx}_meta_records": c.get("records"), f"{rx}_rate": c.get("rate"),
                        f"{rx}_loss_pct": c.get("loss_pct"), f"{rx}_max_gap_ms": c.get("max_gap_ms"),
                        f"{rx}_rssi_med": c.get("rssi_median"), f"{rx}_ok": c.get("ok")})
            if a.decode and (f / f"{rx}.bin").exists():
                rec = cw.load(f / f"{rx}.bin")
                h = rec.hdr
                ours = ((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)
                segs = cw.tx_segments(h["seq"][ours]) if ours.any() else []
                row.update({f"{rx}_decoded": int(ours.sum()), f"{rx}_crc_err": rec.crc_errors,
                            f"{rx}_other_len": json.dumps(rec.other_len) if rec.other_len else "",
                            f"{rx}_tx_segments": len(segs),
                            f"{rx}_ht40_pct": round(100 * float((h["cwb"][ours] == 1).mean()), 1) if ours.any() else 0})
                if not ours.any():
                    problems.append(f"{f.name}: {rx}.bin decodes to 0 CSI records from our TX")
                if len(segs) > 1:
                    problems.append(f"{f.name}: {rx} has {len(segs)} TX boot segments (TX reboot inside take)")
                if c.get("records") is not None and abs(int(ours.sum()) - c["records"]) > 0:
                    problems.append(f"{f.name}: {rx} decoded {int(ours.sum())} vs meta {c['records']}")
        rows.append(row)

    print(f"raw folder: {a.raw}")
    print(f"take folders (excluding _*): {len(folders)}; stray non-folders: {stray}")
    print("\ntakes per subject:", dict(sorted(by_subject.items())), "total", sum(by_subject.values()))
    acts = sorted({k[1] for k in counts})
    subs = sorted({k[0] for k in counts})
    print("\n" + "subject".ljust(8) + "".join(x[:9].rjust(10) for x in acts) + "     total")
    for s in subs:
        print(s.ljust(8) + "".join(str(counts[(s, x)]).rjust(10) for x in acts) + str(by_subject[s]).rjust(10))
    print("total".ljust(8) + "".join(str(sum(counts[(s, x)] for s in subs)).rjust(10) for x in acts)
          + str(sum(by_subject.values())).rjust(10))
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    print(f"\nsame (subject, take_id) kept more than once: {len(dup)}")
    for k, v in sorted(dup.items()):
        print(f"  {k}: {v}")
    redo = [r["session_id"] for r in rows if re.search(r"_r\d+$", r["session_id"])]
    print(f"\nfolders with an _rN suffix (redo kept): {len(redo)}")
    print(f"takes whose check failed but kept by operator: "
          f"{sum(1 for r in rows if 'kept by operator' in (r['notes'] or ''))}")
    print(f"\nproblems: {len(problems)}")
    for p in problems:
        print("  " + p)
    if a.csv:
        import csv
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"\nper-take table: {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
