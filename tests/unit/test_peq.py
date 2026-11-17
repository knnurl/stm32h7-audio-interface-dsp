"""dsp_peq_f32: flat is bit-exact, settings give the designed response, ramps are stable and
arrive exactly."""
import ctypes

import numpy as np

import dsplib
from ref import biquad as ref_biquad
from ref import coef

FS = 48000.0
BLOCK = 16
PEAK, LOW_SHELF, HIGH_SHELF = 1, 2, 3


def make(lib, ramp_blocks=1):
    peq = dsplib.DspPeqF32()
    lib.dsp_peq_f32_init(ctypes.byref(peq), FS, ramp_blocks)
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


def test_settings_match_the_float64_cascade(lib):
    x = noise(16384)
    peq = make(lib)
    lib.dsp_peq_f32_set_highpass(ctypes.byref(peq), 25.0)
    set_band(lib, peq, 0, LOW_SHELF, 120.0, 4.0, 1.0)
    set_band(lib, peq, 1, PEAK, 400.0, -6.0, 2.0)
    set_band(lib, peq, 2, PEAK, 3000.0, 3.0, 0.7)
    set_band(lib, peq, 3, HIGH_SHELF, 9000.0, -2.0, 1.0)
    y = run(lib, peq, x)
    sections = [coef.highpass(FS, 25.0, 0.70710678118654752),
                coef.low_shelf(FS, 120.0, 1.0, 4.0), coef.peak(FS, 400.0, 2.0, -6.0),
                coef.peak(FS, 3000.0, 0.7, 3.0), coef.high_shelf(FS, 9000.0, 1.0, -2.0)]
    expected = ref_biquad.f64_cascade(x, sections)
    # Double state: only the float32 rounding of each section's output remains.
    dsplib.assert_within_db(y, expected, -130.0)


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
