"""dsp_peq_f32: flat is bit-exact, settings give the designed response, ramps are stable and
arrive exactly."""
import ctypes

import numpy as np
import pytest

import dsplib
from ref import biquad as ref_biquad
from ref import coef

FS = 48000.0
BLOCK = 16
PEAK, LOW_SHELF, HIGH_SHELF = 1, 2, 3


def make(lib, ramp_blocks=1, fs=FS):
    peq = dsplib.DspPeqF32()
    lib.dsp_peq_f32_init(ctypes.byref(peq), fs, ramp_blocks)
    return peq


def set_band(lib, peq, index, kind, freq, gain, q):
    band = dsplib.DspPeqBand(kind, freq, gain, q)
    lib.dsp_peq_f32_set_band(ctypes.byref(peq), index, ctypes.byref(band))


def run(lib, peq, x, block=BLOCK):
    y = np.zeros_like(x)
    for i in range(0, len(x), block):
        xs = x[i:i + block].copy()
        ys = np.zeros_like(xs)
        lib.dsp_peq_f32_process(ctypes.byref(peq), dsplib.f32(xs), dsplib.f32(ys), len(xs))
        y[i:i + block] = ys
    return y


def noise(n, seed=1):
    return (np.random.default_rng(seed).uniform(-1, 1, n) * 0.25).astype(np.float32)


def test_flat_is_bit_exact(lib):
    x = noise(2048)
    assert run(lib, make(lib), x).tobytes() == x.tobytes()


@pytest.mark.parametrize("fs, limit_db", [(48000.0, -110.0), (96000.0, -130.0)])
def test_settings_match_the_float64_cascade(lib, fs, limit_db):
    """At 96 kHz every section is double: only the float32 rounding of each output remains. At
    48 kHz bands 3 and 4 run in float32 (budget option D): their arithmetic noise and rounded
    coefficients stay 110 dB under the signal."""
    x = noise(16384)
    peq = make(lib, fs=fs)
    lib.dsp_peq_f32_set_highpass(ctypes.byref(peq), 25.0)
    set_band(lib, peq, 0, LOW_SHELF, 120.0, 4.0, 1.0)
    set_band(lib, peq, 1, PEAK, 400.0, -6.0, 2.0)
    set_band(lib, peq, 2, PEAK, 3000.0, 3.0, 0.7)
    set_band(lib, peq, 3, HIGH_SHELF, 9000.0, -2.0, 1.0)
    y = run(lib, peq, x)
    sections = [coef.highpass(fs, 25.0, 0.70710678118654752),
                coef.low_shelf(fs, 120.0, 1.0, 4.0), coef.peak(fs, 400.0, 2.0, -6.0),
                coef.peak(fs, 3000.0, 0.7, 3.0), coef.high_shelf(fs, 9000.0, 1.0, -2.0)]
    expected = ref_biquad.f64_cascade(x, sections)
    dsplib.assert_within_db(y, expected, limit_db)


def test_upper_bands_run_in_float32_up_to_48k_only(lib):
    assert make(lib, fs=44100.0).first_f32 == 3
    assert make(lib, fs=48000.0).first_f32 == 3
    assert make(lib, fs=96000.0).first_f32 == 5


def test_float32_band_is_raised_to_its_minimum(lib):
    """A float32 band below 2.5 kHz would be too noisy (peq_f32_noise.md): it is raised to
    2.5 kHz. At 96 kHz the same band is double and keeps its corner."""
    for fs, want_hz in ((48000.0, 2500.0), (96000.0, 500.0)):
        peq = make(lib, fs=fs)
        set_band(lib, peq, 2, PEAK, 500.0, 6.0, 2.0)
        t = peq.target[3]
        want = coef.peak(fs, want_hz, 2.0, 6.0)
        np.testing.assert_allclose([t.b0, t.b1, t.b2, t.a1, t.a2], want, rtol=1e-6, atol=1e-9)
    peq = make(lib)
    set_band(lib, peq, 1, PEAK, 500.0, 6.0, 2.0)  # Band 2 is double: not raised.
    np.testing.assert_allclose(peq.target[2].a1, coef.peak(FS, 500.0, 2.0, 6.0)[3], rtol=1e-9)


@pytest.mark.parametrize("level_db", [-1.0, -60.0])
@pytest.mark.parametrize("shelf", [(0.1, 15.0), (0.1, -15.0), (1.0, 15.0), (1.0, -15.0)])
def test_float32_bands_keep_110_db_at_the_worst_setting(lib, level_db, shelf):
    """The worst case for band 3 (a peak at the 2.5 kHz corner, Q 10, +15 dB) with band 4 as the
    registry has it, a high shelf, at the corner and its worst slopes and gains, at 48 kHz: the
    arithmetic noise against float64 running the same float32 coefficients stays 110 dB under the
    signal (113.9 dB measured). At 2 kHz this pair gave 109.6 dB, which is why the corner is
    2.5 kHz."""
    n = 48000
    x = (10 ** (level_db / 20) * np.random.default_rng(7).uniform(-1, 1, n)).astype(np.float32)
    slope, gain = shelf
    peq = make(lib)
    set_band(lib, peq, 2, PEAK, 2500.0, 15.0, 10.0)
    set_band(lib, peq, 3, HIGH_SHELF, 2500.0, gain, slope)
    y = run(lib, peq, x)
    rounded = [np.float32(coef.peak(FS, 2500.0, 10.0, 15.0)).astype(np.float64),
               np.float32(coef.high_shelf(FS, 2500.0, slope, gain)).astype(np.float64)]
    ref = ref_biquad.f64_cascade(x.astype(np.float64), rounded)
    err = y[n // 4:].astype(np.float64) - ref[n // 4:]
    snr = 10 * np.log10(np.mean(ref[n // 4:] ** 2) / np.mean(err ** 2))
    assert snr >= 110.0, snr


def stable(c):
    return abs(c.a2) < 1.0 and abs(c.a1) < 1.0 + c.a2


def test_ramp_arrives_exactly_and_stays_stable(lib):
    peq = make(lib, ramp_blocks=8)
    set_band(lib, peq, 1, PEAK, 50.0, 12.0, 8.0)
    silent = np.zeros(BLOCK, dtype=np.float32)
    seen = []
    for _ in range(8):
        assert peq.remaining > 0
        run(lib, peq, silent)
        seen.append(peq.current[2].a1)
        assert all(stable(peq.current[s]) for s in range(5))
    assert peq.remaining == 0
    target = peq.target[2]
    current = peq.current[2]
    assert (current.b0, current.b1, current.b2, current.a1, current.a2) == \
        (target.b0, target.b1, target.b2, target.a1, target.a2)
    assert len(set(seen)) == 8  # It moved every block.


def test_ramp_of_one_block_applies_at_once(lib):
    peq = make(lib, ramp_blocks=1)
    set_band(lib, peq, 0, PEAK, 1000.0, 6.0, 1.0)
    assert peq.remaining == 0 and peq.current[1].b0 == peq.target[1].b0


def test_a_change_during_a_ramp_starts_from_where_it_is(lib):
    peq = make(lib, ramp_blocks=10)
    set_band(lib, peq, 0, PEAK, 1000.0, 12.0, 1.0)
    run(lib, peq, np.zeros(5 * BLOCK, dtype=np.float32))
    midway = peq.current[1].b0
    set_band(lib, peq, 0, PEAK, 1000.0, 0.0, 1.0)
    run(lib, peq, np.zeros(BLOCK, dtype=np.float32))
    assert peq.current[1].b0 < midway  # Heading back from the midpoint, no jump to the start.
    run(lib, peq, np.zeros(9 * BLOCK, dtype=np.float32))
    assert peq.current[1].b0 == 1.0 and peq.remaining == 0


def test_band_off_and_bad_index(lib):
    peq = make(lib)
    set_band(lib, peq, 0, PEAK, 1000.0, 6.0, 1.0)
    set_band(lib, peq, 0, 0, 1000.0, 6.0, 1.0)  # Off again.
    set_band(lib, peq, 7, PEAK, 1000.0, 6.0, 1.0)  # Ignored.
    x = noise(1024)
    assert run(lib, peq, x).tobytes() == x.tobytes()


def test_in_place_and_reset(lib):
    x = noise(1024)
    peq = make(lib)
    set_band(lib, peq, 1, PEAK, 300.0, 6.0, 1.0)
    separate = run(lib, peq, x)
    lib.dsp_peq_f32_reset(ctypes.byref(peq))
    in_place = x.copy()
    lib.dsp_peq_f32_process(ctypes.byref(peq), dsplib.f32(in_place), dsplib.f32(in_place),
                            len(in_place))
    assert in_place.tobytes() == separate.tobytes()


def test_shelf_slope_above_one_stays_finite(lib):
    """The PEQ passes a band's q to the shelf as its slope; above about 5 at +12 dB the cookbook
    formula takes the square root of a negative number. The design clamps it."""
    peq = make(lib)
    set_band(lib, peq, 0, LOW_SHELF, 150.0, 12.0, 8.0)
    y = run(lib, peq, noise(2048))
    assert np.all(np.isfinite(y))
