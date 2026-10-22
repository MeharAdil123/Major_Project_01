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
keep / redo / reject / quit.

Where a take lives (v1.1, fixes 22 Oct bugs 1-5):
  data/raw/_incoming/<sid>/   while recording and until you decide (ignored by the dataset
                              builder; left there if the program is stopped at the prompt)
  data/raw/<sid>/             only after "keep"; meta.json is written at that moment
  data/raw/_rejected/<sid>/   redo / reject / quit / automatic reject, with meta.json + reason
A take with 0 CSI records on any receiver is rejected automatically (no keep option).
If a serial port dies or goes silent during a take, the take is aborted and rejected, and
you are offered a reconnect (same /dev/serial/by-id name) before the take is redone.

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
TOKENS = {"RX1": RX1_TOKEN, "RX2": RX2_TOKEN}
BAUDS = {"RX1": 115200, "RX2": 2_000_000}
MIN_RATE = 180.0                      # packets/s per receiver
MAX_GAP_MS = 100.0                    # D-012
MIN_CSI_RECORDS = 10                  # fewer than this on any RX -> automatic reject (bug 1)
STALL_S = 2.5                         # no bytes for this long during a take -> port dead (bug 3)
PROTOCOL_VERSION = "p1"
RECORDER_VERSION = "1.1"
INCOMING, REJECTED = "_incoming", "_rejected"


class PortDied(Exception):
    folder: Path | None = None          # the aborted take in _incoming, set by record_take
    meta: dict | None = None


class QuitSession(Exception):
    pass


def find_port(token: str) -> str | None:
    d = Path("/dev/serial/by-id")
    if d.exists():
        for p in sorted(d.iterdir()):
            if token in p.name:
                return str(p)
    return None


def open_serial(port: str, baud: int):
    import serial
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, baud, 0.05
    s.dtr = False
    s.rts = False
    s.open()
    return s


class PortReader(threading.Thread):
    """Reads one port until stopped; while `sink` is set, raw bytes are written to it.

    A read error (USB unplugged, SerialException, OSError) does not kill the session silently:
    the thread records it in `error` and ends, and `alive()` turns False (bug 3).
    """

    def __init__(self, name, port, baud, opener=open_serial):
        super().__init__(daemon=True)
        self.name_, self.port, self.baud = name, port, baud
        self.s = opener(port, baud)
        self.sink = None
        self.lock = threading.Lock()
        self.bytes = 0
        self.last_byte_t = time.monotonic()
        self.error: str | None = None
        self.stop = threading.Event()

    def run(self):
        try:
            while not self.stop.is_set():
                chunk = self.s.read(65536)
                if not chunk:
                    continue
                self.bytes += len(chunk)
                self.last_byte_t = time.monotonic()
                with self.lock:
                    if self.sink:
                        self.sink.write(chunk)
        except Exception as e:  # serial.SerialException, OSError, ...
            self.error = f"{type(e).__name__}: {e}"
        finally:
            try:
                self.s.close()
            except Exception:
                pass

    def alive(self) -> bool:
        return self.error is None and self.is_alive()

    def silent_for(self) -> float:
        return time.monotonic() - self.last_byte_t

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
    """Quality check of a take. Returns (ok, has_csi, stats dict).

    ok      = every receiver meets MIN_RATE and MAX_GAP_MS (may still be kept by the operator)
    has_csi = every receiver has >= MIN_CSI_RECORDS CSI records from our TX (else auto-reject).
    File size is not used: with the TX off, RX files still hold STATS frames (bug 4).
    """
    stats, ok, has_csi = {}, True, True
    for name in expected:
        f = folder / f"{name}.bin"
        if not f.exists():
            stats[name] = dict(records=0, error="no file")
            ok = has_csi = False
            continue
        rec = cw.load(f)
        h = rec.hdr
        if rec.n:
            h = h[((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)]
        n = len(h)
        if n < MIN_CSI_RECORDS:
            stats[name] = dict(records=n, stats_frames=len(rec.stats), error="no CSI")
            ok = has_csi = False
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
    return ok, has_csi, stats


def read_plan(path: Path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["duration_s"] = float(r["duration_s"])
        r["cue_s"] = float(r["cue_s"]) if r.get("cue_s") else None
        r["pre_delay_s"] = float(r.get("pre_delay_s") or 3)
    return rows


def new_session_id(out_root: Path, subject: str, take: dict, day: str | None = None) -> str:
    day = day or dt.datetime.now().strftime("%Y%m%d")
    base = f"{day}_{subject}_{take['take_id']}_{take['activity']}"
    sid, k = base, 1
    while any((d / sid).exists() for d in (out_root, out_root / INCOMING, out_root / REJECTED)):
        k += 1
        sid = f"{base}_r{k}"
    return sid


def check_readers(readers: dict):
    for name, r in readers.items():
        if not r.alive():
            raise PortDied(f"{name}: reader stopped ({r.error or 'thread ended'})")
        if r.silent_for() > STALL_S:
            raise PortDied(f"{name}: no bytes for {r.silent_for():.1f} s (port silent; USB dropped?)")


def record_take(readers, take, args, out_root: Path, sleep=time.sleep):
    """Record one take into out_root/_incoming/<sid>/. Returns (folder, meta) — meta not written yet.

    Raises PortDied (folder left in _incoming, caller rejects it) if a reader dies or stalls.
    """
    sid = new_session_id(out_root, args.subject, take)
    folder = out_root / INCOMING / sid
    folder.mkdir(parents=True)
    meta = dict(
        session_id=sid, protocol=PROTOCOL_VERSION, plan=str(args.plan) if args.plan else "single",
        take_id=take["take_id"], kind=take["kind"], activity=take["activity"],
        position=take["position"], subject=args.subject, setting=args.setting,
        layout=args.layout, operator_position=args.operator_position,
        tx_power_dbm=args.tx_power, duration_s=take["duration_s"], cue_s=take["cue_s"],
        start_local=None, instruction=take["say"], valid=False, check={}, notes="",
    )
    try:
        for i in range(int(take["pre_delay_s"]), 0, -1):
            print(f"  starting in {i} ...", flush=True)
            sleep(1)
        check_readers(readers)
        files = {name: open(folder / f"{name}.bin", "wb") for name in readers}
        meta["start_local"] = dt.datetime.now().isoformat(timespec="seconds")
        t0 = time.monotonic()
        for name, r in readers.items():
            r.set_sink(files[name])
        say("  recording", False)
        cue_done = take["cue_s"] is None
        try:
            while (el := time.monotonic() - t0) < take["duration_s"]:
                if not cue_done and el >= take["cue_s"]:
                    beep(args.voice)
                    cue_done = True
                check_readers(readers)
                time.sleep(0.01)
        finally:
            for r in readers.values():
                r.set_sink(None)
            for f in files.values():
                f.close()
    except PortDied as e:
        e.folder, e.meta = folder, meta
        raise
    say("  done", args.voice)
    return folder, meta


def finalize(folder: Path, meta: dict, out_root: Path, keep: bool, note: str) -> Path:
    """Write meta.json (only now, after the decision: bug 5) and move the take out of _incoming."""
    meta = dict(meta, valid=bool(keep), notes=note)
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    dest_dir = out_root if keep else out_root / REJECTED
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / folder.name
    folder.rename(dest)                 # same file system: atomic
    return dest


def ask(prompt: str, allowed: dict, default: str, input_fn=input) -> str:
    """Ask until the answer is one of `allowed` (Enter = default). Unknown keys never keep (bug 2)."""
    while True:
        c = input_fn(prompt).strip().lower() or default
        if c in allowed:
            return allowed[c]
        print(f"  '{c}' is not an option: " + ", ".join(f"{k} = {v}" for k, v in allowed.items()))


KEEP_GOOD = {"k": "keep", "r": "redo", "x": "reject", "q": "quit"}
KEEP_BAD = {"r": "redo", "k": "keep", "x": "reject", "q": "quit"}


def decide(ok: bool, has_csi: bool, auto: bool, retried: bool, input_fn=input) -> tuple[str, str]:
    """Return (action, note) with action in keep | redo | reject | quit."""
    if not has_csi:
        return ("reject" if auto and retried else "redo"), "auto-rejected: no CSI on a receiver"
    if ok:
        if auto:
            return "keep", ""
        return ask("k = keep (Enter), r = redo, x = reject, q = quit (take not kept): ", KEEP_GOOD, "k",
                   input_fn), ""
    if auto:
        return ("reject" if retried else "redo"), "failed check"
    a = ask("r = redo (Enter), k = keep anyway, x = reject, q = quit (take not kept): ", KEEP_BAD, "r", input_fn)
    return a, ("kept by operator despite failed check" if a == "keep" else "failed check")


def open_readers(ports: dict, opener=open_serial) -> dict:
    readers = {}
    for name, (p, baud) in ports.items():
        r = PortReader(name, p, baud, opener)
        r.start()
        readers[name] = r
        print(f"{name}: {p} @ {baud}")
    return readers


def close_readers(readers: dict):
    for r in readers.values():
        r.stop.set()
    for r in readers.values():
        r.join(timeout=1)


def reconnect(names, args, opener=open_serial, input_fn=input, find=find_port) -> dict:
    """Ask the operator to fix the cable, then reopen every port by its by-id name."""
    while True:
        c = input_fn("Port lost. Re-plug it, then Enter = reconnect, q = quit: ").strip().lower()
        if c == "q":
            raise QuitSession("operator quit after a port was lost")
        ports = {n: (getattr(args, n.lower()) or find(TOKENS[n]), BAUDS[n]) for n in names}
        missing = [n for n, (p, _) in ports.items() if not p]
        if missing:
            print(f"  still not found: {missing}")
            continue
        try:
            readers = open_readers(ports, opener)
        except Exception as e:
            print(f"  could not open: {e}")
            continue
        time.sleep(1.5)
        if all(r.bytes > 0 for r in readers.values()):
            return readers
        print("  opened, but no bytes yet - is the board powered?")
        close_readers(readers)


def run_session(takes, args, readers, out_root: Path, input_fn=input, opener=open_serial, sleep=time.sleep):
    """Main loop. Returns (log, readers). log entries: (action, take_id, session folder name)."""
    log, i, retried = [], 0, False
    try:
        while i < len(takes):
            t = takes[i]
            print("\n" + "=" * 70)
            print(f"[{i + 1}/{len(takes)}] {t['take_id']}  {t['kind'].upper()}  activity={t['activity']}  "
                  f"position={t['position']}  {t['duration_s']:.0f}s" + (f"  cue at {t['cue_s']:.0f}s" if t['cue_s'] else ""))
            say(t["say"], args.voice)
            if not args.auto:
                c = ask("Enter = start, s = skip, q = quit: ", {"go": "start", "s": "skip", "q": "quit"}, "go", input_fn)
                if c == "quit":
                    break
                if c == "skip":
                    i += 1
                    continue
            try:
                folder, meta = record_take(readers, t, args, out_root, sleep=sleep)
            except PortDied as e:
                print(f"  ABORTED: {e}")
                if e.folder is not None:
                    dest = finalize(e.folder, e.meta, out_root, keep=False, note=f"aborted: {e}")
                    log.append(("aborted", t["take_id"], dest.name))
                close_readers(readers)
                readers = reconnect(list(readers), args, opener, input_fn)
                continue                                   # redo the same take
            ok, has_csi, stats = check_take(folder, t["duration_s"], tuple(readers))
            meta["check"] = stats
            for name, s in stats.items():
                print(f"  {name}: {s}")
            if not has_csi:
                print("  NO CSI on a receiver (TX off or receiver silent) - rejected automatically")
            elif ok:
                print(f"  GOOD -> {folder.name}")
            else:
                print("  BAD TAKE (rate or gaps)")
            action, note = decide(ok, has_csi, args.auto, retried, input_fn)
            dest = finalize(folder, meta, out_root, keep=(action == "keep"),
                            note=note if action != "quit" else "operator quit before keeping")
            log.append((action, t["take_id"], dest.name))
            print(f"  -> {dest.relative_to(out_root) if dest.is_relative_to(out_root) else dest}")
            if action == "quit":
                break
            if action == "redo":
                retried = True
                continue
            retried = False
            i += 1
    except QuitSession as e:
        print(str(e))
    return log, readers


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", type=Path, help="plan CSV (protocol/...)")
    ap.add_argument("--single", help="record one take of this activity instead of a plan")
    ap.add_argument("--kind", default="state", choices=["state", "event"])
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--cue", type=float, help="cue time for --single event takes")
    ap.add_argument("--position", default="-")
    ap.add_argument("--subject", required=True, help="S1, S2, ... or none")
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
    a = ap.parse_args(argv)

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
    for name in ("RX1", "RX2"):
        if a.only in (None, name):
            ports[name] = (getattr(a, name.lower()) or find_port(TOKENS[name]), BAUDS[name])
    for name, (p, _) in ports.items():
        if not p:
            print(f"{name} not found in /dev/serial/by-id (use --{name.lower()} PORT)")
            return 1
    readers = open_readers(ports)
    time.sleep(1.5)
    for name, r in readers.items():
        if r.bytes == 0:
            print(f"WARNING: no bytes from {name} yet - is it powered and flashed?")

    a.out.mkdir(parents=True, exist_ok=True)
    left = sorted(p.name for p in (a.out / INCOMING).glob("*")) if (a.out / INCOMING).exists() else []
    if left:
        print(f"NOTE: {len(left)} undecided take(s) from an earlier run in {a.out / INCOMING}: {left}")
    try:
        log, readers = run_session(takes, a, readers, a.out)
    except KeyboardInterrupt:
        print(f"\nstopped; an undecided take (if any) stays in {a.out / INCOMING}")
        close_readers(readers)
        return 130
    close_readers(readers)
    kept = sum(1 for k, _, _ in log if k == "keep")
    print(f"\nfinished: {kept} takes kept in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
