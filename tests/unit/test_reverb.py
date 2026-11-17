"""dsp_reverb: decay times by Schroeder integration, no growth over a minute at the longest
decay, echo density, decorrelation, pre-delay, lengths."""
import ctypes
import math

import numpy as np
import pytest
from scipy import signal

import dsplib
import dsplib_b8b as b8
from ref import fx as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def make(lib8, fs=FS, low=2.0, high=0.8, predelay_ms=0.0):
    rev = b8.DspReverbF32()
    need = lib8.dsp_reverb_f32_mem_needed(fs)
    mem = np.zeros(need, dtype=np.float32)
    assert lib8.dsp_reverb_f32_init(ctypes.byref(rev), fs, dsplib.f32(mem), need) == 0
    lib8.dsp_reverb_f32_set_decay(ctypes.byref(rev), low, high)
    lib8.dsp_reverb_f32_set_predelay_ms(ctypes.byref(rev), predelay_ms)
    return b8.WithMemory(rev, mem)


def impulse_response(lib8, r, seconds, fs=FS):
    x = np.zeros(int(seconds * fs), dtype=np.float32)
    x[0] = 1.0
    return b8.run_stereo(lib8.dsp_reverb_f32_process, r.state, x, np.zeros_like(x), block=4800)


def expected_t60(rev, f, fs=FS):
    """Mean over the lines of -3 L / (fs log10 |b0 / (1 - a1 e^-jw)|)."""
    z = complex(math.cos(2 * math.pi * f / fs), -math.sin(2 * math.pi * f / fs))
    t = []
    for i in range(8):
        h = abs(rev.b0[i] / (1 - rev.a1[i] * z))
        t.append(-3 * rev.len[i] / (fs * math.log10(h)))
    return float(np.mean(t)), float(np.ptp(t))


def schroeder_t60(h, f, fs=FS):
    """Octave band around f, backward-integrated energy, slope fitted from -5 to -25 dB."""
    sos = signal.butter(4, [f / math.sqrt(2), f * math.sqrt(2)], btype="band", fs=fs,
                        output="sos")
    y = signal.sosfilt(sos, h.astype(np.float64))
    edc = np.cumsum(y[::-1] ** 2)[::-1]
    edc_db = 10 * np.log10(edc / edc[0])
    i5 = np.argmax(edc_db <= -5)
    i25 = np.argmax(edc_db <= -25)
    t = np.arange(i5, i25) / fs
    slope = np.polyfit(t, edc_db[i5:i25], 1)[0]
    return -60.0 / slope


def test_lengths_are_distinct_primes(lib8):
    for fs in (44100.0, 48000.0, 96000.0):
        r = make(lib8, fs)
        lens = list(r.state.len)
        assert len(set(lens)) == 8
        assert all(all(n % d for d in range(2, int(n ** 0.5) + 1)) for n in lens)
        assert lens[0] >= round(0.0193 * fs) and lens[7] < round(0.0479 * fs) * 1.01


def test_memory_check(lib8):
    need = lib8.dsp_reverb_f32_mem_needed(FS)
    mem = np.zeros(need, dtype=np.float32)
    assert lib8.dsp_reverb_f32_init(ctypes.byref(b8.DspReverbF32()), FS, dsplib.f32(mem),
                                    need - 1) == -1
    print(f"memory: {need} floats at 48 kHz, {lib8.dsp_reverb_f32_mem_needed(96000.0)} at 96 kHz")


@pytest.mark.parametrize("low,high", [(2.0, 0.8), (1.0, 1.0), (4.0, 1.5)])
def test_decay_time_by_schroeder_integration(lib8, low, high):
    """Within 10 % of the designed decay at 500 Hz and 4 kHz (8b.4)."""
    r = make(lib8, low=low, high=high)
    hl, _ = impulse_response(lib8, r, 1.5 * low)
    for f in (500.0, 4000.0):
        want, spread = expected_t60(r.state, f)
        got = schroeder_t60(hl, f)
        print(f"T60 set {low}/{high} s, at {f:g} Hz: designed {want:.3f} s (lines within "
              f"{spread:.3f}), measured {got:.3f} s")
        assert abs(got / want - 1) < 0.10


def test_no_growth_over_a_minute_at_the_longest_decay(lib8):
    """20 s at both ends: a noise burst, then 60 s of silence. The energy in each second must
    fall, by about 3 dB (60 dB / 20 s), never rise."""
    r = make(lib8, low=20.0, high=20.0)
    n = int(61 * FS)
    x = np.zeros(n, dtype=np.float32)
    x[:4800] = np.random.default_rng(1).uniform(-0.5, 0.5, 4800)
    yl, yr = b8.run_stereo(lib8.dsp_reverb_f32_process, r.state, x, x, block=4800)
    e = np.array([np.sum(yl[k:k + 48000].astype(np.float64) ** 2 +
                         yr[k:k + 48000].astype(np.float64) ** 2) for k in range(48000, n - 47999,
                                                                                  48000)])
    drops = -10 * np.log10(e[1:] / e[:-1])
    print(f"per-second drop: min {drops.min():.2f} dB, mean {drops.mean():.2f} dB")
    assert np.all(drops > 0) and abs(drops.mean() - 3.0) < 0.3


def ned(h, fs=FS, window_ms=20.0):
    """Abel and Huang's normalised echo density, per 20 ms window: the fraction of samples more
    than one standard deviation from 0, over a Gaussian's 0.3173."""
    w = int(window_ms * 1e-3 * fs)
    out = []
    for k in range(0, len(h) - w, w // 4):
        seg = h[k:k + w].astype(np.float64)
        out.append(np.mean(np.abs(seg) > seg.std()) / 0.3173)
    return np.array(out), w // 4


def test_echo_density(lib8):
    r = make(lib8, low=2.0, high=1.0)
    hl, _ = impulse_response(lib8, r, 0.6)
    d, hop = ned(hl)
    first = int(np.argmax(d >= 0.9))
    t_ms = first * hop / FS * 1000
    print(f"normalised echo density reaches 0.9 at {t_ms:.0f} ms; "
          f"at 100/200/400 ms: {d[int(0.1 * FS / hop)]:.2f}/{d[int(0.2 * FS / hop)]:.2f}/"
          f"{d[int(0.4 * FS / hop)]:.2f}")
    # Measured 195 ms (Hadamard; the Householder comparison is in test_matrix_choice). Held as
    # a regression bound, not a target from the plan, which asks for the figure to be stated.
    assert d[first] >= 0.9 and t_ms < 250.0


def test_matches_the_model_without_modulation(lib8):
    r = make(lib8, low=1.5, high=0.6, predelay_ms=5.0)
    r.state.mod_depth = 0.0
    x = np.random.default_rng(2).uniform(-0.5, 0.5, 9600).astype(np.float32)
    x2 = np.random.default_rng(3).uniform(-0.5, 0.5, 9600).astype(np.float32)
    yl, yr = b8.run_stereo(lib8.dsp_reverb_f32_process, r.state, x, x2)
    rv = r.state
    el, er = ref.reverb(x.astype(np.float64), x2.astype(np.float64), list(rv.len), list(rv.b0),
                        list(rv.a1), rv.predelay)
    dsplib.assert_within_db(yl, el, -100.0)
    dsplib.assert_within_db(yr, er, -100.0)


def test_matrix_choice(lib8):
    """The design note's reason for Hadamard: echo density builds faster than with a
    Householder matrix of the same order (measured on the model, same lengths and filters)."""
    r = make(lib8, low=2.0, high=1.0)
    rv = r.state
    x = np.zeros(int(0.5 * FS))
    x[0] = 1.0
    times = {}
    for name, m in (("Hadamard", ref.hadamard8()), ("Householder", ref.householder8())):
        hl, _ = ref.reverb(x, np.zeros_like(x), list(rv.len), list(rv.b0), list(rv.a1), 0, m)
        d, hop = ned(hl)
        times[name] = int(np.argmax(d >= 0.9)) * hop / FS * 1000 if np.any(d >= 0.9) else 1e9
    print("echo density 0.9 reached at (ms):", times)
    assert times["Hadamard"] < times["Householder"]


def test_left_and_right_are_decorrelated(lib8):
    r = make(lib8)
    hl, hr = impulse_response(lib8, r, 1.0)
    c = np.corrcoef(hl.astype(np.float64), hr.astype(np.float64))[0, 1]
    print(f"left/right correlation of the impulse response: {c:.3f}")
    assert abs(c) < 0.2


def test_predelay(lib8):
    r = make(lib8, predelay_ms=25.0)
    hl, hr = impulse_response(lib8, r, 0.2)
    first = int(np.flatnonzero(np.abs(hl) + np.abs(hr) > 0)[0])
    assert first == round(0.025 * FS) + r.state.len[0]


def test_deterministic(lib8):
    a = impulse_response(lib8, make(lib8), 0.5)[0]
    b = impulse_response(lib8, make(lib8), 0.5)[0]
    assert a.tobytes() == b.tobytes()
