"""Reference model of dsp_coef: the RBJ cookbook designs and Butterworth cascades in float64,
written from the formulas, not from the C code. Sections are (b0, b1, b2, a1, a2) with a0 = 1.
"""
import math

import numpy as np


def _norm(b0, b1, b2, a0, a1, a2):
    return np.array([b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0])


def peak(fs, f0, q, gain_db):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2.0 * q)
    c = math.cos(w0)
    return _norm(1 + alpha * a, -2 * c, 1 - alpha * a, 1 + alpha / a, -2 * c, 1 - alpha / a)


def _shelf_terms(fs, f0, slope, gain_db):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / 2.0 * math.sqrt((a + 1.0 / a) * (1.0 / slope - 1.0) + 2.0)
    return a, math.cos(w0), 2.0 * math.sqrt(a) * alpha


def low_shelf(fs, f0, slope, gain_db):
    a, c, k = _shelf_terms(fs, f0, slope, gain_db)
    return _norm(a * ((a + 1) - (a - 1) * c + k), 2 * a * ((a - 1) - (a + 1) * c),
                 a * ((a + 1) - (a - 1) * c - k), (a + 1) + (a - 1) * c + k,
                 -2 * ((a - 1) + (a + 1) * c), (a + 1) + (a - 1) * c - k)


def high_shelf(fs, f0, slope, gain_db):
    a, c, k = _shelf_terms(fs, f0, slope, gain_db)
    return _norm(a * ((a + 1) + (a - 1) * c + k), -2 * a * ((a - 1) + (a + 1) * c),
                 a * ((a + 1) + (a - 1) * c - k), (a + 1) - (a - 1) * c + k,
                 2 * ((a - 1) - (a + 1) * c), (a + 1) - (a - 1) * c - k)


def lowpass(fs, f0, q):
    w0 = 2.0 * math.pi * f0 / fs
    c, alpha = math.cos(w0), math.sin(w0) / (2.0 * q)
    return _norm((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + alpha, -2 * c, 1 - alpha)


def highpass(fs, f0, q):
    w0 = 2.0 * math.pi * f0 / fs
    c, alpha = math.cos(w0), math.sin(w0) / (2.0 * q)
    return _norm((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + alpha, -2 * c, 1 - alpha)


def magnitude_db(sections, fs, f):
    """|H| of a cascade at frequency f (scalar or array), in dB."""
    z = np.exp(-1j * 2.0 * math.pi * np.asarray(f, dtype=np.float64) / fs)
    h = np.ones_like(z)
    for b0, b1, b2, a1, a2 in sections:
        h = h * (b0 + b1 * z + b2 * z * z) / (1.0 + a1 * z + a2 * z * z)
    return 20.0 * np.log10(np.abs(h))


def _round_half_away(x):
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def to_q31(section):
    """The quantisation rule of dsp_coef_to_q31: (ints, shift) or None."""
    limit = (1 << 32) - 1
    for shift in range(8):
        scale = 2.0 ** (30 - shift)
        q = [_round_half_away(v * scale) for v in section]
        if all(-(1 << 31) <= v < (1 << 31) for v in q) and sum(abs(v) for v in q) <= limit:
            return q, shift
    return None
