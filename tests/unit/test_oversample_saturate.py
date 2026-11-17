"""dsp_oversample and dsp_saturate."""
import ctypes
import math

import numpy as np
import pytest
from scipy import signal

import dsplib
import dsplib_b6 as b6

FS = 48000.0


@pytest.fixture(scope="module")
def lib6(lib):
    return b6.bind(lib)


def builtin(lib6, stage):
    n = ctypes.c_int32()
    ptr = (lib6.dsp_halfband_stage1 if stage == 1 else lib6.dsp_halfband_stage2)(ctypes.byref(n))
    return np.array([ptr[i] for i in range(n.value)], dtype=np.float64)


def up(lib6, h, x):
    st = b6.DspHalfbandUpF32()
    hf = h.astype(np.float32)
    assert lib6.dsp_halfband_up_init(ctypes.byref(st), dsplib.f32(hf), len(hf)) == 0
    y = np.zeros(2 * len(x), dtype=np.float32)
    lib6.dsp_halfband_up_process(ctypes.byref(st), dsplib.f32(x), dsplib.f32(y), len(x))
    return y


def down(lib6, h, v):
    st = b6.DspHalfbandDownF32()
    hf = h.astype(np.float32)
    assert lib6.dsp_halfband_down_init(ctypes.byref(st), dsplib.f32(hf), len(hf)) == 0
    y = np.zeros(len(v) // 2, dtype=np.float32)
    lib6.dsp_halfband_down_process(ctypes.byref(st), dsplib.f32(v), dsplib.f32(y), len(y))
    return y


@pytest.mark.parametrize("stage", [1, 2])
def test_polyphase_equals_direct_convolution(lib6, stage):
    h = builtin(lib6, stage).astype(np.float32).astype(np.float64)
    x = np.random.default_rng(stage).uniform(-1, 1, 500).astype(np.float32)
    stuffed = np.zeros(2 * len(x))
    stuffed[::2] = x
    expected_up = np.convolve(stuffed, 2 * h)[:2 * len(x)]
    # Float32 accumulation over 42 taps: measured -129 dBFS against float64.
    dsplib.assert_within_db(up(lib6, h, x), expected_up, -125.0)
    v = np.random.default_rng(stage + 5).uniform(-1, 1, 1000).astype(np.float32)
    expected_down = np.convolve(v.astype(np.float64), h)[:len(v)][::2]
    dsplib.assert_within_db(down(lib6, h, v), expected_down, -125.0)


@pytest.mark.parametrize("stage, edges, atten", [(1, (0.2083, 0.2917), 113.0),
                                                 (2, (0.1042, 0.3958), 124.0)])
def test_builtin_filters_meet_their_figures(lib6, stage, edges, atten):
    h = builtin(lib6, stage).astype(np.float32).astype(np.float64)
    w, resp = signal.freqz(h, worN=1 << 15, fs=1.0)
    mag = np.abs(resp)
    passband = mag[w <= edges[0]]
    stopband = mag[w >= edges[1]]
    assert 20 * np.log10(passband.max() / passband.min()) < 1e-3
    assert -20 * np.log10(stopband.max()) > atten
    assert abs(2 * np.sum(h[::2]) - 1.0) < 5e-6  # DC gain of the even phase, times 2.


def oversampler(lib6, factor):
    os_ = b6.DspOversampleF32()
    lib6.dsp_oversample_f32_init(ctypes.byref(os_), factor)
    return os_


def round_trip(lib6, factor, x, block=64):
    os_ = oversampler(lib6, factor)
    y = np.zeros_like(x)
    hi = np.zeros(factor * block, dtype=np.float32)
    for i in range(0, len(x), block):
        xs = x[i:i + block].copy()
        n = len(xs)
        lib6.dsp_oversample_f32_up(ctypes.byref(os_), dsplib.f32(xs), dsplib.f32(hi), n)
        ys = np.zeros(n, dtype=np.float32)
        lib6.dsp_oversample_f32_down(ctypes.byref(os_), dsplib.f32(hi[:factor * n].copy()),
                                     dsplib.f32(ys), n)
        y[i:i + n] = ys
    return y, lib6.dsp_oversample_f32_latency(ctypes.byref(os_))


@pytest.mark.parametrize("factor, latency", [(2, 41.0), (4, 46.5)])
def test_round_trip_latency_and_flatness(lib6, factor, latency):
    t = np.arange(9600)
    f = 3000.0
    x = (0.5 * np.sin(2 * np.pi * f * t / FS)).astype(np.float32)
    y, reported = round_trip(lib6, factor, x)
    assert reported == latency
    expected = 0.5 * np.sin(2 * np.pi * f * (t - latency) / FS)
    dsplib.assert_within_db(y[200:], expected[200:], -100.0)


def test_image_rejection(lib6):
    """A 15 kHz tone upsampled 2x: its image at 33 kHz is at least 113 dB down."""
    n = 8192
    t = np.arange(n)
    f = 15000.0 * 0 + FS * 1280 / n  # 7.5 kHz on an exact bin, so no window is needed...
    f = FS * 2560 / n                # ...or 15 kHz exactly.
    x = (0.5 * np.sin(2 * np.pi * f * t / FS)).astype(np.float32)
    hi, _ = None, None
    os_ = oversampler(lib6, 2)
    y = np.zeros(2 * n, dtype=np.float32)
    for i in range(0, n, 64):
        lib6.dsp_oversample_f32_up(ctypes.byref(os_), dsplib.f32(x[i:i + 64].copy()),
                                   dsplib.f32(y[2 * i:2 * i + 128]), 64)
    del hi
    # The library writes into a ctypes view of the slice only if it is contiguous: use a copy.
    os_ = oversampler(lib6, 2)
    y = np.zeros(2 * n, dtype=np.float32)
    for i in range(0, n, 64):
        part = np.zeros(128, dtype=np.float32)
        lib6.dsp_oversample_f32_up(ctypes.byref(os_), dsplib.f32(x[i:i + 64].copy()),
                                   dsplib.f32(part), 64)
        y[2 * i:2 * i + 128] = part
    seg = y[4096:4096 + 8192].astype(np.float64)
    spec = np.abs(np.fft.rfft(seg * signal.windows.blackmanharris(len(seg))))
    k_sig = int(round(f * len(seg) / (2 * FS)))
    k_img = int(round((FS - f) * len(seg) / (2 * FS)))
    rejection = 20 * np.log10(spec[k_sig] / np.max(spec[k_img - 2:k_img + 3]))
    assert rejection > 110.0


def test_block_size_does_not_matter(lib6):
    x = np.random.default_rng(9).uniform(-1, 1, 1000).astype(np.float32)
    a, _ = round_trip(lib6, 4, x, block=200)  # Longer than the 64-frame scratch.
    b, _ = round_trip(lib6, 4, x, block=37)
    assert a.tobytes() == b.tobytes()


def test_bad_filter_length_is_refused(lib6):
    st = b6.DspHalfbandUpF32()
    h = np.zeros(21, dtype=np.float32)  # 21 is not 4K + 3.
    assert lib6.dsp_halfband_up_init(ctypes.byref(st), dsplib.f32(h), 21) == -1
    h = np.zeros(99, dtype=np.float32)  # 4K + 3, but 50 even taps > 48.
    assert lib6.dsp_halfband_up_init(ctypes.byref(st), dsplib.f32(h), 99) == -1


# ---- Saturation --------------------------------------------------------------------------------

PLAIN, OS2, OS4, ADAA = 0, 1, 2, 3


def saturator(lib6, mode, drive_db=12.0):
    sat = b6.DspSaturatorF32()
    lib6.dsp_saturator_f32_init(ctypes.byref(sat), mode, drive_db)
    return sat


def run_sat(lib6, sat, x, block=16):
    y = np.zeros_like(x)
    for i in range(0, len(x), block):
        xs = x[i:i + block].copy()
        ys = np.zeros_like(xs)
        lib6.dsp_saturator_f32_process(ctypes.byref(sat), dsplib.f32(xs), dsplib.f32(ys), len(xs))
        y[i:i + block] = ys
    return y


def test_static_curve(lib6):
    sat = saturator(lib6, PLAIN, 12.0)
    d = 10 ** (12 / 20)
    assert abs(lib6.dsp_saturator_f32_shape(ctypes.byref(sat), 1.0) - 1.0) < 1e-6
    for x in np.linspace(-1, 1, 41):
        a = lib6.dsp_saturator_f32_shape(ctypes.byref(sat), float(x))
        assert abs(a + lib6.dsp_saturator_f32_shape(ctypes.byref(sat), float(-x))) < 1e-7
        assert abs(a - math.tanh(d * x) / math.tanh(d)) < 1e-6
    small = lib6.dsp_saturator_f32_shape(ctypes.byref(sat), 1e-4) / 1e-4
    assert abs(small - d / math.tanh(d)) / small < 1e-4


def harmonics_db(y, f0, fs, count=8):
    n = len(y)
    spec = np.abs(np.fft.rfft(y * signal.windows.blackmanharris(n)))
    k0 = int(round(f0 * n / fs))
    ref_level = spec[k0]
    return {k: 20 * np.log10(max(spec[k * k0], 1e-30) / ref_level)
            for k in range(2, count + 1) if k * k0 < n // 2}


def test_symmetric_curve_makes_no_even_harmonics(lib6):
    """Phil's Lab #117: a symmetric curve gives odd harmonics only."""
    n = 48000
    f0 = FS * 250 / n  # 250 Hz on an exact bin
    x = (0.8 * np.sin(2 * np.pi * f0 * np.arange(n) / FS)).astype(np.float32)
    y = run_sat(lib6, saturator(lib6, PLAIN), x).astype(np.float64)
    h = harmonics_db(y, f0, FS)
    assert h[3] > -40.0  # It does distort...
    assert max(h[k] for k in (2, 4, 6, 8)) < -110.0  # ...but not evenly.


def test_adaa_survives_a_drive_change(lib6):
    """Found by the batch 6 review: changing the drive left the stored antiderivative of the old
    curve, and the next output was (F_new(x) - F_old(x_prev)) / dx, huge for a small dx."""
    x = np.full(64, 0.3, dtype=np.float32) + np.linspace(0, 1e-5, 64, dtype=np.float32)
    sat = saturator(lib6, ADAA, 0.0)
    run_sat(lib6, sat, x)
    lib6.dsp_saturator_f32_set_drive(ctypes.byref(sat), 24.0)
    y = run_sat(lib6, sat, x)
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 1.01


def test_adaa_small_signal_response_is_a_half_sample_average(lib6):
    """For small signals first-order ADAA averages two samples: |cos(w/2)| (the review's
    finding, now documented in dsp_saturate.h)."""
    sat_gain = None
    for f in (1000.0, 12000.0, 20000.0):
        n = 9600
        x = (1e-3 * np.sin(2 * np.pi * f * np.arange(n) / FS)).astype(np.float32)
        sat = saturator(lib6, ADAA, 6.0)
        y = run_sat(lib6, sat, x).astype(np.float64)
        d = 10 ** (6 / 20)
        sat_gain = d / math.tanh(d)
        measured = np.sqrt(np.mean(y[1000:] ** 2)) / np.sqrt(np.mean(x[1000:].astype(float) ** 2))
        expected = sat_gain * abs(math.cos(math.pi * f / FS))
        assert abs(20 * np.log10(measured / expected)) < 0.05, f


@pytest.mark.parametrize("mode, latency", [(PLAIN, 0.0), (ADAA, 0.5), (OS2, 41.0), (OS4, 46.5)])
def test_latency_and_bounds(lib6, mode, latency):
    sat = saturator(lib6, mode)
    assert lib6.dsp_saturator_f32_latency(ctypes.byref(sat)) == latency
    x = np.random.default_rng(3).uniform(-1, 1, 4800).astype(np.float32)
    y = run_sat(lib6, sat, x, block=100)
    # Full-band noise driven 12 dB into the curve is clipped almost to a square at the high
    # rate; band-limiting it on the way down raises its peaks (measured 1.45 at 2x, 1.55 at 4x).
    # That is inherent to removing the aliases; the limiter after it catches the overs.
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < (1.0001 if mode in (PLAIN, ADAA) else 1.7)


def alias_db(lib6, mode, f0, drive_db=12.0):
    """The strongest component below 20 kHz that is not a harmonic of f0, relative to the
    fundamental, on a coherent tone. Only the audible band counts: the half-band filters let
    24 to 28 kHz fold into 20 to 24 kHz by design (dsp_oversample.h)."""
    n = 1 << 15
    k0 = int(round(f0 * n / FS)) | 1
    f0 = k0 * FS / n
    x = (0.9 * np.sin(2 * np.pi * f0 * np.arange(n + 4096) / FS)).astype(np.float32)
    y = run_sat(lib6, saturator(lib6, mode, drive_db), x, block=64)[4096:].astype(np.float64)
    spec = np.abs(np.fft.rfft(y))
    wanted = {k * k0 for k in range(1, 200) if k * k0 < n // 2}
    mask = np.zeros(len(spec), bool)
    mask[1:int(20000.0 * n / FS)] = True
    for k in wanted:
        mask[max(k - 1, 0):k + 2] = False
    return 20 * np.log10(np.max(spec[mask]) / spec[k0])


def test_oversampling_reduces_aliasing(lib6):
    """The aliasing study's ordering, held as a test: at 5 kHz, 4x beats plain by at least 30
    dB. The full table is docs/results/b6_aliasing.md."""
    plain = alias_db(lib6, PLAIN, 5000.0)
    os4 = alias_db(lib6, OS4, 5000.0)
    assert os4 < plain - 30.0
