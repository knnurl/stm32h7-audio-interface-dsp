"""Exercise EX8b: the tremolo (dsp/include/dsp/dsp_fx_tremolo.h). These fail until the owner
replaces the pass-through stub in dsp/src/dsp_fx_tremolo.c.
Run: python -m pytest tests/exercises/test_ex8b_tremolo.py
With a DC input of 0.5 the output is half the gain, so most tests read the gain directly."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
from ref import fx as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def make(lib8, depth=0.7, rate=5.0, shape=0, edge=0.05, stereo=0.0):
    fx = b8.DspFxTremoloF32()
    lib8.dsp_fx_tremolo_f32_init(ctypes.byref(fx), FS)
    lib8.dsp_fx_tremolo_f32_set_rate(ctypes.byref(fx), rate)
    lib8.dsp_fx_tremolo_f32_set_shape(ctypes.byref(fx), shape, edge)
    lib8.dsp_fx_tremolo_f32_set_stereo_phase(ctypes.byref(fx), stereo)
    lib8.dsp_fx_tremolo_f32_set_amount(ctypes.byref(fx), depth)
    # Skip the 10 ms depth ramp from the default (0.5): settle at the new depth.
    fx.depth.cur = fx.depth.target = depth
    fx.depth.left = 0
    return fx


def gains(lib8, fx, n):
    x = np.full(n, 0.5, dtype=np.float32)
    yl, yr = b8.run_stereo(lib8.dsp_fx_tremolo_f32_process, fx, x, x)
    return 2 * yl.astype(np.float64), 2 * yr.astype(np.float64)


@pytest.mark.parametrize("shape", [0, 1, 2])
def test_matches_the_reference(lib8, shape):
    fx = make(lib8, 0.7, 5.0, shape, 0.05, 0.25)
    x = np.random.default_rng(1).uniform(-1, 1, 24000).astype(np.float32)
    yl, yr = b8.run_stereo(lib8.dsp_fx_tremolo_f32_process, fx, x, x)
    el, er = ref.tremolo(x, x, FS, 0.7, round(5.0 / FS * 2 ** 32) / 2 ** 32 * FS, shape, 0.05,
                         0.25)
    dsplib.assert_within_db(yl, el, -100.0)
    dsplib.assert_within_db(yr, er, -100.0)


def test_depth_sets_the_range(lib8):
    gl, _ = gains(lib8, make(lib8, 0.6), 48000)
    assert gl.max() == pytest.approx(1.0, abs=1e-5) and gl.min() == pytest.approx(0.4, abs=1e-5)
    gl, _ = gains(lib8, make(lib8, 0.0), 4800)
    assert np.all(gl == 1.0)


def test_auto_pan(lib8):
    """Stereo phase 0.5 with the sine: the two gains always add to 2 - depth."""
    gl, gr = gains(lib8, make(lib8, 0.8, 3.0, stereo=0.5), 48000)
    assert np.max(np.abs(gl + gr - 1.2)) < 1e-5
    assert np.corrcoef(gl, gr)[0, 1] < -0.99


def test_tempo_sync_puts_the_loudest_point_on_the_beat(lib8):
    """120 bpm, a cycle per beat (24000 samples), synced at beat 0: gain 1 on every beat,
    1 - depth halfway between."""
    fx = make(lib8, 0.7)
    lib8.dsp_fx_tremolo_f32_sync(ctypes.byref(fx), 0.0, 1.0, 120.0)
    gl, _ = gains(lib8, fx, 96001)
    for beat in range(4):
        assert gl[beat * 24000] == pytest.approx(1.0, abs=1e-5), beat
        assert gl[beat * 24000 + 12000] == pytest.approx(0.3, abs=1e-5), beat
    # Synced mid-way: beat 2.5 with a cycle per bar (4 beats) is 0.625 of a cycle past the peak.
    fx = make(lib8, 0.7)
    lib8.dsp_fx_tremolo_f32_sync(ctypes.byref(fx), 2.5, 4.0, 120.0)
    gl, _ = gains(lib8, fx, 16)
    expect = ref.tremolo_gain(0.25 + 2.5 / 4.0, 0.7)
    assert gl[0] == pytest.approx(expect, abs=1e-5)


def test_rounded_square_has_no_steps(lib8):
    """The square's edges are rounded: the gain never moves faster than depth pi / (2 edge P)
    per sample (P the period), and it sits at 1 or 1 - depth outside the edges."""
    depth, rate, edge = 1.0, 8.0, 0.02
    gl, _ = gains(lib8, make(lib8, depth, rate, 2, edge), 48000)
    period = FS / rate
    limit = depth * math.pi / (2 * edge * period)
    assert np.max(np.abs(np.diff(gl))) <= 1.02 * limit
    flat = np.mean((np.abs(gl - 1) < 1e-6) | (np.abs(gl - (1 - depth)) < 1e-6))
    assert flat == pytest.approx(1 - 2 * edge, abs=0.01)


def test_depth_changes_are_ramped(lib8):
    fx = make(lib8, 0.0, 0.0001)
    x = np.full(9600, 0.5, dtype=np.float32)
    lib8.dsp_fx_tremolo_f32_set_rate(ctypes.byref(fx), 0.0)
    lib8.dsp_fx_tremolo_f32_set_shape(ctypes.byref(fx), 2, 0.05)  # square: phase 0 is mid-edge
    lib8.dsp_lfo_f32_set_phase(ctypes.byref(fx.lfo), 0.75)  # the quiet half
    lib8.dsp_fx_tremolo_f32_set_amount(ctypes.byref(fx), 1.0)
    yl, _ = b8.run_stereo(lib8.dsp_fx_tremolo_f32_process, fx, x, x)
    g = 2 * yl.astype(np.float64)
    assert g[-1] == pytest.approx(0.0, abs=1e-6)
    assert np.max(np.abs(np.diff(g))) <= 1.0 / 480 + 1e-6  # 10 ms at 48 kHz
