"""The echo's 16-bit storage and its half-rate core at 88.2 and 96 kHz (owner's decision
2026-11-17): the quantiser, the noise it adds, the repeat time, the passband, and the alias and
image products of the half-band resampling."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
from ref import fx as ref

LSB = 1.0 / 8192


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def make_echo(lib8, fs, seconds=0.5, time_ms=100.0, fb=0.0, tone=1.0):
    n = lib8.dsp_fx_echo_f32_mem_needed(fs, seconds)
    fx = b8.DspFxEchoF32()
    mem = np.zeros(n, dtype=np.float32)
    assert lib8.dsp_fx_echo_f32_init(ctypes.byref(fx), fs, dsplib.f32(mem), n) == 0
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(fx), time_ms)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(fx), fb)
    lib8.dsp_fx_echo_f32_set_tone(ctypes.byref(fx), tone)
    lib8.dsp_fx_echo_f32_reset(ctypes.byref(fx), 1)
    fx.wet.cur = fx.wet.target = 1.0
    fx.wet.left = 0
    return b8.WithMemory(fx, mem)


def run(lib8, e, x, block=16):
    return b8.run_stereo(lib8.dsp_fx_echo_f32_process, e.state, x, x, block=block)


def db(v):
    return 20 * math.log10(v) if v > 0 else -math.inf


# ---- The 16-bit line ---------------------------------------------------------------------------

def test_quantiser(lib8):
    """Nearest (halves away from zero) at and above 16 LSB, toward zero below; saturation at
    +/-4; NaN stores 0."""
    q = lib8.dsp_delayline_s16_quantise
    assert q(0.0) == 0.0 and q(1.0) == 1.0 and q(-1.0) == -1.0
    assert q(16.5 * LSB) == 17 * LSB and q(-16.5 * LSB) == -17 * LSB  # nearest, away from 0
    assert q(16.49 * LSB) == 16 * LSB
    assert q(15.9 * LSB) == 15 * LSB and q(-15.9 * LSB) == -15 * LSB  # toward zero below 16
    assert q(0.9 * LSB) == 0.0
    assert q(10.0) == 32767 * LSB and q(-10.0) == -4.0
    assert q(math.nan) == 0.0 and q(math.inf) == 32767 * LSB
    x = np.random.default_rng(1).uniform(-4, 4, 10000).astype(np.float32)
    got = np.array([q(float(v)) for v in x])
    big = np.abs(x) >= 16 * LSB
    assert np.max(np.abs(got - x)[big]) <= 0.5 * LSB + 1e-9
    assert np.max(np.abs(got - x)[~big]) < LSB and np.all(np.abs(got[~big]) <= np.abs(x[~big]))


def test_line_round_trip(lib8):
    mem = np.zeros(50, dtype=np.float32)  # 100 int16 samples
    dl = b8.DspDelaylineS16()
    assert lib8.dsp_delayline_s16_init(ctypes.byref(dl), dsplib.f32(mem), 100) == 0
    vals = np.random.default_rng(2).uniform(-1, 1, 300).astype(np.float32)
    for v in vals:
        lib8.dsp_delayline_s16_push(ctypes.byref(dl), float(v))
    for d in (0, 1, 50, 99):
        assert lib8.dsp_delayline_s16_tap(ctypes.byref(dl), d) == \
            lib8.dsp_delayline_s16_quantise(float(vals[-1 - d]))


# ---- Noise --------------------------------------------------------------------------------------

def test_noise_without_feedback(lib8):
    """A -6 dBFS 1 kHz burst, no feedback, 48 kHz: the repeat differs from the unquantised one by
    the storage's rounding only (printed, RMS and peak); after the repeat the output is exactly
    zero: no dither, so no idle noise."""
    fs = 48000.0
    e = make_echo(lib8, fs)
    n = int(0.5 * fs)
    x = np.zeros(n, dtype=np.float32)
    x[:9600] = (0.5 * np.sin(2 * np.pi * 1000 * np.arange(9600) / fs)).astype(np.float32)
    yl, _ = run(lib8, e, x)
    rep = yl[4800:4800 + 9600].astype(np.float64)
    ideal = x[:9600].astype(np.float64)
    err = rep - ideal
    rms = db(np.sqrt(np.mean(err ** 2)))
    print(f"no feedback: error RMS {rms:.1f} dBFS, peak {db(np.max(np.abs(err))):.1f} dBFS")
    # Half an LSB at and above 16 LSB, under one below (rounding toward zero there).
    assert rms < -88.0 and np.max(np.abs(err)) < LSB
    assert not np.any(yl[4800 + 9600:])


def test_noise_at_feedback_095(lib8):
    """Feedback 0.95, bright tone, a 1 kHz burst, 20 ms repeats, 48 kHz, against the same echo
    with float lines (the float64 model): the error RMS over the first 2 s is printed. The tail
    must end: with pure round-to-nearest it hung at -59 dBFS for ever (a limit cycle), which is
    why the line rounds toward zero below 16 LSB; now it must reach exact zero."""
    fs = 48000.0
    e = make_echo(lib8, fs, time_ms=20.0, fb=0.95)
    n = int(8 * fs)
    x = np.zeros(n, dtype=np.float32)
    x[:480] = (0.5 * np.sin(2 * np.pi * 1000 * np.arange(480) / fs)).astype(np.float32)
    yl, _ = run(lib8, e, x, block=4800)
    fx = e.state
    m = int(2 * fs)
    ideal, _ = ref.echo(x[:m].astype(np.float64), x[:m].astype(np.float64), int(fx.delay),
                        fx.feedback, fx.lp[0].a, fx.hp[0].a, 1.0)
    err = yl[:m].astype(np.float64) - ideal
    rms = db(np.sqrt(np.mean(err ** 2)))
    tail = yl[int(6 * fs):].astype(np.float64)
    tail_peak = db(np.max(np.abs(tail)))
    print(f"feedback 0.95: error RMS over 2 s {rms:.1f} dBFS; tail peak after 6 s "
          f"{tail_peak:.1f} dBFS; last nonzero sample at "
          f"{(np.flatnonzero(yl)[-1] / fs if np.any(yl) else 0):.2f} s")
    assert rms < -72.0  # measured -74.2 dBFS (-79.5 with pure round-to-nearest, which hangs)
    assert not np.any(tail)


@pytest.mark.parametrize("fb,tone,ping_pong", [(0.5, 1.0, 0), (0.8, 0.0, 0), (0.95, 1.0, 1),
                                               (0.95, 0.3, 0)])
def test_tails_end_in_silence(lib8, fb, tone, ping_pong):
    """Loud noise in, then silence: every combination's tail reaches exact zero."""
    fs = 48000.0
    e = make_echo(lib8, fs, time_ms=30.0, fb=fb, tone=tone)
    lib8.dsp_fx_echo_f32_set_ping_pong(ctypes.byref(e.state), ping_pong)
    n = int(10 * fs)
    x = np.zeros(n, dtype=np.float32)
    x[:4800] = np.random.default_rng(4).uniform(-1, 1, 4800)
    yl, yr = b8.run_stereo(lib8.dsp_fx_echo_f32_process, e.state, x, x, block=4800)
    last = max(np.flatnonzero(yl)[-1], np.flatnonzero(yr)[-1]) / fs
    print(f"fb {fb} tone {tone} ping-pong {ping_pong}: silent from {last:.2f} s")
    assert not np.any(yl[int(8 * fs):]) and not np.any(yr[int(8 * fs):])


# ---- The half-rate core at 96 kHz -----------------------------------------------------------------

@pytest.mark.parametrize("fs", [88200.0, 96000.0])
@pytest.mark.parametrize("time_ms", [100.0, 37.3])
def test_first_repeat_lands_at_the_set_time(lib8, fs, time_ms):
    e = make_echo(lib8, fs, time_ms=time_ms)
    assert e.state.half_rate == 1 and e.state.rate_hz == fs / 2
    x = np.zeros(int(0.2 * fs), dtype=np.float32)
    x[100] = 1.0
    yl, _ = run(lib8, e, x)
    peak = int(np.argmax(np.abs(yl)))
    target = 100 + time_ms * fs / 1000
    print(f"{fs:g} Hz, {time_ms} ms: repeat at {peak - 100} samples, set {target - 100:.1f}")
    assert abs(peak - target) <= 1.0


def test_block_size_does_not_matter(lib8):
    """Odd blocks go through the one-sample holds; the output is the same for any block size."""
    x = np.random.default_rng(3).uniform(-0.5, 0.5, 9600).astype(np.float32)
    outs = []
    for block in (16, 7, 1, 64, 33):
        e = make_echo(lib8, 96000.0, time_ms=20.0, fb=0.5)
        outs.append(run(lib8, e, x, block=block)[0].tobytes())
    assert all(o == outs[0] for o in outs)


def tone_level_db(y, f, fs):
    """Least-squares amplitude of a component at f, dB re 1.0: exact for any length, where an
    FFT peak of an off-bin tone loses up to 0.5 dB to the window (the first version of this
    test did exactly that)."""
    t = np.arange(len(y)) / fs
    basis = np.stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)], axis=1)
    (a, b), *_ = np.linalg.lstsq(basis, y.astype(np.float64), rcond=None)
    return 20 * np.log10(math.hypot(a, b) + 1e-30)


def tone_levels_db(y, freqs, fs):
    """Joint least-squares amplitudes of several components, dB re 1.0. Fitting a small component
    alone lets a large one leak into it over a non-integer number of cycles (the 0.5 tone at
    10 kHz read as -94 dB at 38 kHz that way); fitting them together removes that."""
    t = np.arange(len(y)) / fs
    cols = []
    for f in freqs:
        cols += [np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)]
    coef, *_ = np.linalg.lstsq(np.stack(cols, axis=1), y.astype(np.float64), rcond=None)
    return [20 * np.log10(math.hypot(coef[2 * k], coef[2 * k + 1]) + 1e-30)
            for k in range(len(freqs))]


def test_passband_to_18_khz(lib8):
    """The first repeat's gain through down, line and up, by half-scale sines. The first version
    used an impulse, which measured the 16-bit line's rounding of the impulse response
    (+/-0.008 dB) rather than the filters: that test was wrong."""
    fs = 96000.0
    gains = []
    for f in np.linspace(100.0, 18000.0, 15):
        e = make_echo(lib8, fs, time_ms=10.0)
        x = (0.5 * np.sin(2 * np.pi * f * np.arange(24000) / fs)).astype(np.float32)
        yl, _ = run(lib8, e, x, block=4800)
        gains.append(tone_level_db(yl[4000:], f, fs) - db(0.5))
    print(f"passband 100 Hz to 18 kHz: {min(gains):.4f} to {max(gains):.4f} dB")
    assert max(abs(g) for g in gains) < 0.002


def test_alias_and_image_products(lib8):
    """96 kHz. Alias: a 30 kHz tone at the input folds to 18 kHz at the core's 48 kHz; the
    down filter's stopband stops it. Image: a 10 kHz repeat leaves an image at 38 kHz after the
    up filter. Both against the 0.5 input tone, in dB (printed)."""
    fs = 96000.0
    n = 65536
    t = np.arange(n) / fs
    e = make_echo(lib8, fs, time_ms=10.0)
    x = (0.5 * np.sin(2 * np.pi * 30000 * t)).astype(np.float32)
    yl, _ = run(lib8, e, x, block=4096)
    alias = tone_levels_db(yl[8192:], [18000.0], fs)[0] - db(0.5)
    alias_stored = bool(np.any(e.mem))  # nothing at all is stored if the alias is under an LSB
    e = make_echo(lib8, fs, time_ms=10.0)
    x = (0.5 * np.sin(2 * np.pi * 10000 * t)).astype(np.float32)
    yl, _ = run(lib8, e, x, block=4096)
    wanted, image = (v - db(0.5) for v in tone_levels_db(yl[8192:], [10000.0, 38000.0], fs))
    print(f"alias of 30 kHz at 18 kHz: {alias:.1f} dB (anything stored: {alias_stored}); 10 kHz "
          f"repeat {wanted:.4f} dB, image at 38 kHz {image:.1f} dB")
    assert abs(wanted) < 0.01 and alias < -100.0 and image < -100.0
