"""Exercise EX8c: the BS.1770 K-weighting filter (dsp/include/dsp/dsp_kweight.h). These fail
until the owner replaces the stub in dsp/src/dsp_kweight.c.
Run: python -m pytest tests/exercises/test_ex8c_kweight.py
"""

import numpy as np
import pytest
from scipy import signal

import dsplib
import dsplib_b8c as b8c

RATES = [32000.0, 44100.0, 48000.0, 88200.0, 96000.0, 192000.0]


@pytest.fixture(scope="module")
def lib8c(lib):
    return b8c.bind(lib)


def design(lib8c, fs):
    d = (dsplib.DspBiquadCoefsF64 * 2)()
    result = lib8c.dsp_kweight_design(fs, d)
    return result, [(s.b0, s.b1, s.b2, s.a1, s.a2) for s in d]


def response_db(sections, fs, f):
    h = np.ones(len(f), dtype=complex)
    for b0, b1, b2, a1, a2 in sections:
        h *= signal.freqz([b0, b1, b2], [1.0, a1, a2], worN=f, fs=fs)[1]
    return 20 * np.log10(np.abs(h))


def test_48k_is_the_published_filter(lib8c):
    result, sections = design(lib8c, 48000.0)
    assert result == 0, "dsp_kweight_design still returns -1: the stub is in place"
    np.testing.assert_allclose(sections, b8c.KWEIGHT_48K, rtol=0, atol=1e-8)


@pytest.mark.parametrize("fs", [r for r in RATES if r != 48000.0])
def test_other_rates_match_the_48k_response(lib8c, fs):
    """Within 0.05 dB of the published filter from 20 Hz to 20 kHz (below 0.45 fs). Reusing the
    48 kHz coefficients misses this by 1 to 22 dB; a careful re-derivation stays under 0.04."""
    result, sections = design(lib8c, fs)
    assert result == 0
    f = np.geomspace(20, 20000, 200)
    f = f[f < 0.45 * fs]
    diff = response_db(sections, fs, f) - response_db(b8c.KWEIGHT_48K, 48000.0, f)
    assert np.max(np.abs(diff)) < 0.05


@pytest.mark.parametrize("fs", [16000.0, 22050.0, 384000.0])
def test_rates_outside_the_range_are_refused(lib8c, fs):
    d = (dsplib.DspBiquadCoefsF64 * 2)()
    for s in d:
        s.b0, s.b1, s.b2, s.a1, s.a2 = 7.0, 7.0, 7.0, 7.0, 7.0
    assert lib8c.dsp_kweight_design(fs, d) == -1
    assert all((s.b0, s.b1, s.b2, s.a1, s.a2) == (7.0,) * 5 for s in d), "sections untouched"


@pytest.mark.parametrize("fs", [44100.0, 48000.0, 96000.0])
def test_ebu_3341_case_1_through_the_meter(lib8c, fs):
    """EBU Tech 3341 case 1: a 1 kHz sine at -23 dBFS in both channels reads -23.0 LUFS within
    0.1 LU, with the meter using your design (no coefficients injected)."""
    n = int(4 * fs)
    x = (10 ** (-23 / 20) * np.sin(2 * np.pi * 1000 * np.arange(n) / fs)).astype(np.float32)
    m = b8c.Meter(lib8c, fs, flags=b8c.METER_LOUDNESS)
    m.process(x, x)
    r = m.read()
    assert r.kweighted == 1
    assert r.momentary_lufs == pytest.approx(-23.0, abs=0.1)
    assert r.short_term_lufs == pytest.approx(-23.0, abs=0.1)
