"""Exercise EX8d: a double-press detector (docs/exercises/EX8d_doublepress.md).
The detection tests fail until ctl/src/ctl_button_double.c is written; the "never" tests pass
with the stub and must keep passing. The contract here is a proposal: if you design it
differently, change these tests with it and say why in the exercise notes.
Run: python -m pytest tests/exercises/test_ex8d_doublepress.py
"""
import ctypes

import numpy as np
import pytest

import ctllib

WINDOW_MS = 300  # CTL_DOUBLE_WINDOW_MS


def contact(*segments):
    return np.concatenate([np.full(ms, state, dtype=np.uint8) for state, ms in segments])


def doubles(ctl, stream):
    """Debounces a contact stream and feeds the events to the detector; returns the sample
    indices where it reported a double press, and the indices of the press events."""
    btn = ctllib.Button(ctl)
    ev = btn.run(stream)
    buf = ctypes.create_string_buffer(ctl.ctl_sizeof_double())
    d = ctypes.cast(buf, ctypes.c_void_p)
    ctl.ctl_double_init(d)
    hits = [i for i, e in enumerate(ev) if ctl.ctl_double_update(d, int(e))]
    return hits, list(np.nonzero(ev & ctllib.PRESS)[0])


def presses(*gaps_ms, hold_ms=60):
    """Presses of hold_ms whose press-to-press intervals are gaps_ms."""
    segs = [(0, 20)]
    for g in gaps_ms:
        segs += [(1, hold_ms), (0, g - hold_ms)]
    segs += [(1, hold_ms), (0, 1000)]
    return contact(*segs)


# ---- Never a double (pass with the stub; must keep passing) ---------------------------------

def test_single_presses_far_apart_never(ctl):
    hits, _ = doubles(ctl, presses(800, 800, 800))
    assert hits == []


def test_slow_pair_never(ctl):
    hits, _ = doubles(ctl, presses(WINDOW_MS + 50))
    assert hits == []


def test_long_hold_then_press_never(ctl):
    hits, _ = doubles(ctl, contact((0, 20), (1, 700), (0, 100), (1, 60), (0, 500)))
    assert hits == []


# ---- Doubles (fail until the exercise is done) ----------------------------------------------

@pytest.mark.parametrize("gap", [80, 200, WINDOW_MS])
def test_quick_pair_is_one_double_at_the_second_press(ctl, gap):
    hits, press = doubles(ctl, presses(gap))
    assert hits == [press[1]]


def test_triple_is_one_double(ctl):
    hits, press = doubles(ctl, presses(150, 150))
    assert hits == [press[1]]


def test_quadruple_is_two_doubles(ctl):
    hits, press = doubles(ctl, presses(150, 150, 150))
    assert hits == [press[1], press[3]]


def test_bouncing_contacts_do_not_fake_a_double(ctl):
    """One press with 3 ms of bounce at each edge is one press, not two."""
    rng = np.random.default_rng(2)
    b1 = rng.integers(0, 2, 3).astype(np.uint8)
    b2 = rng.integers(0, 2, 3).astype(np.uint8)
    hits, press = doubles(ctl, np.concatenate([contact((0, 20)), b1, contact((1, 80)), b2,
                                               contact((0, 500))]))
    assert len(press) == 1 and hits == []
    # And a real double still counts with the bounce.
    stream = np.concatenate([contact((0, 20)), b1, contact((1, 60)), b2, contact((0, 100)),
                             b1, contact((1, 60)), b2, contact((0, 500))])
    hits, press = doubles(ctl, stream)
    assert hits == [press[1]]
