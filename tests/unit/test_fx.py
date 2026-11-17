"""The effects: each against its float64 model, plus the properties its header promises."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
from ref import fx as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def settle(ramp, value):
    """Puts a parameter ramp at its value at once (the C setters ramp over 10 ms)."""
    ramp.cur = ramp.target = value
    ramp.step = 0.0
    ramp.left = 0


def noise(n, amp=0.5, seed=1):
    return np.random.default_rng(seed).uniform(-amp, amp, n).astype(np.float32)


def amplitude(y, f, start=0):
    y = np.asarray(y[start:], dtype=np.float64)
    t = np.arange(start, start + len(y)) / FS
    basis = np.stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)], axis=1)
    (a, b), *_ = np.linalg.lstsq(basis, y, rcond=None)
    return math.hypot(a, b)


# ---- Echo --------------------------------------------------------------------------------------

def make_echo(lib8, mem_len=2 * 12000):
    fx = b8.DspFxEchoF32()
    mem = np.zeros(mem_len, dtype=np.float32)
    rc = lib8.dsp_fx_echo_f32_init(ctypes.byref(fx), FS, dsplib.f32(mem), mem_len)
    return b8.WithMemory(fx, mem), rc


@pytest.mark.parametrize("ping_pong", [0, 1])
def test_echo_matches_the_model(lib8, ping_pong):
    e, rc = make_echo(lib8)
    assert rc == 0
    fx = e.state
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(fx), 100.0)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(fx), 0.6)
    lib8.dsp_fx_echo_f32_set_tone(ctypes.byref(fx), 0.5)
    lib8.dsp_fx_echo_f32_set_ping_pong(ctypes.byref(fx), ping_pong)
    lib8.dsp_fx_echo_f32_reset(ctypes.byref(fx), 1)
    settle(fx.wet, 0.8)
    assert fx.delay == 4799.0
    xl, xr = noise(20000, seed=2), noise(20000, seed=3)
    yl, yr = b8.run_stereo(lib8.dsp_fx_echo_f32_process, fx, xl, xr)
    # 16-bit lines since 2026-11-17: the float32 model with the same quantiser, bit for bit.
    el, er = ref.echo16(xl, xr, 4799, fx.feedback, fx.lp[0].a, fx.hp[0].a, 0.8, bool(ping_pong))
    assert yl.tobytes() == el.tobytes() and yr.tobytes() == er.tobytes()


def test_echo_setters(lib8):
    e, _ = make_echo(lib8)
    fx = e.state
    assert fx.lp[0].a == pytest.approx(ref.onepole_coef(FS, 1500 * 12 ** 0.7), rel=1e-6)
    assert fx.hp[0].a == pytest.approx(ref.onepole_coef(FS, 80.0), rel=1e-6)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(fx), 1.5)
    assert fx.feedback == pytest.approx(0.95)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(fx), math.nan)
    assert fx.feedback == 0.0
    # 24000 floats hold two lines of 24000 int16 samples: the longest time is 23997 samples.
    assert lib8.dsp_fx_echo_f32_max_time_ms(ctypes.byref(fx)) == pytest.approx(23997 / 48, rel=1e-6)
    assert lib8.dsp_fx_echo_f32_mem_needed(FS, 0.75) == 36004
    assert lib8.dsp_fx_echo_f32_mem_needed(96000.0, 0.75) == 36004  # the core runs at 48 kHz
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(fx), 10000.0)
    assert fx.delay_target == fx.max_delay
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(fx), 100.01)  # rounds to whole samples
    assert fx.delay_target == 4799.0
    _, rc = make_echo(lib8, 400)  # 400 int16 per line: under 10 ms
    assert rc == -1


def test_echo_time_glides_over_50_ms(lib8):
    e, _ = make_echo(lib8)
    fx = e.state
    start = fx.delay
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(fx), 150.0)
    seen = []
    x = np.zeros(16, dtype=np.float32)
    for _ in range(200):
        b8.run_stereo(lib8.dsp_fx_echo_f32_process, fx, x)
        seen.append(fx.delay)
    steps = np.diff([start] + seen)
    assert fx.delay == 150 * 48 - 1  # exact: time x fs / 1000
    # Linear: the same step every block until it arrives, 2400 samples after the change.
    moving = steps[steps != 0]
    assert len(moving) == 2400 // 16 and np.allclose(moving, moving[0], rtol=1e-4)


# ---- Chorus, flanger, phaser --------------------------------------------------------------------

def make_mod(lib8, kind):
    if kind == "phaser":
        fx = b8.DspFxPhaserF32()
        lib8.dsp_fx_phaser_f32_init(ctypes.byref(fx), FS)
        return b8.WithMemory(fx, None)
    cls = b8.DspFxChorusF32 if kind == "chorus" else b8.DspFxFlangerF32
    need = getattr(lib8, f"dsp_fx_{kind}_f32_mem_needed")(FS)
    fx = cls()
    mem = np.zeros(need, dtype=np.float32)
    assert getattr(lib8, f"dsp_fx_{kind}_f32_init")(ctypes.byref(fx), FS, dsplib.f32(mem),
                                                      need) == 0
    assert getattr(lib8, f"dsp_fx_{kind}_f32_init")(ctypes.byref(cls()), FS, dsplib.f32(mem),
                                                      need - 1) == -1
    return b8.WithMemory(fx, mem)


# The chorus and flanger read at float32 positions near 1000 samples, where one ulp is 6.1e-5
# samples: against a float64 model that bounds the error near -90 dBFS for full-scale noise.
POSITION_LIMIT_DB = -85.0


def test_chorus_matches_the_model(lib8):
    m = make_mod(lib8, "chorus")
    fx = m.state
    lib8.dsp_lfo_f32_set_rate(ctypes.byref(fx.lfo), 3.0)
    lib8.dsp_fx_chorus_f32_set_spread(ctypes.byref(fx), 0.6)
    settle(fx.amount, 0.8)
    xl, xr = noise(6000, seed=4), noise(6000, seed=5)
    yl, yr = b8.run_stereo(lib8.dsp_fx_chorus_f32_process, fx, xl, xr)
    el, er = ref.chorus(xl, xr, FS, 0.8, round(3.0 / FS * 2 ** 32), fx.right_offset)
    dsplib.assert_within_db(yl, el, POSITION_LIMIT_DB)
    dsplib.assert_within_db(yr, er, POSITION_LIMIT_DB)


def test_chorus_at_zero_amount_is_silent(lib8):
    m = make_mod(lib8, "chorus")
    settle(m.state.amount, 0.0)
    yl, _ = b8.run_stereo(lib8.dsp_fx_chorus_f32_process, m.state, noise(4800))
    assert not np.any(yl)


def test_flanger_matches_the_model(lib8):
    m = make_mod(lib8, "flanger")
    fx = m.state
    lib8.dsp_lfo_f32_set_rate(ctypes.byref(fx.lfo), 2.0)
    lib8.dsp_fx_flanger_f32_set_feedback(ctypes.byref(fx), -0.7)
    settle(fx.amount, 0.9)
    xl, xr = noise(6000, seed=6), noise(6000, seed=7)
    yl, yr = b8.run_stereo(lib8.dsp_fx_flanger_f32_process, fx, xl, xr)
    el, er = ref.flanger(xl, xr, FS, 0.9, round(2.0 / FS * 2 ** 32), fx.feedback)
    dsplib.assert_within_db(yl, el, POSITION_LIMIT_DB)
    dsplib.assert_within_db(yr, er, POSITION_LIMIT_DB)


def test_flanger_feedback_stays_bounded(lib8):
    m = make_mod(lib8, "flanger")
    fx = m.state
    for fb in (0.9, -0.9, 5.0):
        lib8.dsp_fx_flanger_f32_set_feedback(ctypes.byref(fx), fb)
        yl, _ = b8.run_stereo(lib8.dsp_fx_flanger_f32_process, fx, noise(48000, amp=1.0))
        # With |fb| <= 0.9 the loop gain is at most 0.9: the wet is at most 0.7 / (1 - 0.9).
        assert np.max(np.abs(yl)) < 7.0


@pytest.mark.parametrize("stages", [4, 8])
def test_phaser_matches_the_model(lib8, stages):
    m = make_mod(lib8, "phaser")
    fx = m.state
    lib8.dsp_lfo_f32_set_rate(ctypes.byref(fx.lfo), 1.5)
    lib8.dsp_fx_phaser_f32_set_stages(ctypes.byref(fx), stages)
    lib8.dsp_fx_phaser_f32_set_feedback(ctypes.byref(fx), 0.5)
    settle(fx.amount, 0.7)
    xl, xr = noise(9600, seed=8), noise(9600, seed=9)
    yl, yr = b8.run_stereo(lib8.dsp_fx_phaser_f32_process, fx, xl, xr)
    inc = round(1.5 / FS * 2 ** 32)
    el, er = ref.phaser(xl, xr, FS, 0.7, inc, fx.feedback, stages)
    dsplib.assert_within_db(yl, el, -100.0)
    dsplib.assert_within_db(yr, er, -100.0)


def test_phaser_coefficient_puts_minus_90_degrees_at_fc(lib8):
    """#162: a first-order all-pass with c = (tan(pi fc/fs) - 1) / (tan(pi fc/fs) + 1) shifts
    by -90 degrees at fc. Checked through the Pade tan the phaser uses."""
    for fc in (200.0, 1000.0, 6400.0):
        c = lib8.dsp_fx_phaser_coef(FS, fc)
        z = np.exp(-1j * 2 * np.pi * fc / FS)
        h = (c + z) / (1 + c * z)
        assert abs(h) == pytest.approx(1.0, abs=1e-6)
        assert np.degrees(np.angle(h)) == pytest.approx(-90.0, abs=0.05), fc


def test_phaser_makes_notches(lib8):
    """Rate 0: dry + wet (0.5 each) has notches where the chain reaches -180 degrees."""
    m = make_mod(lib8, "phaser")
    fx = m.state
    lib8.dsp_fx_phaser_f32_set_feedback(ctypes.byref(fx), 0.0)
    lib8.dsp_lfo_f32_set_rate(ctypes.byref(fx.lfo), 0.0)
    settle(fx.amount, 0.5)
    imp = np.zeros(8192, dtype=np.float32)
    imp[0] = 1.0
    wet, _ = b8.run_stereo(lib8.dsp_fx_phaser_f32_process, fx, imp)
    total = 0.5 * imp + wet
    mag = 20 * np.log10(np.abs(np.fft.rfft(total.astype(np.float64))) + 1e-12)
    assert mag.min() < -40.0 and abs(mag[0]) < 0.001  # DC: the chain's phase is 0


# ---- Sweep filter -------------------------------------------------------------------------------

def sweep_map(lib8, p):
    mode, fc, blend = ctypes.c_int32(), ctypes.c_float(), ctypes.c_float()
    lib8.dsp_fx_sweep_map(p, ctypes.byref(mode), ctypes.byref(fc), ctypes.byref(blend))
    return mode.value, fc.value, blend.value


def test_sweep_map(lib8):
    for p in np.linspace(0, 1, 201):
        if min(abs(p - 0.47), abs(p - 0.53)) < 1e-6:
            continue  # float32 and float64 round the boundary differently
        mode, fc, blend = sweep_map(lib8, float(p))
        rmode, rfc, rblend = ref.sweep_map(float(p))
        assert mode == rmode and blend == pytest.approx(rblend, abs=1e-6), p
        if mode >= 0:
            assert fc == pytest.approx(rfc, rel=1e-5), p
    assert sweep_map(lib8, 0.5)[0] == -1 and sweep_map(lib8, 0.471)[0] == -1
    assert sweep_map(lib8, 0.469)[0] == 0 and sweep_map(lib8, 0.531)[0] == 2
    assert sweep_map(lib8, 0.0)[1] == pytest.approx(50.0, rel=1e-5)
    assert sweep_map(lib8, 1.0)[1] == pytest.approx(10000.0, rel=1e-5)
    assert sweep_map(lib8, 0.4699)[2] < 0.002 and sweep_map(lib8, 0.5301)[2] < 0.002


@pytest.mark.parametrize("position", [0.1, 0.35, 0.45, 0.5, 0.55, 0.9])
def test_sweep_matches_the_model(lib8, position):
    fx = b8.DspFxSweepF32()
    lib8.dsp_fx_sweep_f32_init(ctypes.byref(fx), FS)
    lib8.dsp_fx_sweep_f32_set_resonance(ctypes.byref(fx), 2.0)
    settle(fx.position, position)
    x = noise(4800, seed=10)
    yl, _ = b8.run_stereo(lib8.dsp_fx_sweep_f32_process, fx, x)
    dsplib.assert_within_db(yl, ref.sweep(x, FS, position, 2.0), -100.0)


def test_sweep_moves_without_steps(lib8):
    """The knob turned from end to end in 2 s on a 1 kHz sine: no sample-to-sample jump larger
    than the sine's own (2 pi f / fs x 0.5 = 0.065) plus a margin for the resonance."""
    fx = b8.DspFxSweepF32()
    lib8.dsp_fx_sweep_f32_init(ctypes.byref(fx), FS)
    settle(fx.position, 0.0)
    x = (0.5 * np.sin(2 * np.pi * 1000 * np.arange(96000) / FS)).astype(np.float32)
    out = np.zeros_like(x)
    for i in range(0, len(x), 16):
        lib8.dsp_fx_sweep_f32_set_amount(ctypes.byref(fx), i / len(x))
        yl, _ = b8.run_stereo(lib8.dsp_fx_sweep_f32_process, fx, x[i:i + 16])
        out[i:i + 16] = yl
    steps = np.max(np.abs(np.diff(out[4800:].astype(np.float64))))
    print(f"largest step while sweeping: {steps:.4f}")
    assert steps < 0.1


# ---- Overdrive ----------------------------------------------------------------------------------

def make_overdrive(lib8, drive_db, tone=1.0, asymmetric=0):
    fx = b8.DspFxOverdriveF32()
    lib8.dsp_fx_overdrive_f32_init(ctypes.byref(fx), FS)
    lib8.dsp_fx_overdrive_f32_set_tone(ctypes.byref(fx), tone)
    lib8.dsp_fx_overdrive_f32_set_asymmetric(ctypes.byref(fx), asymmetric)
    settle(fx.amount, drive_db / 36.0)
    return fx


def harmonics(y, f0, count=9):
    return np.array([amplitude(y, k * f0) for k in range(1, count + 1)])


@pytest.mark.parametrize("drive_db,asym", [(6.0, 0), (18.0, 0), (30.0, 0), (18.0, 1)])
def test_overdrive_harmonics_match_the_model(lib8, drive_db, asym):
    """A 1 kHz sine at -12 dBFS: the C chain's harmonics (oversampled, so nearly alias-free)
    against the continuous-time model, within 0.2 dB for every harmonic above -60 dB."""
    fx = make_overdrive(lib8, drive_db, 0.8, asym)
    x = (0.25 * np.sin(2 * np.pi * 1000 * np.arange(48000) / FS)).astype(np.float32)
    yl, _ = b8.run_stereo(lib8.dsp_fx_overdrive_f32_process, fx, x)
    got = harmonics(yl[24000:], 1000.0)
    want = ref.overdrive_harmonics(0.25, 1000.0, FS, drive_db, 0.8, asymmetric=bool(asym))
    for k, (g, w) in enumerate(zip(got, want), start=1):
        if 20 * np.log10(w / want[0]) > -60:
            assert 20 * np.log10(g / w) == pytest.approx(0.0, abs=0.2), k
    even = 20 * np.log10(got[1] / got[0])
    print(f"drive {drive_db} asym {asym}: H2 {even:.1f} dB")
    assert (even > -40.0) if asym else (even < -80.0)


def test_overdrive_level_compensation(lib8):
    """A -18 dBFS sine keeps its RMS within 1 dB from 0 to 36 dB of drive (bright tone)."""
    x = (0.12589254 * np.sin(2 * np.pi * 1000 * np.arange(24000) / FS)).astype(np.float32)
    x_rms = np.sqrt(np.mean(x.astype(np.float64) ** 2))
    levels = []
    for drive in (0.0, 9.0, 18.0, 27.0, 36.0):
        fx = make_overdrive(lib8, drive, 1.0)
        yl, _ = b8.run_stereo(lib8.dsp_fx_overdrive_f32_process, fx, x)
        levels.append(20 * np.log10(np.sqrt(np.mean(yl[12000:].astype(np.float64) ** 2)) / x_rms))
    print("level change by drive (dB):", [round(v, 2) for v in levels])
    assert max(abs(v) for v in levels) < 1.0


def test_overdrive_latency(lib8):
    fx = make_overdrive(lib8, 0.0)
    assert lib8.dsp_fx_overdrive_f32_latency(ctypes.byref(fx)) == pytest.approx(41.0)  # 2x


# ---- Bit crusher -------------------------------------------------------------------------------

def make_crusher(lib8, amount, bits=6.0, rate=6000.0):
    fx = b8.DspFxCrusherF32()
    lib8.dsp_fx_crusher_f32_init(ctypes.byref(fx), FS)
    lib8.dsp_fx_crusher_f32_set_bits(ctypes.byref(fx), bits)
    lib8.dsp_fx_crusher_f32_set_rate(ctypes.byref(fx), rate)
    settle(fx.amount, amount)
    return fx


@pytest.mark.parametrize("amount,bits,rate", [(1.0, 4.0, 4000.0), (1.0, 8.0, 48000.0),
                                              (0.5, 6.0, 6000.0), (0.0, 3.0, 1000.0)])
def test_crusher_matches_the_model(lib8, amount, bits, rate):
    fx = make_crusher(lib8, amount, bits, rate)
    x = noise(4800, amp=0.9, seed=11)
    yl, _ = b8.run_stereo(lib8.dsp_fx_crusher_f32_process, fx, x)
    bits_eff = np.float32(16) + np.float32(amount) * (np.float32(bits) - np.float32(16))
    steps = lib8.dsp_fast_exp2f(float(bits_eff - np.float32(1)))
    inc = lib8.dsp_fast_exp2f(float(np.float32(amount) *
                                    np.float32(lib8.dsp_fast_log2f(float(np.float32(rate) /
                                                                         np.float32(FS))))))
    expect = ref.crusher(x, steps, inc)
    assert np.array_equal(yl, expect.astype(np.float32))


def test_crusher_at_zero_amount_is_16_bit(lib8):
    fx = make_crusher(lib8, 0.0)
    x = noise(4800, amp=0.9, seed=12)
    yl, _ = b8.run_stereo(lib8.dsp_fx_crusher_f32_process, fx, x)
    assert np.max(np.abs(yl - x)) <= 0.5 / 32768 + 1e-9


def test_crusher_levels_and_hold(lib8):
    fx = make_crusher(lib8, 1.0, 3.0, 4800.0)  # 3 bits: steps of 1/4; hold 10 samples
    x = noise(4800, amp=1.0, seed=13)
    yl, _ = b8.run_stereo(lib8.dsp_fx_crusher_f32_process, fx, x)
    assert len(np.unique(yl)) <= 9
    runs = np.diff(np.flatnonzero(np.diff(yl) != 0))
    assert np.all(runs % 10 == 0)


def test_crusher_survives_nan(lib8):
    fx = make_crusher(lib8, 1.0)
    x = noise(480)
    x[100] = np.nan
    yl, _ = b8.run_stereo(lib8.dsp_fx_crusher_f32_process, fx, x)
    assert np.all(np.isfinite(yl))
