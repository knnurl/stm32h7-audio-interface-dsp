"""Reference models for batch 9: the packed real spectrum and the partitioned convolver's output.

Double precision throughout, so the C library is judged against the exact result, not against a
second float32 implementation.
"""
import numpy as np


def rfft_packed(x):
    """numpy's real FFT in the packed layout of dsp_fft.h: X[0], X[n/2], then Re, Im of X[1..]."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    spec = np.fft.rfft(x)
    out = np.empty(n, dtype=np.float64)
    out[0] = spec[0].real
    out[1] = spec[n // 2].real
    out[2::2] = spec[1:n // 2].real
    out[3::2] = spec[1:n // 2].imag
    return out


def unpack(packed):
    """The packed layout back to n/2 + 1 complex bins."""
    p = np.asarray(packed, dtype=np.float64)
    n = len(p)
    spec = np.zeros(n // 2 + 1, dtype=np.complex128)
    spec[0] = p[0]
    spec[n // 2] = p[1]
    spec[1:n // 2] = p[2::2] + 1j * p[3::2]
    return spec


def delayed_convolution(x, h, block):
    """y[t] = sum_j h[j] x[t - block - j]: what dsp_pconv produces, same length as x."""
    x = np.asarray(x, dtype=np.float64)
    full = np.convolve(x, np.asarray(h, dtype=np.float64))[:len(x)]
    y = np.zeros(len(x))
    y[block:] = full[:len(x) - block]
    return y
