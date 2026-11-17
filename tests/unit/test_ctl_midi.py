"""ctl_midi: the parser (running status, real-time bytes inside messages, system exclusive),
channel filtering, the map, program change and control change out."""
import pytest

import ctllib

# The CC numbers the MIDI 1.0 specification leaves undefined.
UNDEFINED = {3, 9, 14, 15, *range(20, 32), *range(85, 91), *range(102, 120)}


def pc(dev, name):
    dev.set("mode_" + name.removesuffix("_db"), 1.0)


def test_map_rules(ctl):
    ccs = []
    for i in range(ctl.ctl_midi_map_count()):
        e = ctl.ctl_midi_map_entry(i).contents
        assert e.cc in UNDEFINED, e.cc
        ccs.append(e.cc)
        if e.param_id:
            idx = ctl.ctl_param_index_of(e.param_id)
            assert idx >= 0
            d = ctl.ctl_param_desc(idx).contents
            assert not d.flags & ctllib.FLAG_READ_ONLY
            assert ctl.ctl_midi_cc_of(idx) == e.cc
    assert len(ccs) == len(set(ccs))
    for i, d in ctllib.params(ctl):
        if d.flags & (ctllib.FLAG_KNOB | ctllib.FLAG_BUTTON):
            assert ctl.ctl_midi_cc_of(i) >= 0, f"panel control {d.name} has no CC"


def test_control_change_scales_along_the_curve(dev):
    dev.midi([0xB0, 90, 0])   # rev_decay_s, log 0.2..10
    assert dev.get("rev_decay_s") == pytest.approx(0.2)
    dev.midi([0xB0, 90, 127])
    assert dev.get("rev_decay_s") == pytest.approx(10.0)
    dev.midi([0xB0, 90, 64])
    assert dev.get("rev_decay_s") == pytest.approx((0.2 * 10.0) ** 0.5, rel=1e-5)


def test_running_status(dev):
    dev.midi([0xB0, 102, 0, 103, 127, 112, 64])  # One status byte, three messages.
    assert dev.get("in1_trim_db") == -20.0
    assert dev.get("in2_trim_db") == 20.0
    assert dev.get("chorus_rate_hz") == pytest.approx((0.05 * 5.0) ** 0.5, rel=1e-5)


def test_realtime_bytes_inside_a_message(dev):
    dev.midi([0xB0, 0xF8, 102, 0xF8, 0xFA, 127, 0xF8, 103, 0xFC, 0])
    assert dev.get("in1_trim_db") == 20.0 and dev.get("in2_trim_db") == -20.0
    c = dev.counters()
    assert (c["clocks"], c["starts"], c["stops"], c["continues"]) == (3, 1, 1, 0)


def test_system_exclusive_is_skipped(dev):
    dev.midi([0xF0, 0x7E, 0xB0, 102, 0, 0x01, 0xF7])  # 0xB0 inside sysex ends it: a new message
    assert dev.get("in1_trim_db") == -20.0
    dev.midi([0xF0, 0x7E, 102, 127, 0x09, 0xF7, 102, 127])  # After F7: no running status.
    assert dev.get("in1_trim_db") == -20.0
    dev.midi([0xF0] + [0x55] * 500 + [0xF8, 0x55, 0xF7, 0xB0, 102, 127])
    assert dev.get("in1_trim_db") == 20.0
    assert dev.counters()["sysex_skipped"] == 3


def test_system_common_cancels_running_status(dev):
    dev.midi([0xB0, 102, 0, 0xF2, 0x10, 0x20, 102, 127])  # Song position, then stray data.
    assert dev.get("in1_trim_db") == -20.0


def test_channel_filter_and_omni(dev):
    dev.midi([0xB1, 102, 127])  # Channel 2: ignored on channel 1.
    assert dev.get("in1_trim_db") == 0.0
    dev.set("midi_channel", 2)
    dev.midi([0xB1, 102, 127])
    assert dev.get("in1_trim_db") == 20.0
    dev.set("midi_channel", 0)  # Omni.
    dev.midi([0xBF, 102, 0])
    assert dev.get("in1_trim_db") == -20.0


def test_channel_mode_messages_and_unmapped_ccs_are_ignored(dev):
    dev.midi([0xB0, 7, 0, 0xB0, 121, 0, 0xB0, 123, 0])  # Volume (unmapped), reset, all notes off
    assert dev.cmd("get monitor_volume_db")[0] == "ok monitor_volume_db -40"


def test_knob_wins_refuses_midi(dev):
    dev.midi([0xB0, 20, 127])
    assert dev.get("tone_bass_db") == 0.0
    pc(dev, "tone_bass_db")
    dev.midi([0xB0, 20, 127])
    assert dev.get("tone_bass_db") == 12.0


def test_tap_tempo_cc(dev):
    dev.midi([0xB0, 31, 127, 0xB0, 31, 0, 0xB0, 31, 64])  # Press, release, press.
    assert dev.counters()["taps"] == 2


def test_program_change_recalls_a_preset(dev):
    dev.set("in1_trim_db", 7.0)
    dev.save(4)
    dev.set("in1_trim_db", 0.0)
    dev.midi([0xC0, 4])
    assert dev.get("in1_trim_db") == 7.0
    dev.midi([0xC0, 9])  # Beyond the eight slots: ignored.
    assert dev.get("in1_trim_db") == 7.0


def test_cc_out_for_knobs_and_buttons_not_echoed(dev):
    dev.knob("monitor_volume_db", 1.0)
    dev.set("mute", 0.0, ctllib.SRC_BUTTON)
    assert dev.midi_out() == [0xB0, 23, 127, 0xB0, 29, 0]
    pc(dev, "fx_amount")
    dev.midi([0xB0, 25, 100])
    assert dev.midi_out() == [], "a value that came by MIDI is not sent back"
    dev.set("midi_channel", 5)
    dev.set("dim", 1.0, ctllib.SRC_BUTTON)
    assert dev.midi_out() == [0xB4, 30, 127]
    dev.set("midi_cc_out", 0.0)
    dev.set("dim", 0.0, ctllib.SRC_BUTTON)
    assert dev.midi_out() == []
