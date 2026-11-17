"""The test-signal generators and the checksum. The noise must be bit-exact: the target and the
PC are compared through it."""
import ctypes
import zlib

import numpy as np

import dsplib
from ref import testsig as ref


def test_noise_q31_is_bit_exact(lib):
    noise = dsplib.DspNoise()
    lib.dsp_noise_seed(ctypes.byref(noise), 12345)
    out = np.zeros(2048, dtype=np.int32)
    lib.dsp_noise_q31(ctypes.byref(noise), dsplib.i32(out), len(out))
    assert np.array_equal(out, ref.noise_q31(12345, 2048))


def test_noise_f32_is_bit_exact_for_power_of_two_amplitudes(lib):
    for amplitude in (1.0, 0.5, 0.125):
        noise = dsplib.DspNoise()
        lib.dsp_noise_seed(ctypes.byref(noise), 99)
        out = np.zeros(2048, dtype=np.float32)
        lib.dsp_noise_f32(ctypes.byref(noise), dsplib.f32(out), len(out), amplitude)
        assert out.tobytes() == ref.noise_f32(99, 2048, amplitude).tobytes()
        assert np.max(np.abs(out)) <= amplitude


def test_noise_continues_across_calls(lib):
    noise = dsplib.DspNoise()
    lib.dsp_noise_seed(ctypes.byref(noise), 5)
    a = np.zeros(100, dtype=np.int32)
    b = np.zeros(156, dtype=np.int32)
    lib.dsp_noise_q31(ctypes.byref(noise), dsplib.i32(a), len(a))
    lib.dsp_noise_q31(ctypes.byref(noise), dsplib.i32(b), len(b))
    assert np.array_equal(np.concatenate([a, b]), ref.noise_q31(5, 256))


def test_noise_is_roughly_white(lib):
    noise = dsplib.DspNoise()
    lib.dsp_noise_seed(ctypes.byref(noise), 1)
    out = np.zeros(65536, dtype=np.float32)
    lib.dsp_noise_f32(ctypes.byref(noise), dsplib.f32(out), len(out), 1.0)
    assert abs(float(np.mean(out))) < 0.01
    # Uniform in [-1, 1): variance 1/3.
    assert abs(float(np.var(out)) - 1.0 / 3.0) < 0.01
    lag1 = float(np.corrcoef(out[:-1], out[1:])[0, 1])
    assert abs(lag1) < 0.02


def test_impulse_and_step(lib):
    out = np.ones(16, dtype=np.float32)
    lib.dsp_impulse_f32(dsplib.f32(out), len(out), 3, 0.5)
    expected = np.zeros(16, dtype=np.float32)
    expected[3] = 0.5
    assert np.array_equal(out, expected)
    lib.dsp_step_f32(dsplib.f32(out), len(out), 5, -0.25)
    expected = np.zeros(16, dtype=np.float32)
    expected[5:] = -0.25
    assert np.array_equal(out, expected)


def test_sine(lib):
    out = np.zeros(480, dtype=np.float32)
    lib.dsp_sine_f32(dsplib.f32(out), len(out), 1000.0, 48000.0, 0.5)
    expected = 0.5 * np.sin(2.0 * np.pi * 1000.0 * np.arange(480) / 48000.0)
    # The phase is computed in float32, so the error grows with the index: -90 dBFS over 480.
    dsplib.assert_within_db(out, expected, -90.0)


def test_crc32_matches_zlib(lib):
    data = bytes(range(256)) * 5 + b"dsp"
    buffer = ctypes.create_string_buffer(data, len(data))
    assert lib.dsp_crc32(0, buffer, len(data)) == zlib.crc32(data)
    # Continuing over two pieces gives the same result.
    first = lib.dsp_crc32(0, buffer, 100)
    rest = ctypes.create_string_buffer(data[100:], len(data) - 100)
    assert lib.dsp_crc32(first, rest, len(data) - 100) == zlib.crc32(data)
    assert lib.dsp_crc32(0, buffer, 0) == 0
