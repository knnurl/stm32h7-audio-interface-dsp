"""Reference models of the batch 8b building blocks, in float64: fractional delay reads, the LFO
shapes, and the topology-preserving state-variable filter. Same equations as the C code, exact
sin and tan."""
import math

import numpy as np


# ---- Delay line ------------------------------------------------------------------------------

def read_linear(hist, d):
    """`hist[k]` is the sample k steps ago (hist[0] the newest)."""
    i = int(math.floor(d))
    f = d - i
    return hist[i] + f * (hist[i + 1] - hist[i])


def read_lagrange(hist, d):
    i = int(math.floor(d))
    f = d - i
    xm1, x0, x1, x2 = hist[i - 1], hist[i], hist[i + 1], hist[i + 2]
    return (-f * (f - 1) * (f - 2) / 6 * xm1 + (f + 1) * (f - 1) * (f - 2) / 2 * x0
            - (f + 1) * f * (f - 2) / 2 * x1 + (f + 1) * f * (f - 1) / 6 * x2)


def delay_process(x, delays, interp):
    """Push each sample, then read at delays[n]; interp 0 linear, 1 Lagrange, 2 all-pass."""
    x = np.asarray(x, dtype=np.float64)
    pad = int(max(delays)) + 4
    buf = np.concatenate([np.zeros(pad), x])
    y = np.empty(len(x))
    y1 = 0.0
    for n in range(len(x)):
        hist = buf[pad + n::-1]  # hist[k] = x[n - k]
        d = float(delays[n])
        if interp == 0:
            y[n] = read_linear(hist, d)
        elif interp == 1:
            y[n] = read_lagrange(hist, d)
        else:
            i = int(math.floor(d))
            f = d - i
            if f < 0.5 and i > 0:
                i, f = i - 1, f + 1
            eta = (1 - f) / (1 + f)
            y1 = eta * (hist[i] - y1) + hist[i + 1]
            y[n] = y1
    return y


# ---- LFO --------------------------------------------------------------------------------------

def lfo_value(shape, phase, edge=0.05):
    """`phase` in cycles; 0 is the rising zero crossing. Shapes as dsp_lfo.h."""
    x = phase - math.floor(phase + 0.5)  # [-0.5, 0.5)
    folded = 0.5 - x if x > 0.25 else (-0.5 - x if x < -0.25 else x)
    if shape == 0:
        return math.sin(2 * math.pi * x)
    if shape == 1:
        return 4 * folded
    if shape == 2:
        y = max(-0.25, min(0.25, folded * 0.5 / edge))
        return math.sin(2 * math.pi * y)
    return 2 * x


_C = [np.float32(v) for v in (6.283161163330078, -41.336708068847656, 81.32439422607422,
                              -70.82131958007812)]


def lfo_value_f32(shape, phase_u32):
    """The C LFO's value, step for step in float32 (dsp_lfo.c), for models whose modulation
    depth would magnify the polynomial's 8e-7 error (a 336-sample chorus depth: -71 dB)."""
    p = int(phase_u32) % 2 ** 32
    x = np.float32(p - 2 ** 32 if p >= 2 ** 31 else p) / np.float32(4294967296.0)
    if x > np.float32(0.25):
        x = np.float32(0.5) - x
    elif x < np.float32(-0.25):
        x = np.float32(-0.5) - x
    if shape == 1:
        return np.float32(4.0) * x
    x2 = x * x
    return x * (_C[0] + x2 * (_C[1] + x2 * (_C[2] + x2 * _C[3])))


# ---- State-variable filter --------------------------------------------------------------------

def svf_coefs(fs, fc, q):
    g = math.tan(math.pi * min(max(fc, 1.0), 0.45 * fs) / fs)
    k = 1 / min(max(q, 0.1), 50.0)
    a1 = 1 / (1 + g * (g + k))
    return g, k, a1, g * a1, g * g * a1


def svf(x, fs, fc, q, mode):
    g, k, a1, a2, a3 = svf_coefs(fs, fc, q)
    ic1 = ic2 = 0.0
    y = np.empty(len(x))
    for n, v0 in enumerate(np.asarray(x, dtype=np.float64)):
        v3 = v0 - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1, ic2 = 2 * v1 - ic1, 2 * v2 - ic2
        y[n] = (v2, v1, v0 - k * v1 - v2, v0 - k * v1)[mode]
    return y
