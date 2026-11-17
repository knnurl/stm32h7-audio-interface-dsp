"""Reference model of dsp_comp in float64 with exact log and exp (the C block uses dsp_fastmath,
1e-4 dB). Same structure: instantaneous level, static curve, branching one-pole on the gain
reduction in dB, makeup."""
import math

import numpy as np


def coef(fs, time_ms):
    return 0.0 if time_ms <= 0 else math.exp(-1.0 / (time_ms * 0.001 * fs))


def static_curve(x_db, threshold, ratio, knee):
    over = x_db - threshold
    slope = 1.0 / ratio - 1.0
    if 2 * over < -knee:
        return x_db
    if knee > 0 and 2 * over <= knee:
        k = over + knee / 2
        return x_db + slope * k * k / (2 * knee)
    return threshold + over / ratio


def compressor(x, fs, threshold, ratio, knee, attack_ms, release_ms, makeup_db):
    a, r = coef(fs, attack_ms), coef(fs, release_ms)
    y_l = 0.0
    out = np.empty(len(x))
    floor = 20 * math.log10(1e-30)
    for i, xi in enumerate(np.asarray(x, dtype=np.float64)):
        x_db = max(20 * math.log10(abs(xi)) if xi != 0 else floor, floor)
        x_l = x_db - static_curve(x_db, threshold, ratio, knee)
        c = a if x_l > y_l else r
        y_l = x_l + c * (y_l - x_l)
        out[i] = xi * 10 ** ((makeup_db - y_l) / 20)
    return out
