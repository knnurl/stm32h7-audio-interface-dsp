"""Exercise EX3: dsp_coef_notch and dsp_coef_allpass. These fail until dsp/src/dsp_coef.c has
them. They test properties, not formulas, so they do not give the answer away.
Run: python -m pytest tests/exercises/test_ex3_notch_allpass.py
"""
import math

import numpy as np
import pytest

import dsplib
from ref import coef

FS = (48000.0, 96000.0)


def phase_deg(section, fs, f):
    b0, b1, b2, a1, a2 = section
    z = np.exp(-1j * 2 * math.pi * f / fs)
    return math.degrees(np.angle((b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z)))


@pytest.mark.parametrize("fs", FS)
@pytest.mark.parametrize("f0", [50.0, 1000.0, 12000.0])
def test_notch(lib, fs, f0):
    q = 4.0
    s = dsplib.design(lib, "notch", fs, f0, q)
    assert coef.magnitude_db([s], fs, f0) < -100.0          # A zero on the unit circle at f0.
    assert abs(coef.magnitude_db([s], fs, f0 / 20)) < 0.01  # Flat far below,
    assert abs(coef.magnitude_db([s], fs, min(f0 * 20, 0.49 * fs))) < 0.05  # and far above.
    # Bandwidth: -3 dB points about f0 / Q apart (exact for the analogue prototype).
    lo, hi = f0 * (math.sqrt(1 + 1 / (4 * q * q)) - 1 / (2 * q)), \
        f0 * (math.sqrt(1 + 1 / (4 * q * q)) + 1 / (2 * q))
    if hi < 0.2 * fs:
        assert abs(coef.magnitude_db([s], fs, lo) + 3.0103) < 0.2
        assert abs(coef.magnitude_db([s], fs, hi) + 3.0103) < 0.2


@pytest.mark.parametrize("fs", FS)
@pytest.mark.parametrize("f0", [100.0, 2000.0, 15000.0])
def test_allpass(lib, fs, f0):
    s = dsplib.design(lib, "allpass", fs, f0, 0.7)
    freqs = np.geomspace(10.0, 0.49 * fs, 50)
    assert np.max(np.abs(coef.magnitude_db([s], fs, freqs))) < 1e-9  # Unity gain everywhere.
    assert abs(abs(phase_deg(s, fs, f0)) - 180.0) < 1e-6           # -180 degrees at f0.
    assert abs(phase_deg(s, fs, 1.0)) < 1.0                         # 0 degrees at DC.


def test_both_are_stable(lib):
    for name in ("notch", "allpass"):
        b0, b1, b2, a1, a2 = dsplib.design(lib, name, 48000.0, 1000.0, 2.0)
        assert abs(a2) < 1.0 and abs(a1) < 1.0 + a2, name
