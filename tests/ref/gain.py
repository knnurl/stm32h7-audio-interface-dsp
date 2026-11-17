"""Reference model of dsp_gain: a gain whose linear value follows its target through a one-pole
low-pass. Computed in float64, so it is the ideal the float32 C code is compared against."""
import math

import numpy as np


def coef(sample_rate_hz, smoothing_ms):
    if smoothing_ms <= 0.0 or sample_rate_hz <= 0.0:
        return 1.0
    return 1.0 - math.exp(-1.0 / (smoothing_ms * 0.001 * sample_rate_hz))


def db_to_linear(gain_db):
    return 10.0 ** (gain_db / 20.0)


def process(x, gain, target, k):
    """Returns (y, gain at the end)."""
    y = np.empty(len(x), dtype=np.float64)
    for i, sample in enumerate(np.asarray(x, dtype=np.float64)):
        gain += k * (target - gain)
        y[i] = sample * gain
    return y, gain
