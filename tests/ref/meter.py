"""Reference models of the batch 8c meters (dsp_meter.h), in float64, written from the header's
description. The true-peak model interpolates with the taps that tools/design/tp_detector.py
designs, not with the C tables, so it checks those too."""
import importlib.util
import pathlib

import numpy as np
from scipy import signal

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _tp_design():
    spec = importlib.util.spec_from_file_location("tp_detector",
                                                  ROOT / "tools/design/tp_detector.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.design(16, 4.1)


TP_TAPS = _tp_design()  # 63 taps, 4x


def held_peak(x, hold_samples, decay_coef):
    held, left, out = 0.0, 0, np.zeros(len(x))
    for i, v in enumerate(np.abs(np.asarray(x, dtype=np.float64))):
        if v >= held:
            held, left = v, hold_samples
        elif left > 0:
            left -= 1
        else:
            held *= decay_coef
        out[i] = held
    return out


def mean_square(x, coef):
    x2 = np.asarray(x, dtype=np.float64) ** 2
    return signal.lfilter([1 - coef], [1, -coef], x2)


def true_peak_trace(x):
    """|4x interpolation| of x, one value per output position, aligned so index 4 n is x[n]."""
    up = np.zeros(4 * len(x))
    up[::4] = np.asarray(x, dtype=np.float64)
    y = np.convolve(up, TP_TAPS)
    c = len(TP_TAPS) // 2
    return np.abs(y[c:c + len(up)])


def true_peak(x):
    """The largest true peak the C meter can have seen after the whole of x: positions up to
    sample n - 8 and its three phases after (the detector looks 8 samples back), its history
    starting as 8 zeros."""
    t = true_peak_trace(np.concatenate([np.zeros(8), x]))
    return t[:4 * len(x)].max()


def kweight(x, sections):
    y = np.asarray(x, dtype=np.float64)
    for b0, b1, b2, a1, a2 in sections:
        y = signal.lfilter([b0, b1, b2], [1.0, a1, a2], y)
    return y


def block_powers(channels, sections, block_len):
    """Mean K-weighted power (summed over channels) of each complete block."""
    p = sum(kweight(x, sections) ** 2 for x in channels)
    n = len(p) // block_len
    return p[:n * block_len].reshape(n, block_len).mean(axis=1)


def lufs(power):
    return -0.691 + 10 * np.log10(power) if power > 0 else -120.0


def windowed(powers, n_blocks):
    """The mean of the newest n blocks, the history before the first block being silence."""
    padded = np.concatenate([np.zeros(n_blocks), powers])
    return padded[-n_blocks:].mean()
