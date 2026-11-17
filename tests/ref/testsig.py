"""Reference model of dsp_testsig's noise source, in Python integers: exact by construction.

state' = (state * 1664525 + 1013904223) mod 2^32. The Q31 sample is the state read as a signed
32-bit integer. The float sample is that integer converted to float32 (round to nearest, ties to
even) and multiplied by amplitude / 2^31 in float32.
"""
import numpy as np


def noise_q31(seed, n):
    out = np.empty(n, dtype=np.int32)
    state = seed & 0xFFFFFFFF
    for i in range(n):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        out[i] = state - (1 << 32) if state & 0x80000000 else state
    return out


def noise_f32(seed, n, amplitude):
    scale = np.float32(amplitude) * np.float32(1.0 / 2147483648.0)
    return noise_q31(seed, n).astype(np.float32) * scale
