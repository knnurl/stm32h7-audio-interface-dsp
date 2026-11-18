"""ctl_button with synthetic contact streams: clean presses, contact bounce, interference
glitches, long and short presses; and the C against the reference model
(docs/notes/panel_input.md)."""
import numpy as np
import pytest

import ctllib
from ctllib import LONG, PRESS, RELEASE, SHORT
from ref import panel as ref


@pytest.fixture
def btn(ctl):
    return ctllib.Button(ctl)


def contact(*segments):
    """Concatenated (state, ms) segments."""
    return np.concatenate([np.full(ms, state, dtype=np.uint8) for state, ms in segments])


def bounce(rng, ms, closing):
    """A bouncing contact for `ms` milliseconds, any pattern, ending in the settled state."""
    b = rng.integers(0, 2, ms).astype(np.uint8)
    b[-1] = 1 if closing else 0
    return b


def events(ev, kind):
    return np.nonzero(ev & kind)[0]


def test_c_matches_the_reference(btn):
    rng = np.random.default_rng(0)
    stream = np.concatenate([contact((0, 20))] + [
        np.repeat(rng.integers(0, 2, 200), rng.integers(1, 12, 200)).astype(np.uint8)
        for _ in range(5)] + [contact((1, 900), (0, 50))])
    model = ref.Button()
    want = np.array([model.update(int(c)) for c in stream], dtype=np.uint8)
    assert np.array_equal(btn.run(stream), want)


def test_clean_press_and_release(btn):
    ev = btn.run(contact((0, 10), (1, 100), (0, 50)))
    assert list(events(ev, PRESS)) == [10 + 4]  # The 5th closed sample.
    assert list(events(ev, RELEASE)) == [110 + 4]
    assert list(events(ev, SHORT)) == [110 + 4]
    assert len(events(ev, LONG)) == 0


@pytest.mark.parametrize("seed", range(200))
def test_bounce_up_to_4_ms_gives_one_press_and_one_release(btn, seed):
    rng = np.random.default_rng(seed)
    stream = np.concatenate([
        contact((0, 20)), bounce(rng, int(rng.integers(1, 5)), True), contact((1, 80)),
        bounce(rng, int(rng.integers(1, 5)), False), contact((0, 40))])
    ev = btn.run(stream)
    assert len(events(ev, PRESS)) == 1 and len(events(ev, RELEASE)) == 1


@pytest.mark.parametrize("seed", range(50))
def test_longer_bounce_mostly_closed_still_gives_one_press(btn, seed):
    """Bounce of up to 15 ms with the contact closed at least two samples in three."""
    rng = np.random.default_rng(1000 + seed)
    ms = int(rng.integers(5, 16))
    b = (rng.random(ms) < 0.7).astype(np.uint8)
    b[-1] = 1
    ev = btn.run(np.concatenate([contact((0, 20)), b, contact((1, 80), (0, 40))]))
    assert len(events(ev, PRESS)) == 1 and len(events(ev, RELEASE)) == 1


def test_single_sample_glitches_change_nothing(btn):
    """Interference: one-sample spikes every 3 ms on an open line, then one-sample drop-outs
    every 3 ms on a held button."""
    open_line = np.zeros(300, dtype=np.uint8)
    open_line[::3] = 1
    held = np.ones(300, dtype=np.uint8)
    held[::3] = 0
    ev = btn.run(open_line)
    assert ev.sum() == 0
    ev = btn.run(np.concatenate([contact((1, 20)), held, contact((1, 20))]))
    assert len(events(ev, PRESS)) == 1 and len(events(ev, RELEASE)) == 0


def test_long_press_once_and_no_short(btn):
    ev = btn.run(contact((0, 10), (1, 2000), (0, 20)))
    press = events(ev, PRESS)[0]
    assert list(events(ev, LONG)) == [press + 600]
    assert len(events(ev, RELEASE)) == 1 and len(events(ev, SHORT)) == 0


def test_just_under_long_is_short(btn):
    # Both edges are delayed alike, so the debounced hold is the contact's closed time.
    ev = btn.run(contact((0, 10), (1, 600), (0, 20)))
    assert len(events(ev, LONG)) == 0 and len(events(ev, SHORT)) == 1
    btn2 = ctllib.Button(btn.lib)
    ev = btn2.run(contact((0, 10), (1, 601), (0, 20)))
    assert len(events(ev, LONG)) == 1 and len(events(ev, SHORT)) == 0


def test_tap_intervals_are_kept(btn):
    """Every press is delayed by the same 5 ms, so tap intervals pass through exactly."""
    stream = np.concatenate([contact((0, 7), (1, 60), (0, 340)) for _ in range(6)])
    presses = events(btn.run(stream), PRESS)
    assert set(np.diff(presses)) == {407}
