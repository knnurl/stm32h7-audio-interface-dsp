"""dsp_biquad: float32 against float64, Q31 bit-exact against the integer model, and stability."""
import ctypes

import numpy as np
import pytest

import dsplib
from ref import biquad as ref
from ref import coef

FS = 48000.0


def cascade_f32(lib, sections):
    coefs = (dsplib.DspBiquadCoefsF32 * len(sections))(
        *[dsplib.DspBiquadCoefsF32(*[float(np.float32(v)) for v in s]) for s in sections])
    filt = dsplib.DspBiquadF32()
    lib.dsp_biquad_f32_init(ctypes.byref(filt), coefs, len(sections))
    return filt


def run_f32(lib, filt, x, block=16):
    y = np.zeros_like(x)
    for i in range(0, len(x), block):
        xs = x[i:i + block].copy()
        ys = np.zeros_like(xs)
        lib.dsp_biquad_f32_process(ctypes.byref(filt), dsplib.f32(xs), dsplib.f32(ys), len(xs))
        y[i:i + block] = ys
    return y


def cascade_q31(lib, quantised, error_feedback):
    coefs = (dsplib.DspBiquadCoefsQ31 * len(quantised))(
        *[dsplib.DspBiquadCoefsQ31(*q, shift) for q, shift in quantised])
    filt = dsplib.DspBiquadQ31()
    lib.dsp_biquad_q31_init(ctypes.byref(filt), coefs, len(quantised), error_feedback)
    return filt


def run_q31(lib, filt, x, block=16):
    y = np.zeros_like(x)
    for i in range(0, len(x), block):
        xs = x[i:i + block].copy()
        ys = np.zeros_like(xs)
        lib.dsp_biquad_q31_process(ctypes.byref(filt), dsplib.i32(xs), dsplib.i32(ys), len(xs))
        y[i:i + block] = ys
    return y


EQ = [coef.highpass(FS, 30.0, 0.7071), coef.peak(FS, 1000.0, 1.0, 6.0),
      coef.high_shelf(FS, 8000.0, 1.0, -4.0)]


def noise(n, scale, seed=1):
    return (np.random.default_rng(seed).uniform(-1, 1, n) * scale).astype(np.float32)


def test_f32_cascade_against_float64(lib):
    """The float32 kernel's known weakness, held to its measured size. The 30 Hz high-pass has
    poles 0.003 from z = 1, and float32 rounding in the TDF-II state is amplified by up to
    1 / (1 + a1 + a2), about +90 dB at DC: measured -79 dBFS of error on half-scale noise
    (docs/results/b3_filter_noise.md). That is why the PEQ and the tone control use double
    state. Limit -75 dBFS."""
    x = noise(8192, 0.5)
    sections32 = [np.float32(s).astype(np.float64) for s in EQ]  # The coefficients as rounded.
    y = run_f32(lib, cascade_f32(lib, EQ), x)
    expected = ref.f64_cascade(x, sections32)
    dsplib.assert_within_db(y, expected, -75.0)


def test_f32_mid_frequency_sections_are_accurate(lib):
    """Away from z = 1 float32 is fine: a 1 kHz peak and an 8 kHz shelf within -110 dBFS."""
    x = noise(8192, 0.5)
    mid = EQ[1:]
    y = run_f32(lib, cascade_f32(lib, mid), x)
    expected = ref.f64_cascade(x, [np.float32(s).astype(np.float64) for s in mid])
    dsplib.assert_within_db(y, expected, -110.0)


def test_f64_section_is_float64_with_a_float_output(lib):
    x = noise(8192, 0.5)
    y = np.zeros_like(x)
    src = x
    for s in EQ:
        c = dsplib.DspBiquadCoefsF64(*[float(v) for v in s])
        st = dsplib.DspBiquadStateF64()
        lib.dsp_biquad_f64_section(ctypes.byref(c), ctypes.byref(st), dsplib.f32(src.copy()),
                                   dsplib.f32(y), len(x))
        src = y.copy()
    # Each section rounds its output to float32, which is all that separates it from float64.
    dsplib.assert_within_db(y, ref.f64_cascade(x, EQ), -135.0)


def test_f32_block_size_and_in_place_do_not_matter(lib):
    x = noise(1024, 0.5)
    a = run_f32(lib, cascade_f32(lib, EQ), x, block=1024)
    b = run_f32(lib, cascade_f32(lib, EQ), x, block=7)
    filt = cascade_f32(lib, EQ)
    c = x.copy()
    lib.dsp_biquad_f32_process(ctypes.byref(filt), dsplib.f32(c), dsplib.f32(c), len(c))
    assert a.tobytes() == b.tobytes() == c.tobytes()


def test_f32_identity_and_empty_cascade_pass_bit_exact(lib):
    x = noise(256, 1.0)
    assert run_f32(lib, cascade_f32(lib, [(1.0, 0.0, 0.0, 0.0, 0.0)]), x).tobytes() == x.tobytes()
    assert run_f32(lib, cascade_f32(lib, []), x).tobytes() == x.tobytes()


@pytest.mark.parametrize("error_feedback", [0, 1])
def test_q31_is_bit_exact_against_the_integer_model(lib, error_feedback):
    quantised = [coef.to_q31(s) for s in EQ]
    x = (np.random.default_rng(2).integers(-(1 << 29), 1 << 29, 3000)).astype(np.int32)
    y = run_q31(lib, cascade_q31(lib, quantised, error_feedback), x)
    assert np.array_equal(y, ref.q31_cascade(x, quantised, error_feedback))


@pytest.mark.parametrize("error_feedback", [0, 1])
def test_q31_saturates_like_the_model(lib, error_feedback):
    """Full-scale input through +12 dB: the output saturates, and the model agrees on every
    sample, including the error feedback being dropped when it does."""
    quantised = [coef.to_q31(coef.peak(FS, 500.0, 1.0, 12.0))]
    t = np.arange(2000)
    x = (np.sin(2 * np.pi * 500 * t / FS) * (2 ** 31 - 1)).astype(np.int32)
    y = run_q31(lib, cascade_q31(lib, quantised, error_feedback), x)
    assert np.max(y) == 2 ** 31 - 1 and np.min(y) == -(2 ** 31)
    assert np.array_equal(y, ref.q31_cascade(x, quantised, error_feedback))


def test_q31_extreme_coefficients_do_not_overflow(lib):
    """The worst case the quantiser allows: |coefficients| summing to the bound, with inputs at
    -2^31. Against the model, which cannot overflow, the C accumulator must agree."""
    section = coef.highpass(96000.0, 10.0, 0.7071)  # Sum of |c| close to 7.
    quantised = [coef.to_q31(section)]
    x = np.where(np.arange(4000) % 2 == 0, -(2 ** 31), 2 ** 31 - 1).astype(np.int32)
    for ef in (0, 1):
        y = run_q31(lib, cascade_q31(lib, quantised, ef), x)
        assert np.array_equal(y, ref.q31_cascade(x, quantised, ef))


def test_random_designs_are_stable(lib):
    """Random peaks and shelves at -30 dBFS: outputs stay finite and below full scale (float),
    and never saturate (Q31)."""
    rng = np.random.default_rng(5)
    x32 = noise(4096, 10 ** (-30 / 20), seed=6)
    xq = (x32.astype(np.float64) * 2 ** 31).astype(np.int32)
    for _ in range(60):
        fs = float(rng.choice([48000.0, 96000.0]))
        f0 = float(10 ** rng.uniform(np.log10(20.0), np.log10(0.45 * fs)))
        gain = float(rng.uniform(-24.0, 24.0))
        kind = rng.integers(3)
        s = (coef.peak(fs, f0, float(rng.uniform(0.1, 10.0)), gain) if kind == 0 else
             coef.low_shelf(fs, f0, 1.0, gain) if kind == 1 else
             coef.high_shelf(fs, f0, 1.0, gain))
        y = run_f32(lib, cascade_f32(lib, [s]), x32)
        assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < 1.0
        q = coef.to_q31(s)
        yq = run_q31(lib, cascade_q31(lib, [q], 1), xq)
        assert np.max(yq) < 2 ** 31 - 1 and np.min(yq) > -(2 ** 31)


def test_reset_clears_state(lib):
    x = noise(512, 0.5)
    filt = cascade_f32(lib, EQ)
    first = run_f32(lib, filt, x)
    lib.dsp_biquad_f32_reset(ctypes.byref(filt))
    assert run_f32(lib, filt, x).tobytes() == first.tobytes()
    quantised = [coef.to_q31(s) for s in EQ]
    xq = (x.astype(np.float64) * 2 ** 31).astype(np.int32)
    fq = cascade_q31(lib, quantised, 1)
    first = run_q31(lib, fq, xq)
    lib.dsp_biquad_q31_reset(ctypes.byref(fq))
    assert np.array_equal(run_q31(lib, fq, xq), first)
