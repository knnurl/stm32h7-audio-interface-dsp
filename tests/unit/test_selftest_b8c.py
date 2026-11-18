"""The batch 8c self-test cases: each is rebuilt here through the same C calls and must match
byte for byte, so the case the target runs is the block the other tests checked."""
import ctypes

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
import dsplib_b8c as b8c
from test_selftest import case_index

FS = 48000.0


@pytest.fixture(scope="module")
def lib8c(lib):
    return b8c.bind(lib)


def case(lib8c, name):
    return dsplib.selftest_run(lib8c, case_index(lib8c, name))


def test_channel_counts(lib8c):
    for name, ch in (("mixer_f32", 8), ("crossfeed_f32", 2), ("meter_f32", 2),
                     ("meter_peak_f32", 2)):
        assert lib8c.dsp_selftest_channels(case_index(lib8c, name)) == ch


def test_mixer_case(lib8c):
    x, y = case(lib8c, "mixer_f32")
    n = len(x) // 8
    pans = [-0.5, 0.3, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0]
    sends = [0.5, 0.25, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0]
    m = b8c.Mixer(lib8c, FS, 8, 20.0)
    for c in range(8):
        m.set(c, 0.8 if c < 2 else 1.0, pans[c], sends[c], int(c in (4, 5)))
    m.reset()
    xs = [x[c * n:(c + 1) * n] for c in range(8)]
    first = m.process([v[:n // 2] for v in xs])
    m.set(0, 0.8, 0.8, 0.5, 0)
    m.set(1, 0.8, 0.3, 0.25, 1)
    second = m.process([v[n // 2:] for v in xs])
    expected = np.zeros(len(x), dtype=np.float32)
    for k in range(4):
        expected[k * n:(k + 1) * n] = np.concatenate([first[k], second[k]])
    assert expected.tobytes() == y.tobytes()


def test_crossfeed_case(lib8c):
    x, y = case(lib8c, "crossfeed_f32")
    half = len(x) // 2
    st = b8c.DspCrossfeedF32()
    lib8c.dsp_crossfeed_f32_init(ctypes.byref(st), FS, 10.0)
    lib8c.dsp_crossfeed_f32_set_amount(ctypes.byref(st), 1.0)
    lib8c.dsp_crossfeed_f32_reset(ctypes.byref(st))
    fn = lib8c.dsp_crossfeed_f32_process
    l1, r1 = b8.run_stereo(fn, st, x[:half // 2], x[half:half + half // 2])
    lib8c.dsp_crossfeed_f32_set_amount(ctypes.byref(st), 0.5)
    l2, r2 = b8.run_stereo(fn, st, x[half // 2:half], x[half + half // 2:])
    assert np.concatenate([l1, l2, r1, r2]).tobytes() == y.tobytes()


@pytest.mark.parametrize("name, flags", [("meter_f32", b8c.METER_TRUE_PEAK | b8c.METER_LOUDNESS),
                                         ("meter_peak_f32", 0)])
def test_meter_cases(lib8c, name, flags):
    x, y = case(lib8c, name)
    half = len(x) // 2
    m = b8c.Meter(lib8c, 4800.0, 2, flags, kweight=b8c.KWEIGHT_48K)
    m.st.hold_samples = 48
    m.st.decay_coef = np.float32(0.99)
    m.st.rms_coef = np.float32(0.999)
    expected = np.zeros(len(x), dtype=np.float32)
    for i in range(0, half, 16):
        m.process(x[i:i + 16], x[half + i:half + i + 16])
        s = m.st
        expected[i:i + 10] = [s.held[0], s.held[1], s.max_peak[0], s.max_peak[1], s.ms[0],
                              s.ms[1], s.max_tp[0], s.max_tp[1], m.power(1), s.blocks_done]
    assert expected.tobytes() == y.tobytes()
    # The case does reach a completed loudness block (480 samples at its nominal 4800 Hz).
    assert m.st.blocks_done == (1 if flags & b8c.METER_LOUDNESS else 0)
