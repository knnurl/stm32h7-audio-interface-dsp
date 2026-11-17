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


def band_sos(f, fs=FS):
    return signal.butter(4, [f / math.sqrt(2), f * math.sqrt(2)], btype="band", fs=fs,
                         output="sos")


def fit_t60(edc_db, fs):
    i5 = np.argmax(edc_db <= -5)
    i25 = np.argmax(edc_db <= -25)
    t = np.arange(i5, i25) / fs
    return -60.0 / np.polyfit(t, edc_db[i5:i25], 1)[0]


def designed_band_t60(rev, f, fs=FS, seconds=4.0):
    """The decay the design gives an octave band measured the same way: every frequency in the
    band decays at its own designed rate (the mean over the lines), weighted by the band
    filter's power; that sum of exponentials is backward-integrated and fitted from -5 to
    -25 dB like the measurement. Comparing a band to the design value at its centre is wrong
    where the decay time changes fast across the band (5.7 to 11.3 kHz for the 8 kHz band:
    measured +11 % against the centre value, the first version of this test)."""
    sos = band_sos(f, fs)
    freqs = np.geomspace(f / 2, min(f * 2, 0.49 * fs), 200)
    _, h = signal.sosfreqz(sos, worN=freqs, fs=fs)
    w = np.abs(h) ** 2 * freqs  # power per log-spaced point: df is proportional to f
    t60 = np.array([expected_t60(rev, fk, fs)[0] for fk in freqs])
    t = np.arange(int(seconds * fs)) / fs
    energy = (w[:, None] * 10 ** (-6 * t[None, :] / t60[:, None])).sum(axis=0)
    edc = np.cumsum(energy[::-1])[::-1]
    return fit_t60(10 * np.log10(edc / edc[0]), fs)


def schroeder_t60(h, f, fs=FS):
    """Octave band around f, backward-integrated energy, slope fitted from -5 to -25 dB."""
    y = signal.sosfilt(band_sos(f, fs), h.astype(np.float64))
    edc = np.cumsum(y[::-1] ** 2)[::-1]
    return fit_t60(10 * np.log10(edc / edc[0]), fs)


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
    assert lib8.dsp_reverb_f32_mem_needed(96000.0) == 35718  # 50 ms stereo pre-delay: 9608


@pytest.mark.parametrize("low,high", [(2.0, 0.8), (1.0, 1.0), (4.0, 1.5)])
def test_decay_time_by_schroeder_integration(lib8, low, high):
    """Within 10 % of the designed decay at 500 Hz, 4 kHz and 8 kHz (8b.4; 8 kHz since T_hi is
    anchored there, owner 2026-11-17)."""
    r = make(lib8, low=low, high=high)
    hl, _ = impulse_response(lib8, r, 1.5 * low)
    for f in (500.0, 4000.0, 8000.0):
        point, spread = expected_t60(r.state, f)
        want = designed_band_t60(r.state, f, seconds=1.5 * low)
        got = schroeder_t60(hl, f)
        print(f"T60 set {low}/{high} s, octave at {f:g} Hz: designed {want:.3f} s (at the "
              f"centre {point:.3f}, lines within {spread:.3f}), measured {got:.3f} s")
        assert abs(got / want - 1) < 0.10


@pytest.mark.parametrize("fs", [44100.0, 48000.0, 96000.0])
@pytest.mark.parametrize("low,high", [(2.0, 0.5), (20.0, 0.05), (1.0, 1.0)])
def test_high_decay_is_anchored_at_8_khz(lib8, fs, low, high):
    """The absorbent filter's design: each line's loss per second is 60 / T_lo dB at DC and
    60 / T_hi dB at 8 kHz exactly; the pole stays in [0, 1) and the gain never exceeds the DC
    gain (so the loop gain is below 1)."""
    r = make(lib8, fs=fs, low=low, high=high)
    rv = r.state
    assert rv.high_anchor_hz == pytest.approx(8000.0)
    for f, want in ((0.0, low), (8000.0, high)):
        got, spread = expected_t60(rv, f, fs) if f > 0 else expected_t60(rv, 1e-6, fs)
        assert got == pytest.approx(want, rel=2e-3) and spread < 2e-3 * want, (f, got, spread)
    for i in range(8):
        a1, b0 = rv.a1[i], rv.b0[i]
        assert 0.0 <= a1 < 1.0
        assert b0 / (1 - a1) < 1.0  # the DC gain, the largest


def test_anchor_clamps_below_045_fs(lib8):
    r = make(lib8, fs=16000.0, low=2.0, high=0.5)
    assert r.state.high_anchor_hz == pytest.approx(0.45 * 16000.0)
    got, _ = expected_t60(r.state, 0.45 * 16000.0, 16000.0)
    assert got == pytest.approx(0.5, rel=2e-3)


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
    """Hadamard against Householder on the model, same lengths and filters: the echo density at
    50 to 300 ms and when it first reaches 0.9, printed for docs/notes/reverb.md. With the
    Nyquist-anchored filters Hadamard was clearly ahead and this test asserted it; with the
    8 kHz anchor the two are close and mixed, so the claim was withdrawn from the note (not the
    test loosened to pass). What is asserted is what holds for both: both matrices are
    orthogonal, so the loop is lossless before the filters."""
    r = make(lib8, low=2.0, high=1.0)
    rv = r.state
    x = np.zeros(int(0.5 * FS))
    x[0] = 1.0
    for name, m in (("Hadamard", ref.hadamard8()), ("Householder", ref.householder8())):
        assert np.allclose(m @ m.T, np.eye(8))
        hl, _ = ref.reverb(x, np.zeros_like(x), list(rv.len), list(rv.b0), list(rv.a1), 0, m)
        d, hop = ned(hl)
        at = [round(float(d[int(ms * FS / 1000 / hop)]), 2) for ms in (50, 100, 150, 200, 300)]
        first = int(np.argmax(d >= 0.9)) * hop / FS * 1000 if np.any(d >= 0.9) else None
        print(f"{name}: density at 50/100/150/200/300 ms {at}; 0.9 first at {first} ms")


def test_left_and_right_are_decorrelated(lib8):
    r = make(lib8)
    hl, hr = impulse_response(lib8, r, 1.0)
    c = np.corrcoef(hl.astype(np.float64), hr.astype(np.float64))[0, 1]
    print(f"left/right correlation of the impulse response: {c:.3f}")
    assert abs(c) < 0.2


@pytest.mark.parametrize("ms,expect_ms", [(25.0, 25.0), (50.0, 50.0), (80.0, 50.0)])
def test_predelay(lib8, ms, expect_ms):
    """Pre-delay up to 50 ms (owner 2026-11-17); longer settings clamp to 50."""
    r = make(lib8, predelay_ms=ms)
    hl, hr = impulse_response(lib8, r, 0.2)
    first = int(np.flatnonzero(np.abs(hl) + np.abs(hr) > 0)[0])
    assert first == round(expect_ms * 0.001 * FS) + r.state.len[0]


def test_deterministic(lib8):
    a = impulse_response(lib8, make(lib8), 0.5)[0]
    b = impulse_response(lib8, make(lib8), 0.5)[0]
    assert a.tobytes() == b.tobytes()
