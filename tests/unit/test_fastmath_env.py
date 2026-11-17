"""dsp_fastmath and dsp_env."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
import dsplib_b6 as b6

FS = 48000.0


@pytest.fixture(scope="module")
def lib6(lib):
    return b6.bind(lib)


def test_log2_accuracy(lib6):
    worst = 0.0
    for x in np.geomspace(1e-20, 1e20, 20001):
        worst = max(worst, abs(lib6.dsp_fast_log2f(float(np.float32(x))) -
                               math.log2(float(np.float32(x)))))
    # Measured 2.25e-5 in float32 (the polynomial's design error in double is 1.6e-5).
    assert worst < 2.5e-5


def test_exp2_accuracy(lib6):
    worst = 0.0
    for x in np.linspace(-100, 100, 20001):
        xf = float(np.float32(x))
        worst = max(worst, abs(lib6.dsp_fast_exp2f(xf) / 2.0 ** xf - 1.0))
    assert worst < 3e-7


def test_db_round_trip_and_continuity(lib6):
    for db in np.linspace(-120, 20, 281):
        assert abs(lib6.dsp_fast_lin_to_db(lib6.dsp_fast_db_to_lin(float(db))) - db) < 2e-4
    # Continuous across octave boundaries: no step at powers of two.
    for k in range(-10, 10):
        x = 2.0 ** k
        below = lib6.dsp_fast_log2f(float(np.nextafter(np.float32(x), np.float32(0))))
        assert abs(lib6.dsp_fast_log2f(x) - below) < 1e-5


def test_domain_edges(lib6):
    floor = lib6.dsp_fast_log2f(1e-30)
    for x in (0.0, -1.0, 1e-40, float("nan")):
        assert lib6.dsp_fast_log2f(x) == floor
    assert lib6.dsp_fast_exp2f(float("nan")) == lib6.dsp_fast_exp2f(-126.0)
    assert math.isfinite(lib6.dsp_fast_exp2f(1000.0))
    assert lib6.dsp_fast_lin_to_db(-0.5) == lib6.dsp_fast_lin_to_db(0.5)


def run_env(lib6, env, x, rms=False):
    y = np.zeros_like(x)
    fn = lib6.dsp_env_rms_process if rms else lib6.dsp_env_peak_process
    fn(ctypes.byref(env), dsplib.f32(x), dsplib.f32(y), len(x))
    return y


def time_to(y, start, target, fraction):
    """Samples from `start` until y has covered `fraction` of the way to `target`."""
    y0 = y[start - 1]
    goal = y0 + fraction * (target - y0)
    seg = y[start:]
    idx = np.argmax(seg >= goal) if target > y0 else np.argmax(seg <= goal)
    return idx + 1


def test_peak_attack_and_release_time_constants(lib6):
    env = b6.DspEnvF32()
    lib6.dsp_env_peak_init(ctypes.byref(env), FS, 5.0, 50.0)
    x = np.concatenate([np.zeros(100), np.ones(4800), np.zeros(9600)]).astype(np.float32)
    y = run_env(lib6, env, x)
    attack = time_to(y, 100, 1.0, 1 - math.exp(-1)) / FS * 1000
    release = time_to(y, 4900, 0.0, 1 - math.exp(-1)) / FS * 1000
    assert abs(attack - 5.0) / 5.0 < 0.05 and abs(release - 50.0) / 50.0 < 0.05


@pytest.mark.parametrize("shape, expected", [("sine", 1 / math.sqrt(2)),
                                             ("triangle", 1 / math.sqrt(3)),
                                             ("square", 1.0)])
def test_rms_of_standard_waveforms(lib6, shape, expected):
    """Phil's Lab #103's checks: a sine reads A/sqrt(2), a triangle A/sqrt(3), a square A."""
    t = np.arange(int(FS)) / FS
    phase = (1000.0 * t) % 1.0
    x = {"sine": np.sin(2 * np.pi * phase),
         "triangle": 4 * np.abs(phase - 0.5) - 1,
         "square": np.where(phase < 0.5, 1.0, -1.0)}[shape].astype(np.float32) * 0.5
    env = b6.DspEnvF32()
    lib6.dsp_env_rms_init(ctypes.byref(env), FS, 50.0)
    y = run_env(lib6, env, x, rms=True)
    tail = y[len(y) // 2:]
    assert abs(np.mean(tail) / (0.5 * expected) - 1) < 0.005
    # The one-pole's ripple at twice the input frequency, against the boxcar's none.
    assert (np.max(tail) - np.min(tail)) / np.mean(tail) < 0.01


def test_silence_gives_zero_not_nan(lib6):
    env = b6.DspEnvF32()
    lib6.dsp_env_rms_init(ctypes.byref(env), FS, 10.0)
    y = run_env(lib6, env, np.zeros(10000, dtype=np.float32), rms=True)
    assert np.all(y == 0.0)


def test_fast_tanh_accuracy_and_shape(lib6):
    """Against float64 tanh on a dense grid: absolute error, odd symmetry, bounded, monotonic."""
    xs = np.concatenate([np.linspace(-10, 10, 200001), [1e-30, -1e-30, 1e-8, 0.0]])
    ys = np.array([lib6.dsp_fast_tanhf(float(np.float32(x))) for x in xs], dtype=np.float64)
    ref = np.tanh(xs.astype(np.float32).astype(np.float64))
    err = np.max(np.abs(ys - ref))
    print(f"fast tanh: worst absolute error {err:.2e}")
    assert err < 3e-7
    assert np.all(np.abs(ys) <= 1.0)
    grid = np.linspace(-10, 10, 200001)
    vals = np.array([lib6.dsp_fast_tanhf(float(x)) for x in grid])
    assert np.all(np.diff(vals) >= 0.0), "monotonic"
    for x in (0.1, 0.7, 2.5, 8.9):
        assert lib6.dsp_fast_tanhf(-x) == -lib6.dsp_fast_tanhf(x)


def test_fast_tanh_edges(lib6):
    assert lib6.dsp_fast_tanhf(9.0) == 1.0 and lib6.dsp_fast_tanhf(-1e30) == -1.0
    assert lib6.dsp_fast_tanhf(float("inf")) == 1.0
    assert lib6.dsp_fast_tanhf(float("nan")) == 0.0
    assert lib6.dsp_fast_tanhf(0.0) == 0.0

