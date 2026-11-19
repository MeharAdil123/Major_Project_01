"""Onset/end detector (pipeline/onset.py) on SYNTHETIC grids."""
import numpy as np
import pytest

from pipeline import onset as od


def grid(seconds=10.0, burst=None, scale_steps=0.0, seed=0, rx_gain=(1.0, 0.4)):
    rng = np.random.default_rng(seed)
    L, S = int(seconds * 200), 114
    t = np.arange(L) / 200
    base = 20 + 5 * np.sin(np.arange(S) / 7.0)
    amp = np.empty((2, L, S))
    for r in range(2):
        a = base[None, :] * (1 + 0.03 * rng.standard_normal((L, S)))       # packet noise
        if burst:
            on, end = burst
            m = (t >= on) & (t < end)
            wave = np.sin(2 * np.pi * 1.5 * t[m])[:, None] * np.cos(np.arange(S) / 5.0)[None, :]
            a[m] *= 1 + 0.25 * rx_gain[r] * wave
        if scale_steps:
            a[rng.random(L) < scale_steps] *= 0.5                           # ESP32 per-packet 6 dB shifts
        amp[r] = a
    return dict(seq0=0, amp=amp.astype(np.float32), rssi=np.zeros((2, L)), missing=np.zeros((2, L), bool))


@pytest.mark.parametrize("burst", [(4.0, 5.0), (3.5, 6.0), (5.2, 6.0)])
def test_detects_burst_onset_and_end(burst):
    t, m = od.motion_signal(grid(burst=burst))
    d = od.detect(t, m, cue_s=3.0)
    assert d["detected"] and d["peak_ratio"] > 3
    assert abs(d["onset"] - burst[0]) <= 0.25 and abs(d["end"] - burst[1]) <= 0.3
    assert d["inside_search"] == (burst[1] <= 7.0)
    assert d["rx1_detected"] and abs(d["rx1_onset"] - burst[0]) <= 0.3


def test_still_take_is_not_detected_even_with_scale_steps():
    t, m = od.motion_signal(grid(scale_steps=0.3))
    d = od.detect(t, m, cue_s=3.0)
    assert not d["detected"] and d["peak_ratio"] < od.THR_HI


def test_scale_steps_do_not_hide_or_shift_a_burst():
    t, m = od.motion_signal(grid(burst=(4.0, 5.0), scale_steps=0.3))
    d = od.detect(t, m, cue_s=3.0)
    assert d["detected"] and abs(d["onset"] - 4.0) <= 0.25


def test_global_baseline_for_takes_that_start_moving():
    g = grid(burst=(0.0, 8.0))                                  # moving the whole take
    t, m = od.motion_signal(g)
    own = od.detect(t, m, cue_s=3.0)
    still_base = np.median(od.motion_signal(grid(seed=3))[1], axis=1)
    glob = od.detect(t, m, cue_s=3.0, baseline=still_base)
    assert min(glob["pre_level"]) > 3                           # pre-cue clearly not still
    assert not own["detected"]                                  # own baseline hides the motion


def test_end_uses_post_action_level_when_end_posture_moves_more():
    g = grid(burst=(4.0, 5.0))
    rng = np.random.default_rng(9)
    t = np.arange(g["amp"].shape[1]) / 200
    post = t >= 5.0
    # end posture: packet noise 1.7x higher than before the action (e.g. sitting vs standing)
    g["amp"][:, post] *= (1 + 0.04 * rng.standard_normal(g["amp"][:, post].shape)).astype(np.float32)
    tt, m = od.motion_signal(g)
    d = od.detect(tt, m, cue_s=3.0)
    assert d["detected"] and abs(d["end"] - 5.0) <= 0.4 and d["inside_search"]


def test_motion_before_cue_is_clipped_and_flagged():
    tt, m = od.motion_signal(grid(burst=(2.0, 4.5)))
    d = od.detect(tt, m, cue_s=3.0)
    assert d["detected"] and d["early"] and d["onset"] == 3.0 and not d["inside_search"]


def test_two_part_action_is_one_interval():
    g = grid(burst=(4.0, 4.7))
    g2 = grid(burst=(5.6, 6.4), seed=0)
    t = np.arange(g["amp"].shape[1]) / 200
    late = t >= 5.0
    g["amp"][:, late] = g2["amp"][:, late]                       # bend down 4.0-4.7, pause, rise 5.6-6.4
    tt, m = od.motion_signal(g)
    d = od.detect(tt, m, cue_s=3.0)
    assert d["detected"] and abs(d["onset"] - 4.0) <= 0.25 and abs(d["end"] - 6.4) <= 0.3


def test_weak_wiggle_is_not_merged():
    tt, m = od.motion_signal(grid(burst=(4.0, 5.0)))
    d = od.detect(tt, m, cue_s=3.0)
    assert d["end"] <= 5.3
