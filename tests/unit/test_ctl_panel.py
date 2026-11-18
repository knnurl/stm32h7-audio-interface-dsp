"""ctl_panel on a whole control stack: pots into the registry through knob ownership, the button
mapping (owner, 2026-11-18; no footswitch), the budget rule from the panel, and the LEDs
(docs/notes/panel_input.md)."""
import ctypes

import numpy as np
import pytest

import ctllib
from ctllib import (BTN_DIM, BTN_FX_ON, BTN_FX_SELECT, BTN_MUTE, BTN_TAP,
                    LED_CLIP1, LED_CLIP2, LED_DIM, LED_FX_ON, LED_MUTE, LED_SIGNAL1, LED_SIGNAL2,
                    SRC_DEVICE)


@pytest.fixture
def panel(dev):
    p = ctllib.Panel(dev)
    p.tick(100)
    return p


def drain(dev):
    n = 0
    idx = ctypes.c_uint16()
    while dev.lib.ctl_core_take_notify(dev.core, ctypes.byref(idx)):
        n += 1
    return n


# ---- Pots -----------------------------------------------------------------------------------

def test_first_tick_sets_every_knob(panel, dev):
    assert dev.get("tone_bass_db") == 0.0
    assert dev.get("tone_treble_db") == 0.0
    assert dev.get("monitor_volume_db") == -80.0
    assert dev.get("fx_amount") == pytest.approx(0.5)
    assert dev.get("blend") == pytest.approx(0.5)


def test_a_turn_reaches_the_registry(panel, dev):
    for t in np.linspace(0.0, 1.0, 300):
        panel.travel[3] = t
        panel.tick(2)
    panel.tick(100)
    assert dev.get("monitor_volume_db") == 0.0
    panel.travel[0] = 1.0
    panel.tick(100)
    assert dev.get("tone_bass_db") == 12.0


def test_still_panel_sends_nothing(panel, dev):
    """Ten seconds of a still panel with reading noise: no change reaches the core."""
    rng = np.random.default_rng(1)
    base = list(panel.travel)
    drain(dev)
    for _ in range(10_000):
        panel.travel = list(np.clip(np.array(base) + rng.normal(0, 4 * 60 / (16 * 65535), 7), 0, 1))
        panel.tick()
    assert drain(dev) == 0


def test_pc_wins_knob_is_picked_up_not_jumped(panel, dev):
    dev.set("mode_monitor_volume", 1.0)
    dev.set("monitor_volume_db", -20.0)
    panel.travel[3] = 0.2
    panel.tick(100)
    assert dev.get("monitor_volume_db") == -20.0


# ---- Buttons --------------------------------------------------------------------------------

def test_fx_select_short_next_long_previous_and_wraps(panel, dev):
    assert dev.get("fx_select") == 0
    panel.press(BTN_FX_SELECT)
    assert dev.get("fx_select") == 1
    panel.press(BTN_FX_SELECT, hold_ms=700)
    assert dev.get("fx_select") == 0
    panel.press(BTN_FX_SELECT, hold_ms=700)
    assert dev.get("fx_select") == 7
    panel.press(BTN_FX_SELECT)
    assert dev.get("fx_select") == 0


def test_fx_select_skips_what_the_budget_refuses(panel, dev):
    dev.set("in1_sat_on", 1.0)
    dev.set("fx_on", 1.0)
    dev.set("fx_select", 5.0)
    panel.press(BTN_FX_SELECT)
    assert dev.get("fx_select") == 7
    panel.press(BTN_FX_SELECT, hold_ms=700)
    assert dev.get("fx_select") == 5


def test_fx_on_toggles_and_a_budget_refusal_is_counted(panel, dev):
    panel.press(BTN_FX_ON)
    assert dev.get("fx_on") == 1.0
    panel.press(BTN_FX_ON)
    assert dev.get("fx_on") == 0.0
    dev.set("fx_select", 6.0)
    dev.set("in2_sat_on", 1.0)
    panel.press(BTN_FX_ON)
    assert dev.get("fx_on") == 0.0
    assert dev.lib.ctl_panel_refused(panel.p) == 1


def test_mute_and_dim_toggle(panel, dev):
    assert dev.get("mute") == 1.0  # The outputs start muted.
    panel.press(BTN_MUTE)
    assert dev.get("mute") == 0.0
    panel.press(BTN_DIM)
    assert dev.get("dim") == 1.0
    panel.press(BTN_DIM)
    assert dev.get("dim") == 0.0


def test_buttons_write_as_the_button_source(panel, dev):
    """So their changes go to MIDI out and the PC, like the knobs'."""
    dev.midi_out()
    panel.press(BTN_DIM)
    assert dev.midi_out() != []


def test_tap_sets_the_tempo_and_a_long_press_undoes_it(panel, dev):
    assert dev.get("tempo_bpm") == 120.0 and dev.get("tempo_source") == 0
    for _ in range(4):
        panel.press(BTN_TAP, hold_ms=40, gap_ms=360, update_tempo=True)  # 400 ms: 150 BPM.
    assert dev.get("tempo_source") == 2
    assert dev.get("tempo_bpm") == pytest.approx(150.0, abs=0.01)
    assert dev.get("tempo_now_bpm") == pytest.approx(150.0, abs=0.01)
    panel.press(BTN_TAP, hold_ms=700, gap_ms=2500, update_tempo=True)
    assert dev.get("tempo_source") == 0
    assert dev.get("tempo_bpm") == 120.0


def test_tap_leaves_a_midi_only_source_alone(panel, dev):
    dev.set("tempo_source", 1.0)
    for _ in range(3):
        panel.press(BTN_TAP, hold_ms=40, gap_ms=460, update_tempo=True)
    assert dev.get("tempo_source") == 1
    panel.press(BTN_TAP, hold_ms=700, update_tempo=True)
    assert dev.get("tempo_source") == 1


def test_bouncing_button_toggles_once(panel, dev):
    rng = np.random.default_rng(5)
    for t in range(12):
        panel.closed = int(rng.integers(0, 2)) << BTN_FX_ON
        panel.tick()
    panel.closed = 1 << BTN_FX_ON
    panel.tick(100)
    panel.closed = 0
    panel.tick(50)
    assert dev.get("fx_on") == 1.0


# ---- LEDs -----------------------------------------------------------------------------------

def hold(ctl, h, level, thr, hold_ms, now):
    return ctl.ctl_led_hold(ctypes.cast(h, ctypes.c_void_p), level, thr, hold_ms, now)


def test_led_hold(ctl):
    h = ctypes.create_string_buffer(8)
    assert hold(ctl, h, -39.0, -40.0, 100, 1000) == 1
    assert hold(ctl, h, -60.0, -40.0, 100, 1099) == 1
    assert hold(ctl, h, -60.0, -40.0, 100, 1100) == 0
    assert hold(ctl, h, -40.0, -40.0, 100, 1200) == 1  # At the threshold counts.


def test_led_hold_across_the_counter_wrap(ctl):
    h = ctypes.create_string_buffer(8)
    assert hold(ctl, h, 0.0, -0.5, 300, 0xFFFFFF00) == 1
    assert hold(ctl, h, -90.0, -0.5, 300, 0x10) == 1  # 272 ms later.
    assert hold(ctl, h, -90.0, -0.5, 300, 0x2C) == 0  # 300 ms later.


def test_panel_leds_from_the_meters(panel, dev):
    dev.set("in1_peak_db", -30.0, SRC_DEVICE)
    dev.set("in2_peak_db", -0.2, SRC_DEVICE)
    leds = panel.leds(5000)
    assert leds & LED_SIGNAL1 and not leds & LED_CLIP1
    assert leds & LED_SIGNAL2 and leds & LED_CLIP2
    assert leds & LED_MUTE and not leds & LED_DIM and not leds & LED_FX_ON
    dev.set("in1_peak_db", -120.0, SRC_DEVICE)
    dev.set("in2_peak_db", -120.0, SRC_DEVICE)
    leds = panel.leds(5150)
    assert not leds & LED_SIGNAL1 and leds & LED_CLIP2
    leds = panel.leds(5300)
    assert not leds & (LED_SIGNAL2 | LED_CLIP2)
