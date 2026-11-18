"""The headphone crossfeed (dsp_crossfeed.h) against tests/ref/mix.py: pass-through when off,
the processing, the response it promises for hard-panned and centred sources, the delay, and its
ramps."""
import ctypes

import numpy as np
import pytest

import dsplib_b8c as b8c
from ref import mix as ref

G = float(b8c.CROSSFEED_MAX_GAIN)


@pytest.fixture(scope="module")
def lib8c(lib):
    return b8c.bind(lib)


def noise(seed, n, amp=0.5):
    return (amp * np.random.default_rng(seed).uniform(-1, 1, n)).astype(np.float32)


def sine(f, fs, n, amp=0.5):
    return (amp * np.sin(2 * np.pi * f * np.arange(n) / fs)).astype(np.float32)


def amplitude(y, f, fs):
    t = np.arange(len(y)) / fs
    basis = np.stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)], axis=1)
    (a, b), *_ = np.linalg.lstsq(basis, y.astype(np.float64), rcond=None)
    return np.hypot(a, b)


def test_amount_zero_is_bit_exact_pass_through(lib8c):
    xl, xr = noise(1, 1000), noise(2, 1000)
    yl, yr, _ = b8c.crossfeed(lib8c, 48000.0, 0.0, xl, xr)
    assert yl.tobytes() == xl.tobytes() and yr.tobytes() == xr.tobytes()


@pytest.mark.parametrize("fs", [44100.0, 48000.0, 96000.0])
@pytest.mark.parametrize("amount, delay_us", [(0.3, 0.0), (1.0, 0.0), (1.0, 300.0)])
def test_matches_reference(lib8c, fs, amount, delay_us):
    xl, xr = noise(3, 4000), noise(4, 4000)
    yl, yr, _ = b8c.crossfeed(lib8c, fs, amount, xl, xr, delay_us=delay_us)
    el, er = ref.crossfeed(xl, xr, fs, amount, delay_us=delay_us)
    np.testing.assert_allclose(yl, el, atol=2e-6)
    np.testing.assert_allclose(yr, er, atol=2e-6)


@pytest.mark.parametrize("fs", [48000.0, 96000.0])
def test_hard_panned_source(lib8c, fs):
    """Left only, full amount: the near ear's lows drop by 1 / (1 + g), its highs stay; the far
    ear gets the lows at g / (1 + g)."""
    n = int(fs)
    for f in (50.0, 10000.0):
        x = sine(f, fs, n)
        yl, yr, _ = b8c.crossfeed(lib8c, fs, 1.0, x, np.zeros(n, dtype=np.float32))
        near, far = (amplitude(y[n // 2:], f, fs) / 0.5 for y in (yl, yr))
        want_near, want_far = (abs(v) for v in ref.crossfeed_response(fs, 1.0, f))
        assert 20 * np.log10(near / want_near) == pytest.approx(0, abs=0.01)
        assert 20 * np.log10(far / want_far) == pytest.approx(0, abs=0.01)
        if f == 50.0:
            assert 20 * np.log10(near) == pytest.approx(20 * np.log10(1 / (1 + G)), abs=0.05)
            assert 20 * np.log10(far) == pytest.approx(20 * np.log10(G / (1 + G)), abs=0.05)
            assert 20 * np.log10(far / near) == pytest.approx(-4.5, abs=0.1)
        else:
            assert 20 * np.log10(near) == pytest.approx(0, abs=0.2)
            assert 20 * np.log10(far) < -25


@pytest.mark.parametrize("fs", [44100.0, 48000.0, 96000.0])
def test_centred_source_passes_unchanged(lib8c, fs):
    """Mono in, full amount, no explicit delay: the output is the input to float rounding."""
    x = noise(8, 4000)
    yl, yr, _ = b8c.crossfeed(lib8c, fs, 1.0, x, x)
    np.testing.assert_allclose(yl, x, atol=1e-6)
    np.testing.assert_allclose(yr, x, atol=1e-6)


@pytest.mark.parametrize("delay_us, dip_db, at_hz", [(100.0, -1.41, 1685), (300.0, -3.53, 886)])
def test_explicit_delay_dips_a_centred_source(lib8c, delay_us, dip_db, at_hz):
    """Why the default delay is 0 (dsp_crossfeed.h): at 48 kHz and full amount, a centred source
    dips by these amounts. Checked in the reference response and in the C output at the dip."""
    fs = 48000.0
    f = np.geomspace(20, 20000, 2000)
    near, far = ref.crossfeed_response(fs, 1.0, f, delay_us=delay_us)
    mono_db = 20 * np.log10(np.abs(near + far))
    assert mono_db.min() == pytest.approx(dip_db, abs=0.01)
    assert f[np.argmin(mono_db)] == pytest.approx(at_hz, rel=0.01)
    n = int(fs)
    x = sine(at_hz, fs, n)
    yl, _, _ = b8c.crossfeed(lib8c, fs, 1.0, x, x, delay_us=delay_us)
    got = 20 * np.log10(amplitude(yl[n // 2:], at_hz, fs) / 0.5)
    assert got == pytest.approx(dip_db, abs=0.02)


def test_far_ear_delay(lib8c):
    """The low-pass's group delay at DC, a / (1 - a) samples, is about 0.22 ms; an explicit delay
    adds whole samples, and the far ear stays silent until then."""
    from ref.fx import onepole_coef
    for fs in (48000.0, 96000.0):
        a = onepole_coef(fs, 700.0)
        assert a / (1 - a) / fs * 1e3 == pytest.approx(0.22, abs=0.01)
    n = 64
    x = np.zeros(n, dtype=np.float32)
    x[0] = 1.0
    _, yr, st = b8c.crossfeed(lib8c, 48000.0, 1.0, x, np.zeros(n, dtype=np.float32))
    assert st.delay == 0 and yr[0] > 0.0
    for fs, d in ((48000.0, 14), (96000.0, 29)):
        _, yr, st = b8c.crossfeed(lib8c, fs, 1.0, x, np.zeros(n, dtype=np.float32),
                                  delay_us=300.0)
        assert st.delay == d
        assert np.all(yr[:d] == 0.0) and yr[d] > 0.0
    _, _, st = b8c.crossfeed(lib8c, 48000.0, 1.0, x, x, delay_us=1e6)
    assert st.delay == b8c.XF_RING - 1


def test_amount_changes_ramp_and_return_to_exact_bypass(lib8c):
    fs = 48000.0
    x = noise(5, 3000)
    st = b8c.DspCrossfeedF32()
    lib8c.dsp_crossfeed_f32_init(ctypes.byref(st), fs, 10.0)
    lib8c.dsp_crossfeed_f32_set_amount(ctypes.byref(st), 1.0)  # ramps from 0 over 480
    import dsplib_b8b as b8
    yl, _ = b8.run_stereo(lib8c.dsp_crossfeed_f32_process, st, x, x)
    assert st.h.cur == pytest.approx(G / (1 + G)) and st.h.left == 0
    lib8c.dsp_crossfeed_f32_set_amount(ctypes.byref(st), 0.0)
    zl, zr = b8.run_stereo(lib8c.dsp_crossfeed_f32_process, st, x, -x)
    assert st.h.cur == 0.0
    # After the 480-sample ramp and the end of the block it finished in, bit-exact again.
    assert zl[496:].tobytes() == x[496:].tobytes()
    assert zr[496:].tobytes() == (-x)[496:].tobytes()


def test_centred_source_stays_exact_while_the_amount_ramps(lib8c):
    """Only h ramps, so a centred source is the input during a ramp too."""
    x = noise(9, 2000)
    st = b8c.DspCrossfeedF32()
    lib8c.dsp_crossfeed_f32_init(ctypes.byref(st), 48000.0, 10.0)
    lib8c.dsp_crossfeed_f32_set_amount(ctypes.byref(st), 1.0)
    import dsplib_b8b as b8
    yl, yr = b8.run_stereo(lib8c.dsp_crossfeed_f32_process, st, x, x)
    np.testing.assert_allclose(yl, x, atol=1e-6)
    np.testing.assert_allclose(yr, x, atol=1e-6)


def test_block_size_does_not_change_the_output(lib8c):
    xl, xr = noise(6, 2000), noise(7, 2000)
    a = b8c.crossfeed(lib8c, 48000.0, 0.7, xl, xr, block=16, settle=False)
    b = b8c.crossfeed(lib8c, 48000.0, 0.7, xl, xr, block=5, settle=False)
    assert a[0].tobytes() == b[0].tobytes() and a[1].tobytes() == b[1].tobytes()
