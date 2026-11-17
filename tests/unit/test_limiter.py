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
MARGIN_DB = 0.5  # DSP_LIMITER_TRUE_PEAK_MARGIN_DB
THRESHOLD = 10 ** ((CEILING_DB - MARGIN_DB) / 20)


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
    """True peak by 8x resampling, the first and last 200 input samples' worth left out:
    resample_poly pads with zeros, and the cut edges ring (Gibbs, up to about 0.77 dB). Found
    2026-11-17: a quarter-rate sine read 3.77 dB over its sample peak instead of the 3.01 of
    theory. The batch 6 worst case (the noise bursts) did not change."""
    up = signal.resample_poly(y.astype(np.float64), 8, 1)
    return 20 * np.log10(np.max(np.abs(up[8 * 200:-8 * 200])))


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
        assert np.max(np.abs(y)) <= THRESHOLD * (1 + 1e-6), name


def test_true_peak_stays_under_the_set_ceiling(lib6):
    """The per-sample guarantee is against the threshold (ceiling less 0.5 dB). 4x detection
    under-reads inter-sample peaks, so the true peak can exceed the threshold (0.198 dB measured,
    printed); the margin keeps it under the set ceiling at every look-ahead."""
    table = {}
    for lookahead_ms in (0.0, 1.0, 2.0, 5.0):  # 32, 48, 96, 240 samples
        worst = -99.0
        for name, x in hostile().items():
            x = x.astype(np.float32)
            y, _ = run(lib6, make(lib6, lookahead_ms), x, x)
            worst = max(worst, true_peak_db(y[2000:]) - (CEILING_DB - MARGIN_DB))
        table[lookahead_ms] = round(worst, 3)
    print(f"worst true-peak over the threshold (dB) by look-ahead (ms): {table}")
    assert max(table.values()) < MARGIN_DB


def test_latency_is_lookahead_plus_9(lib6):
    lim = make(lib6, 2.0)
    latency = lib6.dsp_limiter_f32_latency(ctypes.byref(lim))
    assert latency == 96 + 9
    x = np.zeros(1000, dtype=np.float32)
    x[100] = 0.5
    y, _ = run(lib6, lim, x)
    assert np.argmax(np.abs(y)) == 100 + latency and y[100 + latency] == np.float32(0.5)


def test_below_the_ceiling_is_bit_exact(lib6):
    # White noise has inter-sample peaks well above its sample peak: 0.4 keeps them under the
    # threshold (0.5 reached it once the margin lowered the threshold to -1.5 dBFS).
    x = (np.random.default_rng(5).uniform(-1, 1, 9600) * 0.4).astype(np.float32)
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
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= THRESHOLD * (1 + 1e-6)


def test_sample_counter_wrap(lib6):
    """The sliding minimum compares sample indices modulo 2^32; start just before the wrap."""
    lim = make(lib6, 1.0)
    lim.t = 2 ** 32 - 500
    x = hostile()["bursts"].astype(np.float32)
    y, _ = run(lib6, lim, x)
    assert np.max(np.abs(y)) <= THRESHOLD * (1 + 1e-6)


def test_stereo_link(lib6):
    """A peak in one channel turns both down by the same amount."""
    n = 4800
    left = np.full(n, 0.5, dtype=np.float32)
    right = np.full(n, 0.5, dtype=np.float32)
    left[2000:2200] = 2.0
    yl, yr = run(lib6, make(lib6, 1.0), left, right)
    d = 48 + 9
    gain_l = yl[2000 + d + 50] / left[2000 + 50]
    gain_r = yr[2000 + d + 50] / right[2000 + 50]
    assert gain_l < 0.5 and abs(gain_l - gain_r) < 1e-6


# ---- Sample-peak mode (the headphones) --------------------------------------------------------

SAMPLE_PEAK = 1


def make_sp(lib6, lookahead_ms=1.0, release_ms=50.0):
    lim = b6.DspLimiterF32()
    lib6.dsp_limiter_f32_init_mode(ctypes.byref(lim), FS, CEILING_DB, lookahead_ms, release_ms,
                                   SAMPLE_PEAK)
    return lim


@pytest.mark.parametrize("lookahead_ms", [0.0, 2.0, 10.0])
def test_sample_peak_no_sample_exceeds_the_ceiling(lib6, lookahead_ms):
    """The threshold is the ceiling itself in this mode (no true-peak margin)."""
    for name, x in hostile().items():
        x = x.astype(np.float32)
        y, yr = run(lib6, make_sp(lib6, lookahead_ms), x, -x)
        assert max(np.max(np.abs(y)), np.max(np.abs(yr))) <= CEILING * (1 + 1e-6), name


def test_sample_peak_latency_is_lookahead_plus_1(lib6):
    lim = make_sp(lib6, 2.0)
    latency = lib6.dsp_limiter_f32_latency(ctypes.byref(lim))
    assert latency == 96 + 1
    x = np.zeros(1000, dtype=np.float32)
    x[100] = 0.5
    y, _ = run(lib6, lim, x)
    assert np.argmax(np.abs(y)) == 100 + latency and y[100 + latency] == np.float32(0.5)


def test_sample_peak_below_the_ceiling_is_bit_exact_and_releases(lib6):
    lim = make_sp(lib6, 1.0, release_ms=20.0)
    loud = np.full(4800, 3.0, dtype=np.float32)
    quiet = (np.random.default_rng(6).uniform(-1, 1, 96000) * 0.5).astype(np.float32)
    x = np.concatenate([loud, quiet])
    y, _ = run(lib6, lim, x)
    d = lib6.dsp_limiter_f32_latency(ctypes.byref(lim))
    tail = slice(len(x) - 4800, len(x))
    assert y[tail].tobytes() == x[tail.start - d:tail.stop - d].tobytes()


def test_sample_peak_true_peak_overshoot_is_documented(lib6):
    """Not guaranteed in this mode: the inter-sample peaks. Measured and bounded here so a change
    shows; the figure is in the header and docs/notes/limiter.md."""
    worst = -99.0
    for name, x in hostile().items():
        x = x.astype(np.float32)
        y, _ = run(lib6, make_sp(lib6, 1.0), x, x)
        worst = max(worst, true_peak_db(y[2000:]) - CEILING_DB)
    print(f"sample-peak mode: worst true peak over the ceiling {worst:.2f} dB")
    assert worst < 3.2


def test_sample_peak_bad_input(lib6):
    x = (np.random.default_rng(7).uniform(-1, 1, 4800) * 0.5).astype(np.float32)
    x[1000] = np.nan
    x[2000] = np.inf
    y, _ = run(lib6, make_sp(lib6, 1.0), x, x)
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= CEILING * (1 + 1e-6)

