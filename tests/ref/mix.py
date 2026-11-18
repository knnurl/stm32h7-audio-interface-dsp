"""Reference models of the batch 8c mixer and crossfeed, in float64, written from the headers'
equations (dsp_mixer.h, dsp_crossfeed.h). Ramps are the linear ramps of dsp_fx_common.h."""
import math

import numpy as np

from ref.fx import onepole_coef


def pan_gains(pan):
    p = min(max(pan, -1.0), 1.0)
    t = (p + 1.0) * math.pi / 4.0
    return math.cos(t), math.sin(t)


def channel_gains(level, pan, send, mute):
    left, right = pan_gains(pan)
    level, send = (0.0, 0.0) if mute else (level, send)
    return np.array([level * left, level * right, send * left, send * right])


def ramp(start, target, n_ramp, n):
    """The gains of a linear ramp from `start` to `target` over n_ramp samples, for n samples."""
    if n_ramp <= 0:
        return np.full(n, target)
    k = np.arange(1, n + 1)
    return np.where(k < n_ramp, start + (target - start) * k / n_ramp, target)


def mixer(inputs, settings, ramp_samples, changes=()):
    """inputs: arrays per channel (None for silence); settings: (level, pan, send, mute) per
    channel, settled at the start; changes: (sample, channel, (level, pan, send, mute)).
    Returns main L, main R, send L, send R."""
    n = len(next(x for x in inputs if x is not None))
    out = np.zeros((4, n))
    for c, x in enumerate(inputs):
        g = np.tile(channel_gains(*settings[c])[:, None], (1, n)).astype(np.float64)
        cur = channel_gains(*settings[c])
        for at, ch, s in sorted(changes):
            if ch != c:
                continue
            target = channel_gains(*s)
            for k in range(4):
                g[k, at:] = ramp(g[k, at - 1] if at > 0 else cur[k], target[k], ramp_samples,
                                 n - at)
        if x is not None:
            out += g * np.asarray(x, dtype=np.float64)[None, :]
    return out


def crossfeed(xl, xr, fs, amount, fc=700.0, delay_us=0.0, max_gain=0.596):
    """Settled at `amount` from the start."""
    g = min(max(amount, 0.0), 1.0) * max_gain
    a = onepole_coef(fs, fc)
    d = int(delay_us * 1e-6 * fs + 0.5)
    lp = []
    for x in (xl, xr):
        y = np.zeros(len(x))
        z = 0.0
        for i, v in enumerate(np.asarray(x, dtype=np.float64)):
            z = v + a * (z - v)
            y[i] = z
        lp.append(y)
    delayed = [np.concatenate([np.zeros(d), v[:len(v) - d]]) for v in lp]
    xl, xr = (np.asarray(v, dtype=np.float64) for v in (xl, xr))
    yl = ((1 + g) * xl - g * lp[0] + g * delayed[1]) / (1 + g)
    yr = ((1 + g) * xr - g * lp[1] + g * delayed[0]) / (1 + g)
    return yl, yr


def crossfeed_response(fs, amount, f, fc=700.0, delay_us=0.0, max_gain=0.596):
    """Complex responses at f: (near ear from its own channel, far ear from the other)."""
    g = min(max(amount, 0.0), 1.0) * max_gain
    a = onepole_coef(fs, fc)
    d = int(delay_us * 1e-6 * fs + 0.5)
    z = np.exp(-2j * np.pi * np.asarray(f, dtype=np.float64) / fs)
    lp = (1 - a) / (1 - a * z)
    near = ((1 + g) - g * lp) / (1 + g)
    far = g * lp * z ** d / (1 + g)
    return near, far
