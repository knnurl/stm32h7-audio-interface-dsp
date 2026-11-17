"""The batch 8b self-test cases: each is rebuilt here through the same C calls and must match
byte for byte, so the case the target runs is the block the other tests checked."""
import ctypes

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
from test_selftest import case_index

FS = 48000.0
POOL = 7680


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def case(lib8, name):
    return dsplib.selftest_run(lib8, case_index(lib8, name))


def stereo(fn, state, x):
    half = len(x) // 2
    yl, yr = b8.run_stereo(fn, state, x[:half], x[half:])
    return np.concatenate([yl, yr])


def pool():
    return np.zeros(POOL, dtype=np.float32)


def test_delay_and_svf_cases(lib8):
    x, y = case(lib8, "delay_lagrange_f32")
    t = np.arange(len(x), dtype=np.float32) / np.float32(len(x))
    d = np.where(t < 0.5, np.float32(10) + np.float32(590) * (np.float32(2) * t),
                 np.float32(10) + np.float32(590) * (np.float32(2) - np.float32(2) * t))
    line = b8.Delayline(lib8, 1024)
    assert line.process(b8.INTERP_LAGRANGE, x, d.astype(np.float32)).tobytes() == y.tobytes()

    x, y = case(lib8, "svf_f32")
    svf = b8.DspSvfF32()
    lib8.dsp_svf_f32_init(ctypes.byref(svf), FS, 200.0, 4.0)
    out = np.zeros_like(x)
    for i in range(0, len(x), 16):
        fc = np.float32(200) + np.float32(7800) * np.float32(i) / np.float32(len(x))
        lib8.dsp_svf_f32_set_fast(ctypes.byref(svf), FS, float(fc), 4.0)
        seg = np.ascontiguousarray(x[i:i + 16])
        o = np.zeros_like(seg)
        lib8.dsp_svf_f32_process(ctypes.byref(svf), b8.SVF_LOW, dsplib.f32(seg), dsplib.f32(o), 16)
        out[i:i + 16] = o
    assert out.tobytes() == y.tobytes()


def test_effect_cases(lib8):
    x, y = case(lib8, "fx_echo_f32")
    e, m = b8.DspFxEchoF32(), pool()
    lib8.dsp_fx_echo_f32_init(ctypes.byref(e), FS, dsplib.f32(m), POOL)
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(e), 3.0)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(e), 0.6)
    lib8.dsp_fx_echo_f32_set_ping_pong(ctypes.byref(e), 1)
    lib8.dsp_fx_echo_f32_set_amount(ctypes.byref(e), 1.0)
    lib8.dsp_fx_echo_f32_reset(ctypes.byref(e), 1)
    assert stereo(lib8.dsp_fx_echo_f32_process, e, x).tobytes() == y.tobytes()

    x, y = case(lib8, "fx_echo96_f32")
    e, m = b8.DspFxEchoF32(), pool()
    lib8.dsp_fx_echo_f32_init(ctypes.byref(e), 96000.0, dsplib.f32(m), POOL)
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(e), 3.0)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(e), 0.6)
    lib8.dsp_fx_echo_f32_set_amount(ctypes.byref(e), 1.0)
    lib8.dsp_fx_echo_f32_reset(ctypes.byref(e), 1)
    assert e.half_rate == 1
    assert stereo(lib8.dsp_fx_echo_f32_process, e, x).tobytes() == y.tobytes()

    for name, cls, extra, fs in (("chorus", b8.DspFxChorusF32, None, 16000.0),
                                 ("flanger", b8.DspFxFlangerF32, 0.7, FS)):
        x, y = case(lib8, f"fx_{name}_f32")
        fx, m = cls(), pool()
        getattr(lib8, f"dsp_fx_{name}_f32_init")(ctypes.byref(fx), fs, dsplib.f32(m), POOL)
        lib8.dsp_lfo_f32_set_rate(ctypes.byref(fx.lfo), 20.0)
        if extra is not None:
            lib8.dsp_fx_flanger_f32_set_feedback(ctypes.byref(fx), extra)
        getattr(lib8, f"dsp_fx_{name}_f32_set_amount")(ctypes.byref(fx), 1.0)
        assert stereo(getattr(lib8, f"dsp_fx_{name}_f32_process"), fx, x).tobytes() == \
            y.tobytes(), name

    x, y = case(lib8, "fx_phaser_f32")
    ph = b8.DspFxPhaserF32()
    lib8.dsp_fx_phaser_f32_init(ctypes.byref(ph), FS)
    lib8.dsp_lfo_f32_set_rate(ctypes.byref(ph.lfo), 20.0)
    lib8.dsp_fx_phaser_f32_set_stages(ctypes.byref(ph), 8)
    lib8.dsp_fx_phaser_f32_set_amount(ctypes.byref(ph), 1.0)
    assert stereo(lib8.dsp_fx_phaser_f32_process, ph, x).tobytes() == y.tobytes()

    x, y = case(lib8, "fx_sweep_f32")
    sw = b8.DspFxSweepF32()
    lib8.dsp_fx_sweep_f32_init(ctypes.byref(sw), FS)
    lib8.dsp_fx_sweep_f32_set_resonance(ctypes.byref(sw), 3.0)
    lib8.dsp_fx_sweep_f32_set_amount(ctypes.byref(sw), 0.1)
    assert stereo(lib8.dsp_fx_sweep_f32_process, sw, x).tobytes() == y.tobytes()

    x, y = case(lib8, "fx_overdrive_f32")
    od = b8.DspFxOverdriveF32()
    lib8.dsp_fx_overdrive_f32_init(ctypes.byref(od), FS)
    lib8.dsp_fx_overdrive_f32_set_asymmetric(ctypes.byref(od), 1)
    lib8.dsp_fx_overdrive_f32_set_amount(ctypes.byref(od), 0.8)
    assert stereo(lib8.dsp_fx_overdrive_f32_process, od, x).tobytes() == y.tobytes()

    x, y = case(lib8, "fx_crusher_f32")
    cr = b8.DspFxCrusherF32()
    lib8.dsp_fx_crusher_f32_init(ctypes.byref(cr), FS)
    lib8.dsp_fx_crusher_f32_set_dither(ctypes.byref(cr), 1)
    lib8.dsp_fx_crusher_f32_set_amount(ctypes.byref(cr), 1.0)
    assert stereo(lib8.dsp_fx_crusher_f32_process, cr, x).tobytes() == y.tobytes()


def test_slot_and_reverb_cases(lib8):
    x, y = case(lib8, "fxslot_f32")
    sl, m = b8.DspFxSlotF32(), pool()
    lib8.dsp_fxslot_f32_init(ctypes.byref(sl), FS, dsplib.f32(m), POOL)
    lib8.dsp_fxslot_f32_select(ctypes.byref(sl), b8.FX_PHASER)
    lib8.dsp_fxslot_f32_reset(ctypes.byref(sl))
    sl.dirty_len = 0
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(sl), 1)
    half = len(x) // 2
    a, b = b8.run_stereo(lib8.dsp_fxslot_f32_process, sl, x[:half // 2], x[half:half + half // 2])
    lib8.dsp_fxslot_f32_select(ctypes.byref(sl), b8.FX_FLANGER)
    c, d = b8.run_stereo(lib8.dsp_fxslot_f32_process, sl, x[half // 2:half], x[half + half // 2:])
    assert np.concatenate([a, c, b, d]).tobytes() == y.tobytes()

    x, y = case(lib8, "reverb_f32")
    rv, m = b8.DspReverbF32(), pool()
    assert lib8.dsp_reverb_f32_init(ctypes.byref(rv), 16000.0, dsplib.f32(m), POOL) == 0
    lib8.dsp_reverb_f32_set_decay(ctypes.byref(rv), 0.5, 0.2)
    lib8.dsp_reverb_f32_set_predelay_ms(ctypes.byref(rv), 0.0)
    assert stereo(lib8.dsp_reverb_f32_process, rv, x).tobytes() == y.tobytes()
