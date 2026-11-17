"""dsp_limiter: the ceiling holds on hostile signals, the latency is what it says, quiet signals
pass bit for bit, and bad input cannot get through."""
import ctypes

import numpy as np
import pytest
from scipy import signal

import dsplib
import dsplib_b6 as b6

FS = 48000.0
CEILING_DB = -1.0
CEILING = 10 ** (CEILING_DB / 20)


@pytest.fixture(scope="module")
def lib6(lib):
    return b6.bind(lib)


def make(lib6, lookahead_ms=1.0, release_ms=50.0):
    lim = b6.DspLimiterF32()
    lib6.dsp_limiter_f32_init(ctypes.byref(lim), FS, CEILING_DB, lookahead_ms, release_ms)
    return lim


def run(lib6, lim, left, right=None, block=16):
    right = left if right is None else right
    out_l, out_r = np.zeros_like(left), np.zeros_like(right)
    for i in range(0, len(left), block):
        l, r = left[i:i + block].copy(), right[i:i + block].copy()
        ol, orr = np.zeros_like(l), np.zeros_like(r)
        lib6.dsp_limiter_f32_process(ctypes.byref(lim), dsplib.f32(l), dsplib.f32(r),
                                     dsplib.f32(ol), dsplib.f32(orr), len(l))
        out_l[i:i + block], out_r[i:i + block] = ol, orr
    return out_l, out_r


def true_peak_db(y):
    return 20 * np.log10(np.max(np.abs(signal.resample_poly(y.astype(np.float64), 8, 1))))


def hostile():
    rng = np.random.default_rng(4)
    n = 24000
    t = np.arange(n)
    square = np.where((t // 24) % 2 == 0, 2.0, -2.0)
    # Inter-sample peaks: a quarter-rate sine at 45 degrees, samples at 0.707 of its true peak.
    isp = 1.9 * np.sin(2 * np.pi * (FS / 4) * t / FS + np.pi / 4)
    bursts = rng.standard_normal(n) * 3.0 * ((t // 2400) % 2 == 0)
    spikes = np.zeros(n)
    spikes[::997] = 4.0
    return {"square": square, "inter-sample": isp, "bursts": bursts, "spikes": spikes}


@pytest.mark.parametrize("lookahead_ms", [0.0, 2.0, 10.0])  # 0 is raised to 32 samples
def test_no_sample_exceeds_the_ceiling(lib6, lookahead_ms):
    for name, x in hostile().items():
        x = x.astype(np.float32)
        y, _ = run(lib6, make(lib6, lookahead_ms), x, -x)
        assert np.max(np.abs(y)) <= CEILING * (1 + 1e-6), name


def test_true_peak_overshoot_against_lookahead(lib6):
    """The guarantee is per sample; the true peak can exceed the ceiling by the gain's own
    sidebands. Measured for several look-aheads (printed; the table is in docs/notes/limiter.md).
    Held at the measured worst case for the 32-sample minimum, 0.25 dB, until the owner decides
    between a longer minimum look-ahead and a margin below the ceiling."""
    table = {}
    for lookahead_ms in (0.0, 1.0, 2.0, 5.0):  # 32, 48, 96, 240 samples
        worst = 0.0
        for name, x in hostile().items():
            x = x.astype(np.float32)
            y, _ = run(lib6, make(lib6, lookahead_ms), x, x)
            worst = max(worst, true_peak_db(y[2000:]) - CEILING_DB)
        table[lookahead_ms] = round(worst, 3)
    print(f"worst true-peak overshoot (dB) by look-ahead (ms): {table}")
    assert table[0.0] < 0.25


def test_latency_is_lookahead_plus_24(lib6):
    lim = make(lib6, 2.0)
    latency = lib6.dsp_limiter_f32_latency(ctypes.byref(lim))
    assert latency == 96 + 24
    x = np.zeros(1000, dtype=np.float32)
    x[100] = 0.5
    y, _ = run(lib6, lim, x)
    assert np.argmax(np.abs(y)) == 100 + latency and y[100 + latency] == np.float32(0.5)


def test_below_the_ceiling_is_bit_exact(lib6):
    x = (np.random.default_rng(5).uniform(-1, 1, 9600) * 0.5).astype(np.float32)
    lim = make(lib6, 1.0)
    y, _ = run(lib6, lim, x)
    d = lib6.dsp_limiter_f32_latency(ctypes.byref(lim))
    assert y[d:].tobytes() == x[:-d].tobytes()


def test_release_returns_to_bit_exact(lib6):
    lim = make(lib6, 1.0, release_ms=20.0)
    loud = np.full(4800, 3.0, dtype=np.float32)
    quiet = (np.random.default_rng(6).uniform(-1, 1, 96000) * 0.3).astype(np.float32)
    x = np.concatenate([loud, quiet])
    y, _ = run(lib6, lim, x)
    d = lib6.dsp_limiter_f32_latency(ctypes.byref(lim))
    tail = slice(len(x) - 4800, len(x))
    assert y[tail].tobytes() == x[tail.start - d:tail.stop - d].tobytes()


def test_bad_input_cannot_get_through(lib6):
    x = (np.random.default_rng(7).uniform(-1, 1, 4800) * 0.5).astype(np.float32)
    x[1000] = np.nan
    x[2000] = np.inf
    x[3000] = -np.inf
    y, _ = run(lib6, make(lib6, 1.0), x, x)
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= CEILING * (1 + 1e-6)


def test_sample_counter_wrap(lib6):
    """The sliding minimum compares sample indices modulo 2^32; start just before the wrap."""
    lim = make(lib6, 1.0)
    lim.t = 2 ** 32 - 500
    x = hostile()["bursts"].astype(np.float32)
    y, _ = run(lib6, lim, x)
    assert np.max(np.abs(y)) <= CEILING * (1 + 1e-6)


def test_stereo_link(lib6):
    """A peak in one channel turns both down by the same amount."""
    n = 4800
    left = np.full(n, 0.5, dtype=np.float32)
    right = np.full(n, 0.5, dtype=np.float32)
    left[2000:2200] = 2.0
    yl, yr = run(lib6, make(lib6, 1.0), left, right)
    d = 48 + 24
    gain_l = yl[2000 + d + 50] / left[2000 + 50]
    gain_r = yr[2000 + d + 50] / right[2000 + 50]
    assert gain_l < 0.5 and abs(gain_l - gain_r) < 1e-6
