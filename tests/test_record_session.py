"""Recorder fixes for the 22 Oct bugs, with simulated ports (no hardware, SYNTHETIC frames)."""
import json
import types

import pytest

from host import record_session as rs
from host.tests.make_synthetic_dataset import frame
from host import csiwire as cw
from tests.fake_serial import opener_for


def make_args(**kw):
    a = dict(plan=None, subject="S9", setting="same_room", layout="layout_test", operator_position="O",
             tx_power=5.0, voice=False, auto=False, rx1="fake1", rx2="fake2")
    a.update(kw)
    return types.SimpleNamespace(**a)


TAKE = dict(take_id="T01", kind="state", activity="sit", position="A", duration_s=1.0, cue_s=None,
            pre_delay_s=0, say="sit")
TAKE2 = dict(TAKE, take_id="T02", activity="stand")


def answers(*seq):
    it = iter(seq)

    def f(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError(f"unexpected prompt: {prompt}")
    return f


def session(tmp_path, takes, inputs, spec=None, reconnect_spec=None, **kw):
    readers = rs.open_readers({"RX1": ("fake1", 115200), "RX2": ("fake2", 2_000_000)}, opener_for(spec or {}))
    log, readers = rs.run_session(takes, make_args(**kw), readers, tmp_path, input_fn=answers(*inputs),
                                  opener=opener_for(reconnect_spec or {}), sleep=lambda s: None)
    rs.close_readers(readers)
    return log


def kept(tmp_path):
    return sorted(p.name for p in tmp_path.iterdir() if p.is_dir() and not p.name.startswith("_"))


def rejected(tmp_path):
    d = tmp_path / rs.REJECTED
    return {p.name: json.loads((p / "meta.json").read_text()) for p in d.iterdir()} if d.exists() else {}


def incoming(tmp_path):
    d = tmp_path / rs.INCOMING
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def test_good_take_is_kept_with_meta_written_after_decision(tmp_path):
    log = session(tmp_path, [TAKE], ["", ""])          # Enter = start, Enter = keep
    assert [a for a, _, _ in log] == ["keep"]
    (sid,) = kept(tmp_path)
    meta = json.loads((tmp_path / sid / "meta.json").read_text())
    assert meta["valid"] is True and meta["check"]["RX1"]["records"] > 150
    assert incoming(tmp_path) == []


def test_bug1_zero_csi_is_rejected_automatically(tmp_path):
    # RX2 sends only STATS (TX off). The take must never be keepable; operator then quits.
    log = session(tmp_path, [TAKE], ["", "q"], spec={"fake2": {"mode": "no_csi"}})
    assert kept(tmp_path) == []
    (m,) = rejected(tmp_path).values()
    assert m["valid"] is False and "no CSI" in m["notes"] and m["check"]["RX2"]["error"] == "no CSI"
    assert [a for a, _, _ in log] == ["redo"]


def test_bug2_q_at_keep_prompt_quits_and_does_not_keep(tmp_path):
    log = session(tmp_path, [TAKE, TAKE2], ["", "q"])
    assert kept(tmp_path) == []
    assert [a for a, _, _ in log] == ["quit"]
    (m,) = rejected(tmp_path).values()
    assert m["take_id"] == "T01" and "quit" in m["notes"]


def test_bug2_unknown_key_reprompts_instead_of_keeping(tmp_path):
    session(tmp_path, [TAKE], ["", "z", "maybe", "x"])
    assert kept(tmp_path) == [] and len(rejected(tmp_path)) == 1


def test_bad_take_keep_anyway_is_explicit(tmp_path):
    session(tmp_path, [TAKE], ["", "k"], spec={"fake2": {"rate": 120}})
    (sid,) = kept(tmp_path)
    meta = json.loads((tmp_path / sid / "meta.json").read_text())
    assert meta["valid"] is True and meta["notes"] == "kept by operator despite failed check"
    assert meta["check"]["RX2"]["ok"] is False


@pytest.mark.parametrize("mode", ["die", "silent"])
def test_bug3_dead_port_aborts_take_then_reconnects_and_redoes(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(rs, "STALL_S", 0.3)
    # start, (port dies) -> Enter = reconnect, start again, keep
    log = session(tmp_path, [TAKE], ["", "", "", ""], spec={"fake2": {"mode": mode, "die_after": 0.3}})
    assert [a for a, _, _ in log] == ["aborted", "keep"]
    (m,) = rejected(tmp_path).values()
    assert m["valid"] is False and m["notes"].startswith("aborted: RX2")
    assert len(kept(tmp_path)) == 1 and kept(tmp_path)[0].endswith("_r2")


def test_bug3_quit_at_reconnect(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STALL_S", 0.3)
    log = session(tmp_path, [TAKE], ["", "q"], spec={"fake1": {"mode": "die", "die_after": 0.2}})
    assert [a for a, _, _ in log] == ["aborted"] and kept(tmp_path) == []


def test_reader_records_error_instead_of_dying_silently():
    r = rs.PortReader("RX2", "fake2", 2_000_000, opener_for({"fake2": {"mode": "die", "die_after": 0.05}}))
    r.start()
    r.join(timeout=2)
    assert not r.alive() and "SerialException" in r.error


def test_bug5_interrupt_at_prompt_leaves_take_out_of_raw(tmp_path):
    def inp(prompt=""):
        if prompt.startswith("Enter"):
            return ""
        raise KeyboardInterrupt
    readers = rs.open_readers({"RX1": ("fake1", 1), "RX2": ("fake2", 1)}, opener_for({}))
    with pytest.raises(KeyboardInterrupt):
        rs.run_session([TAKE], make_args(), readers, tmp_path, input_fn=inp, sleep=lambda s: None)
    rs.close_readers(readers)
    assert kept(tmp_path) == []
    (sid,) = incoming(tmp_path)
    assert not (tmp_path / rs.INCOMING / sid / "meta.json").exists()


def test_session_ids_skip_incoming_and_rejected(tmp_path):
    for d in (tmp_path / "20261022_S9_T01_sit", tmp_path / rs.INCOMING / "20261022_S9_T01_sit_r2",
              tmp_path / rs.REJECTED / "20261022_S9_T01_sit_r3"):
        d.mkdir(parents=True)
    assert rs.new_session_id(tmp_path, "S9", TAKE, day="20261022") == "20261022_S9_T01_sit_r4"


def test_bug4_stats_only_file_is_not_a_take(tmp_path):
    data = b"".join(frame(cw.T_STATS, json.dumps({"type": "stats", "pad": "x" * 200}).encode()) for _ in range(20))
    (tmp_path / "RX1.bin").write_bytes(data)
    (tmp_path / "RX2.bin").write_bytes(data)
    assert (tmp_path / "RX1.bin").stat().st_size > 1000
    ok, has_csi, stats = rs.check_take(tmp_path, 10.0)
    assert not ok and not has_csi and stats["RX1"]["stats_frames"] == 20


@pytest.mark.parametrize("ok,has_csi,auto,retried,expect", [
    (True, True, True, False, "keep"), (False, True, True, False, "redo"), (False, True, True, True, "reject"),
    (False, False, True, False, "redo"), (False, False, True, True, "reject"), (False, False, False, False, "redo")])
def test_decide_auto_rules(ok, has_csi, auto, retried, expect):
    assert rs.decide(ok, has_csi, auto, retried, input_fn=answers())[0] == expect
