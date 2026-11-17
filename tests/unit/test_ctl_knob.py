"""Knob ownership and pick-up (SPEC 6.7, docs/notes/knob_pickup.md)."""
import numpy as np
import pytest

import ctllib

KNOB = "tone_bass_db"  # -12..+12 dB, linear: position x gives 24 x - 12


def pc_wins(dev, name=KNOB):
    assert dev.set("mode_" + name.removesuffix("_db"), 1.0) == ctllib.OK


def db(x):
    return 24.0 * x - 12.0


def test_knob_wins_refuses_the_pc_midi_and_presets(dev):
    dev.knob(KNOB, 0.75)
    assert dev.get(KNOB) == pytest.approx(6.0)
    for src in (ctllib.SRC_PC, ctllib.SRC_MIDI, ctllib.SRC_PRESET):
        assert dev.set(KNOB, -3.0, src) == ctllib.ERR_KNOB_WINS
    assert dev.get(KNOB) == pytest.approx(6.0)
    final, _ = dev.cmd("set tone_bass_db -3")
    assert final.startswith("err 5 knob wins")


def test_pc_wins_detaches_the_knob(dev):
    pc_wins(dev)
    dev.knob(KNOB, 0.5)
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(KNOB)) == 1
    assert dev.set(KNOB, 6.0) == ctllib.OK
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(KNOB)) == 0
    dev.knob(KNOB, 0.55)  # Moves, but has not reached 6 dB (x = 0.75): ignored.
    assert dev.get(KNOB) == 6.0


@pytest.mark.parametrize("start,direction", [(0.2, +1), (0.95, -1)])
def test_no_jump_on_re_attach_from_either_side(dev, start, direction):
    pc_wins(dev)
    dev.knob(KNOB, start)
    dev.set(KNOB, 6.0)  # x = 0.75
    values = [dev.get(KNOB)]
    x = start
    for _ in range(400):
        x = float(np.clip(x + direction * 0.002, 0, 1))
        dev.knob(KNOB, x)
        values.append(dev.get(KNOB))
    steps = np.abs(np.diff(values))
    # Never more than the knob's own movement (0.002 of travel, 0.048 dB) plus the 1 % that the
    # pick-up hysteresis holds back, released in one step.
    assert steps.max() <= 24.0 * (0.002 + 0.01) + 1e-4
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(KNOB)) == 1
    assert dev.get(KNOB) == pytest.approx(db(x), abs=1e-4), "it follows once attached"


def test_fast_turn_crossing_between_two_readings(dev):
    pc_wins(dev)
    dev.knob(KNOB, 0.1)
    dev.set(KNOB, 0.0)  # x = 0.5
    dev.knob(KNOB, 0.9)  # One reading jumps across the value.
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(KNOB)) == 1
    assert dev.get(KNOB) == pytest.approx(db(0.9))


def test_reading_noise_near_the_value_changes_nothing(dev):
    pc_wins(dev)
    dev.knob(KNOB, 0.2)
    dev.set(KNOB, 0.0)  # x = 0.5
    rng = np.random.default_rng(3)
    for _ in range(2000):
        dev.knob(KNOB, float(0.5 + rng.uniform(-0.01, 0.01)))
        assert dev.get(KNOB) == 0.0
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(KNOB)) == 1
    dev.knob(KNOB, 0.53)  # A real turn leaves the hysteresis: it follows.
    assert dev.get(KNOB) == pytest.approx(db(0.53))


def test_mode_change_while_detached(dev):
    pc_wins(dev)
    dev.knob(KNOB, 0.25)
    dev.set(KNOB, 9.0)
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(KNOB)) == 0
    final, _ = dev.cmd("mode tone_bass_db knob")
    assert final == "ok mode tone_bass_db knob attached=1"
    assert dev.get(KNOB) == pytest.approx(db(0.25)), "knob wins: the knob's value at once"
    final, _ = dev.cmd("mode tone_bass_db pc")
    assert final == "ok mode tone_bass_db pc attached=1", "still attached: nothing moved"


def test_mode_change_before_any_reading_keeps_the_value(dev):
    pc_wins(dev)
    dev.set(KNOB, 9.0)
    dev.cmd("mode tone_bass_db knob")
    assert dev.get(KNOB) == 9.0, "the knob's position is unknown until its first reading"


def test_preset_recall_detaches_every_pc_wins_knob(dev):
    knobs = ["tone_bass_db", "tone_mid_db", "tone_treble_db", "fx_amount", "blend"]
    for name in knobs:
        dev.knob(name, 0.3)  # Knob wins: attached at once.
        pc_wins(dev, name)  # Still attached: nothing moved.
        assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(name)) == 1
    dev.set("tone_mid_db", 3.0)  # The PC detaches the mid knob...
    assert dev.save(0) == 0
    dev.knob("tone_mid_db", 0.7)  # ...which picks up again by crossing 3 dB (x = 0.625).
    assert dev.lib.ctl_core_knob_attached(dev.core, dev.index("tone_mid_db")) == 1
    assert dev.load(0) == 0
    for name in knobs:
        assert dev.lib.ctl_core_knob_attached(dev.core, dev.index(name)) == 0, name
    assert dev.get("tone_mid_db") == 3.0


def test_knob_reports_to_the_pc_and_to_midi(dev):
    dev.knob(KNOB, 0.75)
    assert dev.poll() == ["# set tone_bass_db 6"]
    assert dev.midi_out() == [0xB0, 20, 96]  # 0.75 of travel is CC 96 with the centred scaling
    dev.set("mode_tone_bass", 1.0)
    dev.set(KNOB, 1.0)  # From the PC: no echo to the PC, no CC out.
    assert dev.poll() == [] and dev.midi_out() == []


def test_not_a_knob(dev):
    assert dev.knob("tone_bass_hz", 0.5) == ctllib.ERR_NOT_KNOB
    assert dev.knob(KNOB, float("nan")) == 4
