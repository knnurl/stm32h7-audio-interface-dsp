"""Reference model of dsp_dcblock (exercise EX1), in float64.

y[n] = x[n] - x[n-1] + r * y[n-1],  r = 1 - 2 * pi * cutoff_hz / sample_rate_hz
"""
import math

import numpy as np


def pole(sample_rate_hz, cutoff_hz):
    return 1.0 - 2.0 * math.pi * cutoff_hz / sample_rate_hz


def process(x, r, x_prev=0.0, y_prev=0.0):
    y = np.empty(len(x), dtype=np.float64)
    for i, sample in enumerate(np.asarray(x, dtype=np.float64)):
        y_prev = sample - x_prev + r * y_prev
        x_prev = sample
        y[i] = y_prev
    return y
