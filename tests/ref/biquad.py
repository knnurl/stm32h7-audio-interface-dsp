"""Reference models of dsp_biquad.

Float: the cascade in float64 (scipy's sosfilt), the ideal the float32 code is compared to.

Q31: an integer model with the C code's exact rules, so the comparison is bit-exact:
  acc = b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2       (Python integers: no overflow)
  k = 30 - shift
  without error feedback: y = floor((acc + 2^(k-1)) / 2^k)        round half up
  with error feedback:    acc += err;  y = floor(acc / 2^k);  err = acc - y*2^k
                          (err = 0 when y saturates)
  y is saturated to [-2^31, 2^31 - 1] and that saturated value is what the state keeps.
Sections run one after another over the whole block.
"""
import numpy as np
from scipy import signal

INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1


def f64_cascade(x, sections):
    sos = np.array([[b0, b1, b2, 1.0, a1, a2] for b0, b1, b2, a1, a2 in sections])
    return signal.sosfilt(sos, np.asarray(x, dtype=np.float64))


def q31_section(x, q, shift, error_feedback, state=None):
    b0, b1, b2, a1, a2 = q
    k = 30 - shift
    x1, x2, y1, y2, err = state if state else (0, 0, 0, 0, 0)
    out = np.empty(len(x), dtype=np.int32)
    for i, xi in enumerate(int(v) for v in x):
        acc = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        if error_feedback:
            acc += err
            y = acc >> k
            err = acc - (y << k)
            if y > INT32_MAX or y < INT32_MIN:
                err = 0
        else:
            y = (acc + (1 << (k - 1))) >> k
        y = max(INT32_MIN, min(INT32_MAX, y))
        x2, x1, y2, y1 = x1, xi, y1, y
        out[i] = y
    return out, (x1, x2, y1, y2, err)


def q31_cascade(x, quantised, error_feedback):
    """`quantised` is a list of (ints, shift)."""
    y = np.asarray(x, dtype=np.int32)
    for q, shift in quantised:
        y, _ = q31_section(y, q, shift, error_feedback)
    return y
