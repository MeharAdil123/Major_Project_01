#!/usr/bin/env python3
"""Record labelled takes from RX1 + RX2 following a plan CSV (protocol/*.csv).

One take = one activity = one folder:  data/raw/<session_id>/RX1.bin, RX2.bin, meta.json
(Format 1 in docs/CONTRACTS.md). The label is the take, so nobody labels by hand.

    python3 -m host.record_session --plan protocol/plan_empty.csv --subject none
    python3 -m host.record_session --plan protocol/plan_subject.csv --subject P1
    python3 -m host.record_session --plan protocol/plan_subject.csv --subject P1 --from E01
    python3 -m host.record_session --single walk --seconds 30 --subject P2 --position free

Per take: the instruction is printed (and spoken if `spd-say` exists), the operator presses
Enter, a countdown runs (pre_delay_s), recording starts. Event takes beep + say "now" at
cue_s. After the take the files are checked (both receivers, rate, gaps) and you choose
keep / redo / skip. Rejected takes are moved to data/raw/_rejected/.

The serial ports stay open for the whole run, so boards are never reset between takes.
Raw data stays on this laptop (data/ is git-ignored).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402

RX1_TOKEN = "28:84:85:85:5E:2C"       # RX1 native USB, MAC in the by-id name
RX2_TOKEN = "5C38144809"              # RX2 CH343 serial number
RX1_BAUD, RX2_BAUD = 115200, 2_000_000
MIN_RATE = 180.0                      # packets/s per receiver
MAX_GAP_MS = 100.0                    # D-012
PROTOCOL_VERSION = "p1"


def find_port(token: str) -> str | None:
    d = Path("/dev/serial/by-id")
    if d.exists():
        for p in sorted(d.iterdir()):
            if token in p.name:
                return str(p)
    return None


class PortReader(threading.Thread):
    """Reads one port forever; while `sink` is set, raw bytes are written to it."""

    def __init__(self, name, port, baud):
        super().__init__(daemon=True)
        import serial
        self.name_ = name
        self.s = serial.Serial()
        self.s.port, self.s.baudrate, self.s.timeout = port, baud, 0.05
        self.s.dtr = False
        self.s.rts = False
        self.s.open()
        self.sink = None
        self.lock = threading.Lock()
        self.bytes = 0
        self.stop = threading.Event()

    def run(self):
        while not self.stop.is_set():
            chunk = self.s.read(65536)
            if not chunk:
                continue
            self.bytes += len(chunk)
            with self.lock:
                if self.sink:
                    self.sink.write(chunk)

    def set_sink(self, f):
        with self.lock:
            self.sink = f


def say(text: str, voice: bool):
    print(text, flush=True)
    if voice and shutil.which("spd-say"):
        subprocess.Popen(["spd-say", "-w", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def beep(voice: bool):
    print("\a" + "#" * 20 + "  NOW  " + "#" * 20, flush=True)
    if voice and shutil.which("spd-say"):
        subprocess.Popen(["spd-say", "now"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def check_take(folder: Path, duration: float, expected=("RX1", "RX2")):
    """Quick quality check of a take. Returns (ok, stats dict)."""
    stats, ok = {}, True
    for name in expected:
        f = folder / f"{name}.bin"
        if not f.exists():
            stats[name] = dict(error="no file")
            ok = False
            continue
        rec = cw.load(f)
        h = rec.hdr[(rec.hdr["flags"] & cw.F_SEQ_VALID) != 0] if rec.n else rec.hdr
        n = len(h)
        if n < 10:
            stats[name] = dict(records=n, error="no CSI")
            ok = False
            continue
        seq = h["seq"].astype(int)
        gaps = (cw.np.diff(seq) - 1).clip(min=0)
        rate = n / duration
        max_gap_ms = float((gaps.max() + 1) * 5.0)
        s = dict(records=n, rate=round(rate, 1), loss_pct=round(float(100 * (1 - n / (seq[-1] - seq[0] + 1))), 2),
                 max_gap_ms=max_gap_ms, rssi_median=float(cw.np.median(h["rssi"])),
                 crc_rejected=rec.crc_errors)
        s["ok"] = bool(rate >= MIN_RATE and max_gap_ms <= MAX_GAP_MS)
        ok &= s["ok"]
        stats[name] = s
    return ok, stats


def read_plan(path: Path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["duration_s"] = float(r["duration_s"])
        r["cue_s"] = float(r["cue_s"]) if r.get("cue_s") else None
        r["pre_delay_s"] = float(r.get("pre_delay_s") or 3)
    return rows


def record_take(readers, take, args, out_root: Path):
    day = dt.datetime.now().strftime("%Y%m%d")
    base = f"{day}_{args.subject}_{take['take_id']}_{take['activity']}"
    sid, k = base, 1
    while (out_root / sid).exists() or (out_root / "_rejected" / sid).exists():
        k += 1
        sid = f"{base}_r{k}"
    folder = out_root / sid
    folder.mkdir(parents=True)

    for i in range(int(take["pre_delay_s"]), 0, -1):
        print(f"  starting in {i} ...", flush=True)
        time.sleep(1)
    files = {name: open(folder / f"{name}.bin", "wb") for name in readers}
    start_wall = dt.datetime.now().isoformat(timespec="seconds")
    t0 = time.monotonic()
    for name, r in readers.items():
        r.set_sink(files[name])
    say("  recording", False)
    cue_done = take["cue_s"] is None
    while (el := time.monotonic() - t0) < take["duration_s"]:
        if not cue_done and el >= take["cue_s"]:
            beep(args.voice)
            cue_done = True
        time.sleep(0.01)
    for r in readers.values():
        r.set_sink(None)
    for f in files.values():
        f.close()
    say("  done", args.voice)

    ok, stats = check_take(folder, take["duration_s"], tuple(readers))
    meta = dict(
        session_id=sid, protocol=PROTOCOL_VERSION, plan=str(args.plan) if args.plan else "single",
        take_id=take["take_id"], kind=take["kind"], activity=take["activity"],
        position=take["position"], subject=args.subject, setting=args.setting,
        layout=args.layout, operator_position=args.operator_position,
        tx_power_dbm=args.tx_power, duration_s=take["duration_s"], cue_s=take["cue_s"],
        start_local=start_wall, instruction=take["say"], valid=ok, check=stats, notes="",
    )
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    for name, s in stats.items():
        print(f"  {name}: {s}")
    return folder, ok, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", type=Path, help="plan CSV (protocol/...)")
    ap.add_argument("--single", help="record one take of this activity instead of a plan")
    ap.add_argument("--kind", default="state", choices=["state", "event"])
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--cue", type=float, help="cue time for --single event takes")
    ap.add_argument("--position", default="-")
    ap.add_argument("--subject", required=True, help="P1, P2, ... or none")
    ap.add_argument("--from", dest="from_take", help="start the plan at this take_id")
    ap.add_argument("--setting", default="same_room")
    ap.add_argument("--layout", default="layout_A", help="name of the board layout drawn in docs")
    ap.add_argument("--operator-position", default="O", help="where the operator sits during takes")
    ap.add_argument("--tx-power", type=float, default=None, help="TX power in dBm (from TX HELLO)")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--rx1", default=None)
    ap.add_argument("--rx2", default=None)
    ap.add_argument("--only", choices=["RX1", "RX2"], help="record one receiver only (testing)")
    ap.add_argument("--no-voice", dest="voice", action="store_false")
    ap.add_argument("--auto", action="store_true", help="no Enter between takes; keep good takes, redo bad once")
    a = ap.parse_args()

    if a.single:
        takes = [dict(take_id="X", kind=a.kind, activity=a.single, position=a.position,
                      duration_s=a.seconds, cue_s=a.cue, pre_delay_s=3, say=f"{a.single} at {a.position}")]
    elif a.plan:
        takes = read_plan(a.plan)
        if a.from_take:
            ids = [t["take_id"] for t in takes]
            takes = takes[ids.index(a.from_take):]
    else:
        ap.error("give --plan or --single")

    ports = {}
    if a.only != "RX2":
        ports["RX1"] = (a.rx1 or find_port(RX1_TOKEN), RX1_BAUD)
    if a.only != "RX1":
        ports["RX2"] = (a.rx2 or find_port(RX2_TOKEN), RX2_BAUD)
    for name, (p, _) in ports.items():
        if not p:
            print(f"{name} not found in /dev/serial/by-id (use --{name.lower()} PORT)")
            return 1
    readers = {}
    for name, (p, baud) in ports.items():
        r = PortReader(name, p, baud)
        r.start()
        readers[name] = r
        print(f"{name}: {p} @ {baud}")
    time.sleep(1.5)
    for name, r in readers.items():
        if r.bytes == 0:
            print(f"WARNING: no bytes from {name} yet - is it powered and flashed?")

    a.out.mkdir(parents=True, exist_ok=True)
    log = []
    i = 0
    while i < len(takes):
        t = takes[i]
        print("\n" + "=" * 70)
        print(f"[{i + 1}/{len(takes)}] {t['take_id']}  {t['kind'].upper()}  activity={t['activity']}  "
              f"position={t['position']}  {t['duration_s']:.0f}s" + (f"  cue at {t['cue_s']:.0f}s" if t['cue_s'] else ""))
        say(t["say"], a.voice)
        if not a.auto:
            c = input("Enter = start, s = skip, q = quit: ").strip().lower()
            if c == "q":
                break
            if c == "s":
                i += 1
                continue
        folder, ok, meta = record_take(readers, t, a, a.out)
        if ok:
            print(f"  GOOD -> {folder.name}")
            c = "k" if a.auto else input("k = keep (Enter), r = redo, x = reject: ").strip().lower() or "k"
        else:
            print("  BAD TAKE (rate or gaps)")
            c = "r" if a.auto and not log[-1:] == [("retry", t["take_id"])] else \
                ("x" if a.auto else input("r = redo (Enter), k = keep anyway, x = reject: ").strip().lower() or "r")
        if c in ("r", "x"):
            rej = a.out / "_rejected"
            rej.mkdir(exist_ok=True)
            shutil.move(str(folder), str(rej / folder.name))
            print(f"  moved to _rejected/{folder.name}")
            if c == "r":
                log.append(("retry", t["take_id"]))
                continue
        else:
            if not ok:
                meta["valid"] = True
                meta["notes"] = "kept by operator despite failed check"
                (folder / "meta.json").write_text(json.dumps(meta, indent=2))
            log.append(("kept", t["take_id"]))
        i += 1

    for r in readers.values():
        r.stop.set()
    kept = sum(1 for k, _ in log if k == "kept")
    print(f"\nfinished: {kept} takes kept in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
