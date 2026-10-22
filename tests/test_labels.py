"""Event/state window labelling (pipeline/labels.py)."""
import numpy as np

from pipeline import labels as lb

EV = dict(session_id="X_S9_E01_sit_down", kind="event", activity="sit_down", cue_s=3.0,
          instruction="Stand in front of the chair. On the beep sit down normally.")


def test_state_take_all_windows_get_activity():
    m = dict(session_id="X", kind="state", activity="walk", instruction="")
    lab, src = lb.label_windows(m, np.arange(0, 27), 3.0)
    assert set(lab) == {"walk"} and set(src) == {"state"}


def test_event_overlap_rule_and_pre_post():
    on = dict(detected=True, onset=4.0, end=5.5, early=False, short=False)
    starts = np.arange(0, 7.5, 0.5)                                     # 3 s windows
    lab, src = lb.label_windows(EV, starts, 3.0, on)
    d = dict(zip(starts, lab))
    assert d[0.0] == "stand" and d[0.5] == "stand"                      # end 3.5 <= 4.0 - 0.3
    assert d[1.0] == ""                                                 # ends 4.0: transition
    assert d[2.5] == "sit_down" and d[3.0] == "sit_down" and d[4.0] == "sit_down"
    assert d[6.0] == "sit"                                              # starts 6.0 >= 5.5 + 0.3
    assert "fall" not in lab


def test_long_interval_vs_short_window_uses_min_length():
    on = dict(detected=True, onset=4.0, end=8.0, early=False, short=False)    # 4 s action, 2 s window
    lab, _ = lb.label_windows(dict(EV, activity="bend_pick"), np.array([5.0]), 2.0, on)
    assert lab[0] == "bend_pick"


def test_unusable_event_takes_give_no_event_windows():
    starts = np.arange(0, 7.5, 0.5)
    for on in (None, dict(detected=False), dict(detected=True, onset=3.0, end=5.0, early=True, short=False),
               dict(detected=True, onset=4.0, end=4.3, early=False, short=True)):
        lab, src = lb.label_windows(EV, starts, 3.0, on)
        assert "sit_down" not in lab and set(src) <= {"event_pre", "transition"}
        assert all(s + 3.0 <= 3.0 - lb.GUARD_S for s, l in zip(starts, lab) if l)


def test_walking_start_fall_pre_label_and_exclusion():
    m = dict(session_id="20261022_S2_E57_fall", kind="event", activity="fall", cue_s=3.0,
             instruction="Walk slowly toward the mattress. On the beep fall forward onto it.")
    on = dict(detected=True, onset=3.0, end=6.5, early=True, short=False)
    lab, src = lb.label_windows(m, np.arange(0, 7.5, 0.5), 2.0, on)
    assert "fall" not in lab
    assert set(lab[src == "event_pre"]) == {"walk"} and set(lab[src == "event_post"]) == {"lie"}
    ok, why = lb.event_usable(m, on)
    assert not ok and "D-038" in why
