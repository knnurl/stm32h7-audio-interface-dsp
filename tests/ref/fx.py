"""Reference models of the batch 8b effects, in float64, written from the headers' equations.
Where a header specifies an approximation (the Pade tan, the polynomial sine), the model uses
the exact function unless stated: the tests' tolerances absorb the difference.
Parameters come from the C struct after its setters ran (coefficients, delays), so the model
checks the processing, and separate tests check the setters' formulas."""
import math

import numpy as np

from ref.modulation import lfo_value, lfo_value_f32, read_lagrange


def onepole_coef(fs, fc):
    return math.exp(-2 * math.pi * min(fc, 0.49 * fs) / fs) if fc > 0 else 0.0


def onepole_hp_mag(fs, fc, f):
    """|x - lp(x)| of the digital one-pole at f: a (1 - z^-1) / (1 - a z^-1)."""
    a = onepole_coef(fs, fc)
    z = complex(math.cos(2 * math.pi * f / fs), -math.sin(2 * math.pi * f / fs))
    return abs(a * (1 - z) / (1 - a * z))


def pade_g(fs, fc):
    x = math.pi * min(max(fc, 1.0), 0.45 * fs) / fs
    return x * (15 - x * x) / (15 - 6 * x * x)


# ---- Echo --------------------------------------------------------------------------------------

def echo(xl, xr, delay, fb, lp_a, hp_a, wet, ping_pong=False):
    """`delay` is the read position the C struct holds (the echo time in samples minus 1)."""
    n = len(xl)
    hist = [np.zeros(n + 8), np.zeros(n + 8)]
    lp = [0.0, 0.0]
    hpz = [0.0, 0.0]
    out = [np.empty(n), np.empty(n)]
    for i in range(n):
        r = []
        f = []
        for ch in range(2):
            k = i - 1 - delay  # hist index of the sample `delay` before the newest
            rv = hist[ch][int(k)] if k >= 0 else 0.0
            r.append(rv)
            lp[ch] = rv + lp_a * (lp[ch] - rv)
            hpz[ch] = lp[ch] + hp_a * (hpz[ch] - lp[ch])
            f.append(lp[ch] - hpz[ch])
        if ping_pong:
            hist[0][i] = 0.5 * (xl[i] + xr[i]) + fb * f[1]
            hist[1][i] = fb * f[0]
        else:
            hist[0][i] = xl[i] + fb * f[0]
            hist[1][i] = xr[i] + fb * f[1]
        out[0][i] = wet * r[0]
        out[1][i] = wet * r[1]
    return out


def quantise_s16(v):
    """dsp_delayline_s16's storage: 2^13 per 1.0, saturated; rounded to nearest (halves away from
    zero) at and above 16 LSB, toward zero below (the limit-cycle fix); in float32 arithmetic.
    Returns the stored value as float32."""
    s = np.float32(v) * np.float32(8192.0)
    if not s >= np.float32(-32768.0):
        s = np.float32(0.0) if s != s else np.float32(-32768.0)
    elif s > np.float32(32767.0):
        s = np.float32(32767.0)
    if s >= np.float32(16.0) or s <= np.float32(-16.0):
        q = int(s + (np.float32(0.5) if s >= 0 else np.float32(-0.5)))
    else:
        q = int(s)
    return np.float32(q) * np.float32(1.0 / 8192.0)


def echo16(xl, xr, delay, fb, lp_a, hp_a, wet, ping_pong=False):
    """The echo at fs <= 48 kHz with 16-bit lines, step for step in float32 (no fused
    multiply-add, as both builds compile it), so it matches the C code bit for bit. `delay` is a
    whole number of samples (the C code rounds the resting delay)."""
    f32 = np.float32
    n = len(xl)
    hist = [np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)]
    lp = [f32(0), f32(0)]
    hpz = [f32(0), f32(0)]
    la, ha, g, w = f32(lp_a), f32(hp_a), f32(fb), f32(wet)
    out = [np.empty(n, dtype=np.float32), np.empty(n, dtype=np.float32)]
    for i in range(n):
        r, f = [], []
        for ch in range(2):
            k = i - 1 - delay
            rv = hist[ch][k] if k >= 0 else f32(0)
            r.append(rv)
            lp[ch] = rv + la * (lp[ch] - rv)
            hpz[ch] = lp[ch] + ha * (hpz[ch] - lp[ch])
            f.append(lp[ch] - hpz[ch])
        if ping_pong:
            hist[0][i] = quantise_s16(f32(0.5) * (f32(xl[i]) + f32(xr[i])) + g * f[1])
            hist[1][i] = quantise_s16(g * f[0])
        else:
            hist[0][i] = quantise_s16(f32(xl[i]) + g * f[0])
            hist[1][i] = quantise_s16(f32(xr[i]) + g * f[1])
        out[0][i] = w * r[0]
        out[1][i] = w * r[1]
    return out


# ---- Chorus and flanger -----------------------------------------------------------------------

def _hist_reader(buf, i):
    """hist[k] = buf[i - k], zeros before the start."""
    class H:
        def __getitem__(self, k):
            j = i - k
            return buf[j] if j >= 0 else 0.0
    return H()


def chorus(xl, xr, fs, amount, inc, right_offset, phase0=0):
    n = len(xl)
    buf = [np.zeros(n), np.zeros(n)]
    centre = 0.020 * fs - 1
    depth = amount * 0.007 * fs
    out = [np.empty(n), np.empty(n)]
    for i in range(n):
        p = (phase0 + i * inc) % 2 ** 32
        offs = [(0, 2 ** 31), (right_offset, right_offset + 2 ** 31)]
        for ch, x in enumerate((xl, xr)):
            acc = 0.0
            for o in offs[ch]:
                d = centre + depth * float(lfo_value_f32(0, p + o))
                acc += read_lagrange(_hist_reader(buf[ch], i - 1), d)
            out[ch][i] = 0.7 * amount * 0.5 * acc
            buf[ch][i] = x[i]
    return out


def flanger(xl, xr, fs, amount, inc, fb, phase0=0):
    n = len(xl)
    buf = [np.zeros(n), np.zeros(n)]
    out = [np.empty(n), np.empty(n)]
    for i in range(n):
        p = (phase0 + i * inc) % 2 ** 32
        for ch, x in enumerate((xl, xr)):
            u = 0.5 + 0.5 * float(lfo_value_f32(1, p + ch * 2 ** 30))
            d = 0.0005 * fs - 1 + amount * 0.0095 * fs * u
            r = read_lagrange(_hist_reader(buf[ch], i - 1), d)
            buf[ch][i] = x[i] + fb * r
            out[ch][i] = 0.7 * r
    return out


# ---- Phaser ----------------------------------------------------------------------------------

def phaser(xl, xr, fs, amount, inc, fb, stages, phase0=0, sub=16):
    n = len(xl)
    state = [[0.0] * stages, [0.0] * stages]
    last = [0.0, 0.0]
    out = [np.empty(n), np.empty(n)]
    for start in range(0, n, sub):
        m = min(sub, n - start)
        p = (phase0 + start * inc) % 2 ** 32
        for ch, x in enumerate((xl, xr)):
            u = 0.5 + 0.5 * float(lfo_value_f32(0, p + ch * 2 ** 30))
            t = pade_g(fs, 200.0 * 2 ** (5 * amount * u))
            c = (t - 1) / (t + 1)
            for i in range(start, start + m):
                v = x[i] + fb * last[ch]
                for k in range(stages):
                    y = c * v + state[ch][k]
                    state[ch][k] = v - c * y
                    v = y
                last[ch] = v
                out[ch][i] = 0.5 * v
    return out


# ---- Tremolo (the owner's exercise: this is its specification) ----------------------------------

def tremolo_gain(phase_cycles, depth, shape=0, edge=0.05):
    u = 0.5 + 0.5 * lfo_value(shape, phase_cycles, edge)
    return 1 - depth * (1 - u)


def tremolo(xl, xr, fs, depth, rate_hz, shape=0, edge=0.05, stereo_phase=0.0, phase0=0.0):
    """Fixed depth and rate; phase0 in cycles at the first sample."""
    n = np.arange(len(xl))
    ph = phase0 + n * rate_hz / fs
    gl = np.array([tremolo_gain(p, depth, shape, edge) for p in ph])
    gr = np.array([tremolo_gain(p + stereo_phase, depth, shape, edge) for p in ph])
    return [np.asarray(xl) * gl, np.asarray(xr) * gr]


# ---- Sweep filter -------------------------------------------------------------------------------

def sweep_map(p):
    p = min(max(p, 0.0), 1.0)
    off = p - 0.5
    dist = abs(off)
    blend = min(max((dist - 0.03) / 0.07, 0.0), 1.0)
    if dist <= 0.03:
        return -1, 0.0, blend
    if off < 0:
        return 0, 20000.0 * (50 / 20000) ** ((0.47 - p) / 0.47), blend
    return 2, 20.0 * (10000 / 20) ** ((p - 0.53) / 0.47), blend


def sweep(x, fs, position, q):
    """One channel at a fixed position (the coefficients do not change)."""
    mode, fc, blend = sweep_map(position)
    if mode < 0:
        return np.asarray(x, dtype=np.float64).copy()
    g = pade_g(fs, fc)
    k = 1 / q
    a1 = 1 / (1 + g * (g + k))
    a2, a3 = g * a1, g * g * a1
    ic1 = ic2 = 0.0
    y = np.empty(len(x))
    for i, v0 in enumerate(np.asarray(x, dtype=np.float64)):
        v3 = v0 - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1, ic2 = 2 * v1 - ic1, 2 * v2 - ic2
        f = v2 if mode == 0 else v0 - k * v1 - v2
        y[i] = v0 + blend * (f - v0)
    return y


# ---- Overdrive -----------------------------------------------------------------------------------

def overdrive_harmonics(amp, f0, fs, drive_db, tone, level_db=0.0, asymmetric=False, count=9):
    """The continuous-time chain for a sine of amplitude `amp` at f0: the linear filters' gains
    at each harmonic around the static curve. Returns harmonic amplitudes 1..count. Valid when
    the 100 Hz high-pass barely touches f0 (f0 >= 1 kHz), so the curve sees the sine itself."""
    d = 10 ** (drive_db / 20)
    norm = 1 / math.tanh(d)
    h_pre = onepole_hp_mag(fs, 100.0, f0)
    bias = 0.3 / d if asymmetric else 0.0
    t = np.arange(4096) / 4096
    y = np.tanh(d * (h_pre * amp * np.sin(2 * np.pi * t) + bias)) * norm
    spec = np.fft.rfft(y) / 2048
    comp = overdrive_comp(drive_db)
    out = []
    fc_post = 1000.0 * 12 ** tone
    for k in range(1, count + 1):
        f = k * f0
        # One-pole low-pass, digital, at its exact magnitude.
        a = onepole_coef(fs, fc_post)
        w = 2 * math.pi * f / fs
        h_post = (1 - a) / abs(1 - a * complex(math.cos(w), -math.sin(w)))
        h_dc = onepole_hp_mag(fs, 10.0, f)
        out.append(abs(spec[k]) * h_post * h_dc * comp * 10 ** (level_db / 20))
    return np.array(out)


def overdrive_comp(drive_db):
    """The compensation table's value, interpolated as the C code does."""
    amp = 0.12589254

    def entry(k):
        d = 10 ** (k / 20)
        j = (np.arange(64) + 0.5) / 64
        y = np.tanh(d * amp * np.sin(2 * np.pi * j)) / math.tanh(d)
        return amp * math.sqrt(0.5) / math.sqrt(np.mean(y ** 2))

    k = int(drive_db)
    if k >= 36:
        return entry(36)
    return entry(k) + (drive_db - k) * (entry(k + 1) - entry(k))


# ---- Bit crusher -------------------------------------------------------------------------------

def crusher(x, steps, inc):
    """One channel, no dither, fixed settings. `steps` = 2^(bits - 1) and `inc` = rate / fs as
    the header says the C code computes them (dsp_fast_exp2f); float32 arithmetic for the phase,
    so the hold instants are the same."""
    steps = np.float32(steps)
    inc = np.float32(inc)
    phase = np.float32(1.0)
    held = 0.0
    y = np.empty(len(x))
    for i, xi in enumerate(np.asarray(x, dtype=np.float32)):
        phase = np.float32(phase + inc)
        if phase >= 1:
            phase = np.float32(phase - np.float32(1))
            v = min(max(float(np.float32(xi * steps)), -float(steps)), float(steps))
            r = math.floor(abs(v) + 0.5) * (1 if v >= 0 else -1)
            held = r / float(steps)
        y[i] = held
    return y


# ---- Reverb ------------------------------------------------------------------------------------

OUT_L = np.array([1, 1, -1, -1, 1, 1, -1, -1], dtype=np.float64)
OUT_R = np.array([1, -1, 1, -1, -1, 1, -1, 1], dtype=np.float64)
INJECT = np.array([1, 1, -1, -1, 1, 1, -1, -1], dtype=np.float64)  # even lines left, odd right


def hadamard8():
    h = np.array([[1.0]])
    for _ in range(3):
        h = np.block([[h, h], [h, -h]])
    return h / math.sqrt(8)


def householder8():
    return np.eye(8) - 2.0 / 8 * np.ones((8, 8))


def reverb(xl, xr, lens, b0, a1, predelay, matrix=None):
    """The FDN without the modulation (the test sets its depth to 0), float64."""
    m = hadamard8() if matrix is None else matrix
    lens = np.asarray(lens)
    n = len(xl)
    total = n + int(lens.max()) + predelay + 2
    lines = np.zeros((8, total))
    z = np.zeros(8)
    yl, yr = np.empty(n), np.empty(n)
    left = np.arange(8) % 2 == 0
    for i in range(n):
        ul = xl[i - predelay] if i >= predelay else 0.0
        ur = xr[i - predelay] if i >= predelay else 0.0
        idx = i - lens
        s = np.where(idx >= 0, lines[np.arange(8), np.maximum(idx, 0)], 0.0)
        yl[i] = 0.35 * OUT_L @ s
        yr[i] = 0.35 * OUT_R @ s
        z = np.asarray(b0) * s + np.asarray(a1) * z
        v = m @ z + INJECT * np.where(left, ul, ur)
        lines[:, i] = v
    return yl, yr
