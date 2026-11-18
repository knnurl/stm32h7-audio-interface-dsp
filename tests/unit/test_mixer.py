"""The monitor mixer (dsp_mixer.h) against tests/ref/mix.py: the pan law, settled mixing, ramps,
mute, unconnected channels and the send bus."""
import math

import numpy as np
import pytest

import dsplib_b8c as b8c
from ref import mix as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8c(lib):
    return b8c.bind(lib)


def noise(seed, n, amp=0.5):
    return (amp * np.random.default_rng(seed).uniform(-1, 1, n)).astype(np.float32)


def test_pan_law(lib8c):
    assert b8c.pan_gains(lib8c, -1.0) == (1.0, 0.0)
    assert b8c.pan_gains(lib8c, 1.0) == (0.0, 1.0)
    left, right = b8c.pan_gains(lib8c, 0.0)
    assert left == right and 20 * math.log10(left) == pytest.approx(-3.0103, abs=1e-4)
    assert b8c.pan_gains(lib8c, -3.0) == (1.0, 0.0)  # clamped
    for p in np.linspace(-1, 1, 41):
        left, right = b8c.pan_gains(lib8c, float(p))
        assert left * left + right * right == pytest.approx(1.0, abs=1e-6)
        assert (left, right) == pytest.approx(ref.pan_gains(float(p)), abs=1e-6)


def test_init_limits(lib8c):
    st = b8c.DspMixerF32()
    import ctypes
    assert lib8c.dsp_mixer_f32_init(ctypes.byref(st), FS, 0, 20.0) == -1
    assert lib8c.dsp_mixer_f32_init(ctypes.byref(st), FS, 9, 20.0) == -1
    assert lib8c.dsp_mixer_f32_init(ctypes.byref(st), FS, 8, 20.0) == 0
    assert st.ramp_samples == 960


SETTINGS = [(0.8, -0.5, 0.5, 0), (0.5, 0.3, 0.25, 0), (1.0, -1.0, 0.1, 0), (1.0, 1.0, 0.1, 0),
            (1.0, 0.0, 0.0, 1), (0.25, 0.9, 0.0, 0)]


def make(lib8c, settings, ramp_ms=20.0):
    m = b8c.Mixer(lib8c, FS, len(settings), ramp_ms)
    for c, s in enumerate(settings):
        m.set(c, *s)
    m.reset()
    return m


def test_settled_mix_matches_reference(lib8c):
    xs = [noise(c, 2000) for c in range(len(SETTINGS))]
    out = make(lib8c, SETTINGS).process(xs)
    expected = ref.mixer(xs, SETTINGS, 960)
    for got, want in zip(out, expected):
        np.testing.assert_allclose(got, want, atol=2e-6)


def test_stereo_source_passes_at_unity_bit_for_bit(lib8c):
    xl, xr = noise(1, 512), noise(2, 512)
    ml, mr, _, _ = make(lib8c, [(1.0, -1.0, 0.0, 0), (1.0, 1.0, 0.0, 0)]).process([xl, xr])
    assert ml.tobytes() == xl.tobytes() and mr.tobytes() == xr.tobytes()


def test_changes_ramp_linearly_and_match_reference(lib8c):
    xs = [noise(c + 10, 3000) for c in range(len(SETTINGS))]
    m = make(lib8c, SETTINGS)
    changes = [(1024, 0, (0.8, 0.8, 0.5, 0)), (1024, 1, (0.5, 0.3, 0.25, 1)),
               (2048, 4, (1.0, 0.0, 0.0, 0))]
    out = [np.zeros(3000, dtype=np.float32) for _ in range(4)]
    bounds = [0, 1024, 2048, 3000]
    for k in range(3):
        for at, ch, s in changes:
            if at == bounds[k]:
                m.set(ch, *s)
        seg = m.process([x[bounds[k]:bounds[k + 1]] for x in xs])
        for o, s in zip(out, seg):
            o[bounds[k]:bounds[k + 1]] = s
    expected = ref.mixer(xs, SETTINGS, 960, changes)
    # A float ramp adds its step 960 times: up to about 4e-6 off the exact line before it lands.
    for got, want in zip(out, expected):
        np.testing.assert_allclose(got, want, atol=1e-5)


def test_ramp_has_no_step_and_reaches_target(lib8c):
    """A constant input shows the gain itself: from 1 to muted over exactly 960 samples, in equal
    steps (the last lands on the target and absorbs the float ramp's drift: within 1 %)."""
    m = make(lib8c, [(1.0, -1.0, 0.0, 0)])
    m.set(0, 1.0, -1.0, 0.0, 1)
    ml, _, _, _ = m.process([np.ones(1200, dtype=np.float32)])
    steps = np.diff(np.concatenate([[1.0], ml.astype(np.float64)]))
    assert np.all(steps[:960] < 0) and np.max(np.abs(steps)) <= 1.01 / 960
    assert np.all(ml[959:] == 0.0)


def test_mute_silences_main_and_send(lib8c):
    x = noise(3, 256)
    out = make(lib8c, [(1.0, 0.0, 1.0, 1)]).process([x])
    assert all(np.all(o == 0.0) for o in out)


def test_send_follows_the_level(lib8c):
    """Post-level send (owner, 2026-11-18): halving the level halves the send, bit for bit
    against the main bus's own halving; level 0 sends nothing."""
    x = noise(6, 256)
    full = make(lib8c, [(1.0, -1.0, 0.5, 0)]).process([x])
    half = make(lib8c, [(0.5, -1.0, 0.5, 0)]).process([x])
    off = make(lib8c, [(0.0, -1.0, 0.5, 0)]).process([x])
    assert half[0].tobytes() == (0.5 * full[0]).astype(np.float32).tobytes()
    assert half[2].tobytes() == (0.5 * full[2]).astype(np.float32).tobytes()
    assert np.all(off[2] == 0.0) and np.all(off[3] == 0.0)


def test_unconnected_channel_and_no_send_bus(lib8c):
    xs = [noise(4, 512), None, noise(5, 512)]
    settings = [(1.0, 0.2, 0.5, 0), (1.0, 0.0, 1.0, 0), (0.5, -0.4, 0.3, 0)]
    with_send = make(lib8c, settings).process(xs)
    without = make(lib8c, settings).process(xs, send=False)
    assert with_send[0].tobytes() == without[0].tobytes()
    assert with_send[1].tobytes() == without[1].tobytes()
    expected = ref.mixer(xs, settings, 960)
    for got, want in zip(with_send, expected):
        np.testing.assert_allclose(got, want, atol=2e-6)


def test_block_size_does_not_change_the_output(lib8c):
    xs = [noise(c + 20, 1500) for c in range(3)]
    settings = SETTINGS[:3]
    a, b = make(lib8c, settings), make(lib8c, settings)
    a.set(0, 0.1, 0.7, 0.9, 0)
    b.set(0, 0.1, 0.7, 0.9, 0)
    out16, out7 = a.process(xs, block=16), b.process(xs, block=7)
    assert all(p.tobytes() == q.tobytes() for p, q in zip(out16, out7))
