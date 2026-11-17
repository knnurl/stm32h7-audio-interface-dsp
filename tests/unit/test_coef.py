"""dsp_coef: the C designs against the Python reference formulas, and the properties each design
must have, checked analytically."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
from ref import coef as ref

FS = (48000.0, 96000.0)


@pytest.mark.parametrize("fs", FS)
def test_designs_match_reference(lib, fs):
    cases = [
        ("peak", (fs, 1000.0, 0.7, 6.0), ref.peak(fs, 1000.0, 0.7, 6.0)),
        ("peak", (fs, 40.0, 10.0, -12.0), ref.peak(fs, 40.0, 10.0, -12.0)),
        ("low_shelf", (fs, 100.0, 1.0, 9.0), ref.low_shelf(fs, 100.0, 1.0, 9.0)),
        ("high_shelf", (fs, 10000.0, 1.0, -6.0), ref.high_shelf(fs, 10000.0, 1.0, -6.0)),
        ("lowpass", (fs, 5000.0, 0.7071), ref.lowpass(fs, 5000.0, 0.7071)),
        ("highpass", (fs, 20.0, 0.7071), ref.highpass(fs, 20.0, 0.7071)),
    ]
    for name, args, expected in cases:
        got = dsplib.design(lib, name, *args)
        assert np.allclose(got, expected, rtol=1e-12, atol=1e-14), name


@pytest.mark.parametrize("fs", FS)
def test_peak_has_its_gain_at_f0(lib, fs):
    for gain in (-12.0, -3.0, 3.0, 12.0):
        section = dsplib.design(lib, "peak", fs, 2000.0, 1.4, gain)
        assert abs(ref.magnitude_db([section], fs, 2000.0) - gain) < 1e-9
        # Far from f0 the peak is flat.
        assert abs(ref.magnitude_db([section], fs, 20.0)) < 0.01


@pytest.mark.parametrize("fs", FS)
def test_shelves_reach_their_gain(lib, fs):
    low = dsplib.design(lib, "low_shelf", fs, 100.0, 1.0, 9.0)
    assert abs(ref.magnitude_db([low], fs, 1e-6) - 9.0) < 1e-6
    assert abs(ref.magnitude_db([low], fs, fs / 2 - 1e-6)) < 1e-6
    assert abs(ref.magnitude_db([low], fs, 100.0) - 4.5) < 1e-9  # Half the gain at f0.
    high = dsplib.design(lib, "high_shelf", fs, 10000.0, 1.0, -6.0)
    assert abs(ref.magnitude_db([high], fs, fs / 2 - 1e-6) + 6.0) < 1e-6
    assert abs(ref.magnitude_db([high], fs, 1e-6)) < 1e-6


@pytest.mark.parametrize("fs", FS)
@pytest.mark.parametrize("order", [1, 2, 3, 4, 5, 8])
@pytest.mark.parametrize("highpass", [0, 1])
def test_butterworth(lib, fs, order, highpass):
    sections = (dsplib.DspBiquadCoefsD * 8)()
    fc = 80.0
    n = lib.dsp_coef_butterworth(sections, 8, fs, fc, order, highpass)
    assert n == (order + 1) // 2
    secs = [sections[i].as_tuple() for i in range(n)]
    assert abs(ref.magnitude_db(secs, fs, fc) + 10 * math.log10(2)) < 1e-6  # -3.01 dB at fc
    # A decade into the passband the analogue response is -10 log10(1 + 0.1^(2n)): 0.043 dB
    # for order 1, under 0.0005 dB from order 2 on.
    passband = fc * 10 if highpass else fc / 10
    expected = -10 * math.log10(1 + 0.1 ** (2 * order))
    assert abs(ref.magnitude_db(secs, fs, passband) - expected) < 0.002
    # The C magnitude function agrees with the reference one.
    got = lib.dsp_coef_magnitude_db(sections, n, fs, 1234.5)
    assert abs(got - ref.magnitude_db(secs, fs, 1234.5)) < 1e-9


def test_butterworth_rejects_bad_orders(lib):
    sections = (dsplib.DspBiquadCoefsD * 8)()
    assert lib.dsp_coef_butterworth(sections, 8, 48000.0, 100.0, 0, 1) == 0
    assert lib.dsp_coef_butterworth(sections, 8, 48000.0, 100.0, 9, 1) == 0
    assert lib.dsp_coef_butterworth(sections, 1, 48000.0, 100.0, 4, 1) == 0


def test_q31_quantisation_matches_the_rule(lib):
    rng = np.random.default_rng(11)
    for _ in range(200):
        kind = rng.integers(3)
        fs = float(rng.choice(FS))
        f0 = float(10 ** rng.uniform(np.log10(15.0), np.log10(0.45 * fs)))
        gain = float(rng.uniform(-18.0, 18.0))
        section = (ref.peak(fs, f0, float(rng.uniform(0.2, 12.0)), gain) if kind == 0 else
                   ref.low_shelf(fs, f0, 1.0, gain) if kind == 1 else
                   ref.highpass(fs, f0, 0.7071))
        q = dsplib.DspBiquadCoefsQ31()
        err = ctypes.c_double()
        shift = lib.dsp_coef_to_q31(ctypes.byref(dsplib.coefs_d(section)), ctypes.byref(q),
                                    ctypes.byref(err))
        expected = ref.to_q31(section)
        assert expected is not None and shift == expected[1]
        assert [q.b0, q.b1, q.b2, q.a1, q.a2] == expected[0]
        assert err.value <= 2.0 ** -(31 - shift) + 1e-18


def test_q31_quantisation_refuses_what_cannot_fit(lib):
    q = dsplib.DspBiquadCoefsQ31()
    big = dsplib.coefs_d((300.0, 0.0, 0.0, 0.0, 0.0))
    assert lib.dsp_coef_to_q31(ctypes.byref(big), ctypes.byref(q), None) == -1


def test_to_f32_rounds_each_coefficient(lib):
    section = ref.peak(48000.0, 1000.0, 0.7, 6.0)
    out = dsplib.DspBiquadCoefsF32()
    lib.dsp_coef_to_f32(ctypes.byref(dsplib.coefs_d(section)), ctypes.byref(out))
    got = np.array([out.b0, out.b1, out.b2, out.a1, out.a2], dtype=np.float32)
    assert np.array_equal(got, np.float32(section))
