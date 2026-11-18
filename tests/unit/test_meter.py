"""The meters (dsp_meter.h) against tests/ref/meter.py: peak with hold and decay, RMS, true peak,
and the BS.1770 loudness windows, with the published 48 kHz K-weighting injected (the C design of
other rates is the owner's exercise EX8c, tested in tests/exercises)."""
import ctypes

import numpy as np
import pytest

import dsplib
import dsplib_b8c as b8c
from ref import meter as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8c(lib):
    return b8c.bind(lib)


def sine(f, fs, n, amp, phase=0.0):
    return (amp * np.sin(2 * np.pi * f * np.arange(n) / fs + phase)).astype(np.float32)


def noise(seed, n, amp=0.5):
    return (amp * np.random.default_rng(seed).uniform(-1, 1, n)).astype(np.float32)


def bursts(seed, n):
    x = noise(seed, n, 0.9)
    return (x * np.where((np.arange(n) // 3000) % 2 == 0, 1.0, 0.02)).astype(np.float32)


def test_init_limits_and_silence(lib8c):
    st = b8c.DspMeterF32()
    assert lib8c.dsp_meter_f32_init(ctypes.byref(st), FS, 0, 0) == -1
    assert lib8c.dsp_meter_f32_init(ctypes.byref(st), FS, 3, 0) == -1
    m = b8c.Meter(lib8c, FS)
    m.process(np.zeros(9600, dtype=np.float32))
    r = m.read()
    values = [*r.peak_db, *r.max_peak_db, *r.rms_db, *r.true_peak_db, r.momentary_lufs,
              r.short_term_lufs]
    assert all(v == b8c.FLOOR_DB for v in values)
    assert r.loudness_blocks == 2
    assert m.st.block_len == 4800 and m.st.hold_samples == 48000


def test_kweighted_flag_follows_the_design(lib8c):
    d = (dsplib.DspBiquadCoefsF64 * 2)()
    designed = lib8c.dsp_kweight_design(FS, d) == 0
    assert b8c.Meter(lib8c, FS).read().kweighted == int(designed)
    assert b8c.Meter(lib8c, FS, kweight=b8c.KWEIGHT_48K).read().kweighted == 1


def test_peak_hold_and_decay_match_reference(lib8c):
    x = bursts(1, 40000)
    m = b8c.Meter(lib8c, FS, flags=0)
    lib8c.dsp_meter_f32_set_ballistics(ctypes.byref(m.st), 50.0, 200.0, 300.0)
    held = []
    for i in range(0, len(x), 16):
        m.process(x[i:i + 16], x[i:i + 16])
        held.append(m.st.held[0])
    want = ref.held_peak(x, m.st.hold_samples, float(np.float32(m.st.decay_coef)))[15::16]
    np.testing.assert_allclose(held, want, rtol=1e-4, atol=1e-7)
    # The decay is linear in dB at the set rate.
    assert 20 * np.log10(m.st.decay_coef) * FS == pytest.approx(-200.0, rel=1e-4)


def test_max_since_last_read_and_clearing(lib8c):
    m = b8c.Meter(lib8c, FS, flags=0)
    x = np.zeros(1000, dtype=np.float32)
    x[123] = -0.5
    m.process(x)
    r = m.read()
    assert r.max_peak_db[0] == pytest.approx(-6.0206, abs=1e-3)
    assert r.peak_db[0] == pytest.approx(-6.0206, abs=1e-3)  # still holding
    m.process(np.zeros(16, dtype=np.float32))
    assert m.read().max_peak_db[0] == b8c.FLOOR_DB


def test_rms(lib8c):
    n = int(3 * FS)
    x = sine(997.0, FS, n, 1.0)
    m = b8c.Meter(lib8c, FS, flags=0)
    ms = []
    for i in range(0, n, 16):
        m.process(x[i:i + 16], x[i:i + 16])
        ms.append(m.st.ms[0])
    want = ref.mean_square(x, float(np.float32(m.st.rms_coef)))[15::16]
    np.testing.assert_allclose(ms, want, rtol=2e-4, atol=1e-9)
    assert m.read().rms_db[0] == pytest.approx(-3.0103, abs=0.05)


def test_true_peak_catches_the_peak_between_samples(lib8c):
    """A quarter-rate sine at 45 degrees: every sample is at 0.707 of the peak, so the sample peak
    reads -3 dB below it and the true peak within the detector's 0.1 dB at 12 kHz. The first
    reading is dropped: the sine's abrupt start overshoots in the interpolator (0.1 dB here)."""
    x = sine(FS / 4, FS, 4800, 0.5, np.pi / 4)
    m = b8c.Meter(lib8c, FS, flags=b8c.METER_TRUE_PEAK)
    m.process(x[:1600], x[:1600])
    m.read()
    m.process(x[1600:], x[1600:])
    r = m.read()
    assert r.max_peak_db[0] == pytest.approx(20 * np.log10(0.5) - 3.0103, abs=0.01)
    assert 20 * np.log10(0.5) - 0.1 < r.true_peak_db[0] <= 20 * np.log10(0.5) + 0.001


def test_true_peak_matches_reference(lib8c):
    rng = np.random.default_rng(2)
    for trial in range(5):
        x = noise(10 + trial, 3000, 0.8)
        x = np.convolve(x, np.ones(3) / 3, mode="same").astype(np.float32)
        m = b8c.Meter(lib8c, FS, channels=1, flags=b8c.METER_TRUE_PEAK)
        m.process(x)
        assert m.st.max_tp[0] == pytest.approx(ref.true_peak(x), rel=1e-5)
    assert rng is not None


@pytest.mark.parametrize("level_dbfs", [-23.0, -33.0])
def test_ebu_3341_stereo_sine_at_48k(lib8c, level_dbfs):
    """EBU Tech 3341, cases 1 and 2: a 1 kHz sine in both channels at level_dbfs reads
    level_dbfs LUFS, momentary and short-term, within 0.1 LU [Verify the tolerance]."""
    n = int(4 * FS)
    x = sine(1000.0, FS, n, 10 ** (level_dbfs / 20))
    m = b8c.Meter(lib8c, FS, flags=b8c.METER_LOUDNESS, kweight=b8c.KWEIGHT_48K)
    m.process(x, x)
    r = m.read()
    assert r.momentary_lufs == pytest.approx(level_dbfs, abs=0.1)
    assert r.short_term_lufs == pytest.approx(level_dbfs, abs=0.1)
    assert r.loudness_blocks == 40


def test_block_powers_match_reference(lib8c):
    xl, xr = bursts(3, 48000), bursts(4, 48000)
    m = b8c.Meter(lib8c, FS, flags=b8c.METER_LOUDNESS, kweight=b8c.KWEIGHT_48K)
    m.process(xl, xr)
    want = ref.block_powers([xl, xr], b8c.KWEIGHT_48K, 4800)
    got = [m.st.block_power[i] for i in range(10)]
    np.testing.assert_allclose(got, want, rtol=1e-4)


@pytest.mark.parametrize("fs, block_len", [(44100.0, 4410), (48000.0, 4800), (88200.0, 8820),
                                           (96000.0, 9600)])
def test_windows_at_every_rate(lib8c, fs, block_len):
    """Unweighted (pass-through sections), so the windows alone are under test: the momentary and
    short-term values after each 0.7 s of bursts and silence, against the reference windows."""
    x = bursts(5, int(5 * fs))
    m = b8c.Meter(lib8c, fs, flags=b8c.METER_LOUDNESS, kweight=b8c.IDENTITY)
    assert m.st.block_len == block_len
    step = int(0.7 * fs)
    for end in range(step, len(x), step):
        m.process(x[end - step:end], x[end - step:end])
        powers = ref.block_powers([x[:end], x[:end]], b8c.IDENTITY, block_len)
        r = m.read()
        assert r.loudness_blocks == len(powers)
        assert r.momentary_lufs == pytest.approx(ref.lufs(ref.windowed(powers, 4)), abs=0.001)
        assert r.short_term_lufs == pytest.approx(ref.lufs(ref.windowed(powers, 30)), abs=0.001)


def test_mono_meter_counts_one_channel(lib8c):
    x = sine(1000.0, FS, int(4 * FS), 10 ** (-23 / 20))
    m = b8c.Meter(lib8c, FS, channels=1, flags=b8c.METER_LOUDNESS, kweight=b8c.KWEIGHT_48K)
    m.process(x)
    r = m.read()
    assert r.momentary_lufs == pytest.approx(-23.0 - 3.0103, abs=0.1)
    assert r.peak_db[1] == b8c.FLOOR_DB


def test_block_size_does_not_change_the_state(lib8c):
    xl, xr = bursts(6, 20000), bursts(7, 20000)
    a = b8c.Meter(lib8c, FS, kweight=b8c.KWEIGHT_48K)
    b = b8c.Meter(lib8c, FS, kweight=b8c.KWEIGHT_48K)
    a.process(xl, xr, block=16)
    b.process(xl, xr, block=5)
    assert bytes(a.st) == bytes(b.st)
