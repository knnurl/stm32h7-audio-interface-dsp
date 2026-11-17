"""dsp_delayline: integer reads are exact, fractional reads match the float64 model, the three
interpolators have the responses their maths says, and bad delays cannot reach memory."""
import ctypes

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
from ref import modulation as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def test_init_refuses_bad_memory(lib8):
    dl = b8.DspDelaylineF32()
    mem = np.zeros(3, dtype=np.float32)
    assert lib8.dsp_delayline_f32_init(ctypes.byref(dl), dsplib.f32(mem), 3) == -1
    assert lib8.dsp_delayline_f32_init(ctypes.byref(dl), None, 64) == -1


@pytest.mark.parametrize("length", [4, 5, 100, 1000])  # not only powers of two
def test_integer_delay_is_exact(lib8, length):
    x = np.random.default_rng(1).uniform(-1, 1, 3 * length).astype(np.float32)
    for d in (0, 1, length // 2, length - 2):
        line = b8.Delayline(lib8, length)
        for interp in (b8.INTERP_LINEAR, b8.INTERP_LAGRANGE):
            line = b8.Delayline(lib8, length)
            dd = max(d, 1) if interp == b8.INTERP_LAGRANGE else d
            if interp == b8.INTERP_LAGRANGE and dd > length - 3:
                continue
            y = line.process(interp, x, np.full(len(x), dd))
            assert y[dd:].tobytes() == x[:len(x) - dd].tobytes(), (interp, dd)


@pytest.mark.parametrize("interp", [0, 1, 2])
def test_fractional_reads_match_the_model(lib8, interp):
    rng = np.random.default_rng(2)
    n = 3000
    x = rng.uniform(-1, 1, n).astype(np.float32)
    d = (20 + 15 * np.sin(2 * np.pi * np.arange(n) / 700)).astype(np.float32)
    y = b8.Delayline(lib8, 64).process(interp, x, d)
    expect = ref.delay_process(x.astype(np.float64), d.astype(np.float64), interp)
    dsplib.assert_within_db(y, expect, -110.0)


def sine_gain_db(lib8, interp, f, d):
    n = 8192
    x = (0.5 * np.sin(2 * np.pi * f * np.arange(n) / FS)).astype(np.float32)
    y = b8.Delayline(lib8, 64).process(interp, x, np.full(n, d))[1000:]
    t = np.arange(1000, n) / FS
    basis = np.stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)], axis=1)
    (a, b), *_ = np.linalg.lstsq(basis, y.astype(np.float64), rcond=None)
    return 20 * np.log10(np.hypot(a, b) / 0.5)


def test_interpolator_magnitude_at_half_a_sample(lib8):
    """At a fraction of 0.5: linear is (1 + z^-1) / 2, so cos(w / 2); third-order Lagrange is
    (-1, 9, 9, -1) / 16, so (9 cos(w / 2) - cos(3 w / 2)) / 8; the all-pass is flat."""
    for f in (1000.0, 6000.0, 12000.0):
        w = 2 * np.pi * f / FS
        lin = sine_gain_db(lib8, b8.INTERP_LINEAR, f, 10.5)
        assert abs(lin - 20 * np.log10(np.cos(w / 2))) < 0.01, f
        lag = sine_gain_db(lib8, b8.INTERP_LAGRANGE, f, 10.5)
        expect = 20 * np.log10((9 * np.cos(w / 2) - np.cos(3 * w / 2)) / 8)
        assert abs(lag - expect) < 0.01 and abs(lag) < abs(lin), f
        ap = sine_gain_db(lib8, b8.INTERP_ALLPASS, f, 10.5)
        assert abs(ap) < 0.001, f
    assert abs(sine_gain_db(lib8, b8.INTERP_LINEAR, 12000.0, 10.5) + 3.01) < 0.01


def test_bad_delays_stay_in_bounds(lib8):
    line = b8.Delayline(lib8, 16)
    x = np.ones(64, dtype=np.float32)
    for d in (-5.0, 1e9, np.nan, np.inf, -np.inf):
        for interp in (0, 1, 2):
            y = line.process(interp, x, np.full(64, d, dtype=np.float32))
            assert np.all(np.isfinite(y)), (interp, d)
