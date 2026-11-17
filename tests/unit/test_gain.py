"""dsp_gain_f32 against its float64 reference.

Tolerance: -120 dBFS while a ramp is moving. A float32 one-pole stalls short of its target
(3.6e-6 away for 5 ms at 48 kHz, measured), so a ramp followed to its end is held to -100 dBFS,
and a separate test checks that the settled gain is exactly the target."""
import ctypes

import numpy as np

import dsplib
from ref import gain as ref

LIMIT_DB = -120.0
FS = 48000.0


def make(lib, smoothing_ms):
    state = dsplib.DspGainF32()
    lib.dsp_gain_f32_init(ctypes.byref(state), FS, smoothing_ms)
    return state


def run(lib, state, x):
    y = np.zeros_like(x)
    lib.dsp_gain_f32_process(ctypes.byref(state), dsplib.f32(x), dsplib.f32(y), len(x))
    return y


def noise(n, seed=7):
    return np.random.default_rng(seed).uniform(-1.0, 1.0, n).astype(np.float32)


def test_starts_at_unity_and_passes_signal(lib):
    x = noise(256)
    y = run(lib, make(lib, 5.0), x)
    assert np.array_equal(y, x)


def test_ramp_matches_reference(lib):
    """The first 1024 samples of a ramp (4 time constants): still moving."""
    x = noise(1024)
    state = make(lib, 5.0)
    lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.25)
    y = run(lib, state, x)
    expected, _ = ref.process(x, 1.0, 0.25, ref.coef(FS, 5.0))
    dsplib.assert_within_db(y, expected, LIMIT_DB)


def test_ramp_to_its_end_stays_within_the_stall_distance(lib):
    x = noise(4096)
    state = make(lib, 5.0)
    lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.25)
    y = run(lib, state, x)
    expected, _ = ref.process(x, 1.0, 0.25, ref.coef(FS, 5.0))
    dsplib.assert_within_db(y, expected, -100.0)


def test_settled_gain_is_exactly_the_target(lib):
    """Without the snap at the end of a block the gain would stop at 0.250003576."""
    state = make(lib, 5.0)
    lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.25)
    for _ in range(8):
        run(lib, state, np.ones(1024, dtype=np.float32))
    assert state.gain == np.float32(0.25)
    y = run(lib, state, np.ones(16, dtype=np.float32))
    assert np.array_equal(y, np.full(16, 0.25, dtype=np.float32))


def test_coefficient_is_accurate(lib):
    """-expm1 keeps the coefficient to float32 precision even for long time constants."""
    for smoothing_ms in (1.0, 5.0, 50.0, 500.0):
        state = make(lib, smoothing_ms)
        exact = ref.coef(FS, smoothing_ms)
        assert abs(state.coef - exact) / exact < 2e-7


def test_time_constant(lib):
    """After one time constant a step of gain has covered 63.2 % of the distance."""
    tau_samples = int(0.005 * FS)
    x = np.ones(tau_samples, dtype=np.float32)
    state = make(lib, 5.0)
    lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.0)
    y = run(lib, state, x)
    assert abs(y[-1] - np.exp(-1.0)) < 1e-3


def test_set_db(lib):
    state = make(lib, 0.0)
    lib.dsp_gain_f32_set_db(ctypes.byref(state), -6.0)
    y = run(lib, state, np.ones(4, dtype=np.float32))
    dsplib.assert_within_db(y, np.full(4, ref.db_to_linear(-6.0)), LIMIT_DB)


def test_no_smoothing_jumps_at_once(lib):
    state = make(lib, 0.0)
    lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.5)
    y = run(lib, state, np.ones(4, dtype=np.float32))
    assert np.array_equal(y, np.full(4, 0.5, dtype=np.float32))


def test_reset_jumps_to_target(lib):
    state = make(lib, 50.0)
    lib.dsp_gain_f32_set_linear(ctypes.byref(state), 2.0)
    lib.dsp_gain_f32_reset(ctypes.byref(state))
    y = run(lib, state, np.ones(4, dtype=np.float32))
    assert np.array_equal(y, np.full(4, 2.0, dtype=np.float32))


def test_in_place(lib):
    x = noise(512)
    state_a, state_b = make(lib, 5.0), make(lib, 5.0)
    for state in (state_a, state_b):
        lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.1)
    separate = run(lib, state_a, x)
    in_place = x.copy()
    lib.dsp_gain_f32_process(ctypes.byref(state_b), dsplib.f32(in_place), dsplib.f32(in_place),
                             len(in_place))
    assert np.array_equal(in_place, separate)


def test_block_size_does_not_change_the_output(lib):
    x = noise(1024)
    state_a, state_b = make(lib, 5.0), make(lib, 5.0)
    for state in (state_a, state_b):
        lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.3)
    whole = run(lib, state_a, x)
    pieces = np.concatenate([run(lib, state_b, x[i:i + 16].copy()) for i in range(0, 1024, 16)])
    assert np.array_equal(whole, pieces)


def test_deterministic(lib):
    x = noise(1024)
    outputs = []
    for _ in range(2):
        state = make(lib, 5.0)
        lib.dsp_gain_f32_set_linear(ctypes.byref(state), 0.3)
        outputs.append(run(lib, state, x))
    assert outputs[0].tobytes() == outputs[1].tobytes()
