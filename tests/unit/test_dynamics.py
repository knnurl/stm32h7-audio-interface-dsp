"""dsp_comp and dsp_gate."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
import dsplib_b6 as b6
from ref import dynamics as ref

FS = 48000.0
PARAMS = dict(threshold_db=-20.0, ratio=4.0, knee_db=6.0, attack_ms=5.0, release_ms=50.0,
              makeup_db=3.0, sidechain_hpf_hz=0.0)


@pytest.fixture(scope="module")
def lib6(lib):
    return b6.bind(lib)


def make_comp(lib6, **overrides):
    p = dict(PARAMS, **overrides)
    comp = b6.DspCompF32()
    lib6.dsp_comp_f32_init(ctypes.byref(comp), FS, ctypes.byref(b6.DspCompParams(**p)))
    return comp


def run(lib6, fn, state, x, block=16):
    y = np.zeros_like(x)
    for i in range(0, len(x), block):
        xs = x[i:i + block].copy()
        ys = np.zeros_like(xs)
        fn(ctypes.byref(state), dsplib.f32(xs), dsplib.f32(ys), len(xs))
        y[i:i + block] = ys
    return y


def db(v):
    return 20 * np.log10(np.abs(v))


def test_static_curve_at_20_levels(lib6):
    """A steady (DC) input settles onto the static curve, within 0.1 dB (the fast log and exp
    are good to 1e-4 dB)."""
    for level in np.linspace(-60.0, 0.0, 20):
        comp = make_comp(lib6)
        x = np.full(48000, 10 ** (level / 20), dtype=np.float32)
        y = run(lib6, lib6.dsp_comp_f32_process, comp, x)
        expected = ref.static_curve(level, -20.0, 4.0, 6.0) + 3.0
        assert abs(db(y[-1]) - expected) < 0.1, level
        assert abs(lib6.dsp_comp_f32_static_db(ctypes.byref(comp), float(level)) - expected) < 1e-4


def test_knee_edges_and_ratio_one(lib6):
    comp = make_comp(lib6)
    # The knee starts at T - W/2 and ends at T + W/2, continuously.
    for edge in (-23.0, -17.0):
        a = lib6.dsp_comp_f32_static_db(ctypes.byref(comp), edge - 1e-3)
        b = lib6.dsp_comp_f32_static_db(ctypes.byref(comp), edge + 1e-3)
        assert abs(a - b) < 0.01
    # Ratio 1, no makeup: the output is the input, bit for bit (gain is exactly 2^0).
    comp = make_comp(lib6, ratio=1.0, makeup_db=0.0)
    x = (np.random.default_rng(1).uniform(-1, 1, 4800)).astype(np.float32)
    assert run(lib6, lib6.dsp_comp_f32_process, comp, x).tobytes() == x.tobytes()


def test_attack_and_release_time_constants(lib6):
    comp = make_comp(lib6)
    x = np.concatenate([np.full(4800, 1e-3), np.full(9600, 1.0), np.full(19200, 1e-3)])
    x = x.astype(np.float32)
    y = run(lib6, lib6.dsp_comp_f32_process, comp, x)
    reduction = 3.0 - (db(y) - db(x))  # y_L, recovered from the gain.
    full = reduction[4800 + 9599]
    up = np.argmax(reduction[4800:] >= full * (1 - math.exp(-1)))
    down = np.argmax(reduction[4800 + 9600:] <= full * math.exp(-1))
    assert abs(up / FS * 1000 - 5.0) / 5.0 < 0.05
    assert abs(down / FS * 1000 - 50.0) / 50.0 < 0.05


def test_matches_the_float64_reference(lib6):
    rng = np.random.default_rng(2)
    t = np.arange(24000)
    x = (0.6 * np.sin(2 * np.pi * 220 * t / FS) * (0.2 + 0.8 * (t % 6000 < 3000))
         + 0.01 * rng.standard_normal(len(t))).astype(np.float32)
    y = run(lib6, lib6.dsp_comp_f32_process, make_comp(lib6), x)
    expected = ref.compressor(x, FS, -20.0, 4.0, 6.0, 5.0, 50.0, 3.0)
    dsplib.assert_within_db(y, expected, -90.0)


def thd_db(y, f0, fs):
    n = len(y)
    spec = np.abs(np.fft.rfft(y * np.hanning(n)))
    k0 = int(round(f0 * n / fs))
    fund = np.sum(spec[k0 - 3:k0 + 4] ** 2)
    harm = sum(np.sum(spec[k * k0 - 3:k * k0 + 4] ** 2) for k in range(2, 11) if k * k0 < n // 2)
    return 10 * np.log10(harm / fund)


def test_bass_distortion_against_release(lib6):
    """The batch 6 review's design risk, measured: an instantaneous detector lets the gain move
    within each cycle of a 40 Hz tone. Longer release, less distortion. The numbers go into
    docs/notes/dynamics.md; the test holds the trend and a ceiling for the default release."""
    t = np.arange(96000)
    x = (0.5 * np.sin(2 * np.pi * 40 * t / FS)).astype(np.float32)
    results = {}
    for release in (10.0, 50.0, 200.0):
        y = run(lib6, lib6.dsp_comp_f32_process, make_comp(lib6, release_ms=release), x)
        results[release] = thd_db(y[48000:].astype(np.float64), 40.0, FS)
    print(f"THD of a 40 Hz tone, 12 dB over threshold: {results}")
    assert results[10.0] > results[50.0] > results[200.0]
    assert results[50.0] < -30.0


def test_sidechain_highpass_ignores_bass(lib6):
    t = np.arange(48000)
    x = (0.5 * np.sin(2 * np.pi * 40 * t / FS)).astype(np.float32)
    plain = make_comp(lib6)
    filtered = make_comp(lib6, sidechain_hpf_hz=150.0)
    run(lib6, lib6.dsp_comp_f32_process, plain, x)
    run(lib6, lib6.dsp_comp_f32_process, filtered, x)
    assert filtered.reduction_db < plain.reduction_db - 6.0


def test_nan_does_not_poison_the_compressor(lib6):
    comp = make_comp(lib6, sidechain_hpf_hz=100.0)
    x = np.full(4800, 0.5, dtype=np.float32)
    x[100] = np.nan
    run(lib6, lib6.dsp_comp_f32_process, comp, x)
    y = run(lib6, lib6.dsp_comp_f32_process, comp, np.full(4800, 0.5, dtype=np.float32))
    assert np.all(np.isfinite(y)) and comp.reduction_db > 1.0  # Still compressing.


# ---- Gate --------------------------------------------------------------------------------------

GATE = dict(open_db=-40.0, hysteresis_db=6.0, hold_ms=20.0, attack_ms=0.5, release_ms=20.0,
            range_db=-80.0, detector_release_ms=10.0)


def make_gate(lib6, **overrides):
    gate = b6.DspGateF32()
    lib6.dsp_gate_f32_init(ctypes.byref(gate), FS,
                           ctypes.byref(b6.DspGateParams(**dict(GATE, **overrides))))
    return gate


def sine(level_db, n, f=500.0):
    t = np.arange(n)
    return (10 ** (level_db / 20) * np.sin(2 * np.pi * f * t / FS)).astype(np.float32)


def test_opens_above_and_stays_shut_below(lib6):
    gate = make_gate(lib6)
    y = run(lib6, lib6.dsp_gate_f32_process, gate, sine(-30.0, 9600))
    assert gate.open == 1 and abs(gate.gain - 1.0) < 1e-4
    gate = make_gate(lib6)
    run(lib6, lib6.dsp_gate_f32_process, gate, sine(-50.0, 9600))
    assert gate.open == 0 and gate.transitions == 0 and abs(gate.gain - 1e-4) < 1e-6
    del y


def test_no_chatter_at_the_threshold(lib6):
    """Phil's Lab #58 describes the failure: a signal that "keeps going above and under". A tone
    whose level wanders between -41 and -38 dB opens once and never closes, because the close
    threshold is 6 dB lower."""
    n = 96000
    t = np.arange(n)
    level = -39.5 + 1.5 * np.sin(2 * np.pi * 3.0 * t / FS)
    x = (10 ** (level / 20) * np.sin(2 * np.pi * 500 * t / FS)).astype(np.float32)
    gate = make_gate(lib6)
    run(lib6, lib6.dsp_gate_f32_process, gate, x)
    assert gate.transitions == 1


def test_hold_time(lib6):
    """DC at -30 dBFS, then silence: the detector falls from 10^(-30/20) to the close threshold
    (-46 dB) in 10 ms x ln(10^(16/20)) = 18.4 ms, then the 20 ms hold runs."""
    x = np.concatenate([np.full(4800, 10 ** (-30 / 20)), np.zeros(9600)]).astype(np.float32)
    gate = make_gate(lib6)
    closed_at = None
    for i in range(0, len(x), 1):
        lib6.dsp_gate_f32_process(ctypes.byref(gate), dsplib.f32(x[i:i + 1].copy()),
                                  dsplib.f32(np.zeros(1, dtype=np.float32)), 1)
        if gate.open == 0 and i > 4800:
            closed_at = i - 4800
            break
    expected = (10.0 * math.log(10 ** (16 / 20)) + 20.0) / 1000 * FS
    assert abs(closed_at - expected) <= 3


def test_range_is_the_closed_gain_and_cannot_boost(lib6):
    gate = make_gate(lib6, range_db=-20.0)
    run(lib6, lib6.dsp_gate_f32_process, gate, np.zeros(4800, dtype=np.float32))
    assert abs(gate.gain - 0.1) < 1e-6
    gate = make_gate(lib6, range_db=6.0)
    assert gate.closed_gain == 1.0
