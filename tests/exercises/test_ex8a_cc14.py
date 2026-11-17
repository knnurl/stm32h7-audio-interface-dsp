"""Exercise EX8a: 14-bit control change for the tone gains (docs/exercises/EX8a_cc14.md).
The resolution tests fail until ctl/src/ctl_midi_cc14.c is written; the 7-bit tests pass with
the stub and must keep passing.
Run: python -m pytest tests/exercises/test_ex8a_cc14.py
"""
import pytest

import ctllib

COARSE = {"tone_bass_db": 20, "tone_mid_db": 21, "tone_treble_db": 22}


@pytest.fixture
def dev(ctl):
    d = ctllib.Device(ctl)
    for name in COARSE:
        d.set("mode_" + name.removesuffix("_db"), 1.0)  # PC wins: MIDI may write.
    return d


def send(dev, *pairs):
    msg = []
    for cc, value in pairs:
        msg += [0xB0, cc, value]
    dev.midi(msg)


# ---- A 7-bit-only controller (passes with the stub; must keep passing) ------------------------

@pytest.mark.parametrize("value,db", [(0, -12.0), (64, 0.0), (127, 12.0)])
def test_seven_bit_controller_reaches_both_ends_and_the_centre(dev, value, db):
    for name, cc in COARSE.items():
        send(dev, (cc, value))
        assert dev.get(name) == db


def test_fine_part_alone_is_ignored(dev):
    send(dev, (52, 100))
    assert dev.get("tone_bass_db") == 0.0


def test_coarse_then_fine_zero_equals_coarse_alone(dev, ctl):
    for msb in range(128):
        send(dev, (20, msb))
        seven = dev.get("tone_bass_db")
        send(dev, (52, 0))
        assert dev.get("tone_bass_db") == seven, msb


def test_a_new_coarse_part_resets_the_fine_part(dev):
    send(dev, (20, 10), (52, 100), (20, 11))
    alone = ctllib.Device(dev.lib)
    alone.set("mode_tone_bass", 1.0)
    send(alone, (20, 11))
    assert dev.get("tone_bass_db") == alone.get("tone_bass_db")


# ---- 14 bits (fail until the exercise is done) ------------------------------------------------

def test_fine_part_refines_monotonically(dev):
    values = []
    for msb in range(128):
        for lsb in range(128):
            send(dev, (20, msb), (52, lsb))
            values.append(dev.get("tone_bass_db"))
    assert all(b >= a for a, b in zip(values, values[1:])), "never goes backwards"
    assert len(set(values)) >= 16000, f"only {len(set(values))} distinct values"
    assert values[0] == -12.0 and values[-1] == 12.0
    assert values[64 * 128] == 0.0, "coarse 64, fine 0 is flat"


def test_fine_part_belongs_to_its_own_parameter(dev):
    send(dev, (20, 64), (21, 64), (53, 127))
    assert dev.get("tone_bass_db") == 0.0
    assert dev.get("tone_mid_db") > 0.0


def test_running_status_carries_the_pair(dev):
    dev.midi([0xB0, 22, 64, 54, 127])
    assert dev.get("tone_treble_db") > 0.0
