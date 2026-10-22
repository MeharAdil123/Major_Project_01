"""D-031 set-up drift check, on SYNTHETIC rows (never reads data/raw)."""
import importlib.util

from tests.conftest import ROOT

spec = importlib.util.spec_from_file_location("audit_raw", ROOT / "scripts" / "audit_raw.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def row(sid, subj, act, pos, r1, r2):
    return dict(session_id=sid, subject=subj, activity=act, position=pos, RX1_rssi_med=r1, RX2_rssi_med=r2)


BASE = [row("b1", "S1", "sit", "A", -46, -40), row("b2", "S2", "sit", "A", -44, -41),
        row("b3", "S3", "sit", "A", -45, -39), row("e1", "none", "empty", "none", -36, -38),
        row("f1", "S1", "fall", "M", -38, -40)]


def test_flags_per_take_against_same_activity_and_position():
    new = [row("n1", "S5", "sit", "A", -45, -40),        # same as baseline median
           row("n2", "S5", "sit", "A", -49.5, -40),      # RX1 4.5 dB lower -> flag
           row("n3", "S5", "empty", "none", -36, -34.5), # RX2 +3.5 -> flag
           row("n4", "S5", "walk", "path1", -37, -37)]   # no reference
    per_take, per_subject = audit.rssi_drift(new, BASE, tol=3.0)
    t = {x["session_id"]: x for x in per_take}
    assert not t["n1"]["flag"] and t["n1"]["RX1_diff"] == 0.0
    assert t["n2"]["flag"] and t["n2"]["RX1_diff"] == -4.5
    assert t["n3"]["flag"] and t["n3"]["RX2_diff"] == 3.5
    assert not t["n4"]["flag"] and t["n4"]["RX1_ref_range"] == "no reference"
    assert per_subject["S5"]["n"] == 3 and not per_subject["S5"]["flag"]


def test_whole_subject_shift_is_flagged():
    new = [row("n1", "S6", "sit", "A", -49, -44), row("n2", "S6", "fall", "M", -42, -44),
           row("n3", "S6", "empty", "none", -40, -42)]
    _, per_subject = audit.rssi_drift(new, BASE, tol=3.0)
    assert per_subject["S6"]["flag"] and per_subject["S6"]["RX1"] == -4.0 and per_subject["S6"]["RX2"] == -4.0


def test_exactly_tol_is_not_flagged():
    per_take, _ = audit.rssi_drift([row("n", "S5", "fall", "M", -41, -40)], BASE, tol=3.0)
    assert not per_take[0]["flag"]
