#!/usr/bin/env python3
"""Read-only audit of data/raw (Phase 0). Opens files for reading only; writes nothing under data/.

    python3 scripts/audit_raw.py [--raw data/raw] [--decode] > results/audit/raw_audit.log

Counts takes per subject x activity from meta.json, checks the `check` block (records > 0 on
RX1 and RX2), flags folders without meta.json, name/meta mismatches and _rN duplicates.
With --decode it also decodes every RXn.bin (host/csiwire.py) and counts CSI records itself.

Set-up drift check (D-031), for takes recorded after the 22 Oct baseline:
    python3 scripts/audit_raw.py --decode --baseline-csv results/audit/raw_takes.csv --rssi-tol 3 \
        --csv results/audit/raw_takes_s5s6.csv > results/audit/raw_audit_s5s6.log
Takes whose session_id is not in the baseline CSV are "new". For each new take and receiver, its
RSSI median is compared with the median of the baseline takes of the same activity and position
(empty room with empty room); |difference| > tol dB is flagged. A per-subject median of the
differences is also reported (one take can differ through body shadowing; a whole subject
shifting is the sign that the set-up moved).
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

RXS = ("RX1", "RX2")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def rssi_drift(new_rows, base_rows, tol=3.0):
    """Compare RSSI medians of new takes with the baseline. Returns (per_take, per_subject).

    per_take:    list of dict(session_id, subject, key, RXn_rssi, RXn_ref, RXn_diff, RXn_ref_range, flag)
    per_subject: dict subject -> {RXn: median diff, "flag": bool, "n": takes compared}
    """
    import statistics as st
    ref = collections.defaultdict(lambda: {rx: [] for rx in RXS})
    for r in base_rows:
        for rx in RXS:
            v = _f(r.get(f"{rx}_rssi_med"))
            if v is not None:
                ref[(r["activity"], r["position"])][rx].append(v)
    per_take, diffs = [], collections.defaultdict(lambda: {rx: [] for rx in RXS})
    for r in new_rows:
        key = (r["activity"], r["position"])
        out = dict(session_id=r["session_id"], subject=r["subject"], key=f"{key[0]}@{key[1]}", flag=False)
        for rx in RXS:
            v, b = _f(r.get(f"{rx}_rssi_med")), ref.get(key, {}).get(rx, [])
            out[f"{rx}_rssi"] = v
            if v is None or not b:
                out[f"{rx}_ref"] = out[f"{rx}_diff"] = None
                out[f"{rx}_ref_range"] = "no reference"
                continue
            d = v - st.median(b)
            out.update({f"{rx}_ref": st.median(b), f"{rx}_diff": round(d, 1),
                        f"{rx}_ref_range": f"{min(b):g}..{max(b):g} (n={len(b)})"})
            diffs[r["subject"]][rx].append(d)
            if abs(d) > tol:
                out["flag"] = True
        per_take.append(out)
    per_subject = {}
    for subj, dd in diffs.items():
        m = {rx: round(st.median(v), 1) if v else None for rx, v in dd.items()}
        per_subject[subj] = dict(m, n=max(len(v) for v in dd.values()),
                                 flag=any(x is not None and abs(x) > tol for x in m.values()))
    return per_take, per_subject


NAME_RE = re.compile(r"^(\d{8})_(S\d|none)_([A-Z]\d{2})_([a-z_]+?)(?:_r(\d+))?$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--decode", action="store_true")
    ap.add_argument("--csv", type=Path, help="write a per-take table here")
    ap.add_argument("--baseline-csv", type=Path, help="per-take table of the baseline takes (D-031)")
    ap.add_argument("--rssi-tol", type=float, default=3.0, help="dB; flag |RSSI - baseline| above this")
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
    if a.baseline_csv:
        import csv
        with open(a.baseline_csv, newline="") as fh:
            base = list(csv.DictReader(fh))
        base_ids = {r["session_id"] for r in base}
        new = [r for r in rows if r["session_id"] not in base_ids]
        gone = sorted(base_ids - {r["session_id"] for r in rows})
        print(f"\n== set-up drift check vs {a.baseline_csv} (tol {a.rssi_tol:g} dB) ==")
        print(f"baseline takes: {len(base)}; new takes: {len(new)}; baseline takes missing now: {gone or 'none'}")
        nc = collections.Counter((r["subject"], r["activity"]) for r in new)
        print("new takes per subject:", dict(sorted(collections.Counter(r["subject"] for r in new).items())))
        for (sj, act), n in sorted(nc.items()):
            print(f"  {sj:<5} {act:<10} {n}")
        per_take, per_subject = rssi_drift(new, base, a.rssi_tol)
        print("\nper subject (median of new-minus-baseline RSSI over its takes):")
        for sj, v in sorted(per_subject.items()):
            print(f"  {sj}: RX1 {v['RX1']:+} dB, RX2 {v['RX2']:+} dB over {v['n']} takes"
                  + ("   <-- FLAG: set-up may have moved" if v["flag"] else ""))
        flagged = [t for t in per_take if t["flag"]]
        print(f"\ntakes with |diff| > {a.rssi_tol:g} dB: {len(flagged)} of {len(per_take)}")
        for t in per_take:
            if t["flag"] or t["RX1_ref"] is None or t["RX2_ref"] is None:
                print(f"  {t['session_id']:<40} {t['key']:<16} "
                      + "  ".join(f"{rx} {t[rx + '_rssi']} vs {t[rx + '_ref']} ({t[rx + '_diff']}; base {t[rx + '_ref_range']})"
                                  for rx in RXS) + ("  FLAG" if t["flag"] else "  (no reference)"))
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
