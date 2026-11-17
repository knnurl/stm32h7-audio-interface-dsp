"""Exercise EX1: dsp_dcblock_f32. These fail until dsp/src/dsp_dcblock.c is written.
Run: python -m pytest tests/exercises/test_ex1_dcblock.py
"""
import ctypes

import numpy as np

import dsplib
from ref import dcblock as ref

FS = 48000.0
CUTOFF_HZ = 10.0
LIMIT_DB = -110.0


def make(lib):
    state = dsplib.DspDcblockF32()
    lib.dsp_dcblock_f32_init(ctypes.byref(state), FS, CUTOFF_HZ)
    return state


def run(lib, state, x):
    y = np.zeros_like(x)
    lib.dsp_dcblock_f32_process(ctypes.byref(state), dsplib.f32(x), dsplib.f32(y), len(x))
    return y


def test_pole_radius(lib):
    assert abs(make(lib).r - ref.pole(FS, CUTOFF_HZ)) < 1e-6


def test_matches_reference_on_noise(lib):
    x = np.random.default_rng(3).uniform(-0.5, 0.5, 8192).astype(np.float32)
    y = run(lib, make(lib), x)
    dsplib.assert_within_db(y, ref.process(x, ref.pole(FS, CUTOFF_HZ)), LIMIT_DB)


def test_removes_dc(lib):
    """A constant 0.5 decays to below -60 dBFS within one second."""
    x = np.full(int(FS), 0.5, dtype=np.float32)
    y = run(lib, make(lib), x)
    assert abs(float(y[-1])) < 1e-3
    assert abs(float(y[0]) - 0.5) < 1e-6  # The step itself passes.


def test_passes_1_khz(lib):
    """At 1 kHz, a hundred times the cutoff, the gain is within 0.01 dB of unity."""
    n = int(FS)
    x = (0.5 * np.sin(2.0 * np.pi * 1000.0 * np.arange(n) / FS)).astype(np.float32)
    y = run(lib, make(lib), x)
    gain_db = 20.0 * np.log10(np.std(y[n // 2:]) / np.std(x[n // 2:]))
    assert abs(gain_db) < 0.01


def test_reset_clears_the_state(lib):
    state = make(lib)
    run(lib, state, np.full(1000, 0.5, dtype=np.float32))
    lib.dsp_dcblock_f32_reset(ctypes.byref(state))
    assert state.x_prev == 0.0 and state.y_prev == 0.0
    assert abs(state.r - ref.pole(FS, CUTOFF_HZ)) < 1e-6


def test_in_place_and_block_size(lib):
    x = np.random.default_rng(4).uniform(-0.5, 0.5, 1024).astype(np.float32)
    whole = run(lib, make(lib), x)
    state = make(lib)
    in_place = x.copy()
    for start in range(0, 1024, 16):
        piece = in_place[start:start + 16]
        lib.dsp_dcblock_f32_process(ctypes.byref(state), dsplib.f32(piece), dsplib.f32(piece), 16)
    assert np.array_equal(in_place, whole)
