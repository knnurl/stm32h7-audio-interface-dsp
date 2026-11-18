"""dsp_pconv: the partitioned convolver against direct convolution in double precision; its
latency of one partition; call sizes; reset; argument checks."""
import numpy as np
import pytest

import dsplib_b9 as b9
from ref import pconv as ref


@pytest.fixture(scope="module")
def lib9(lib):
    return b9.bind(lib)


def room_like(taps, seed=1):
    """Noise under an exponential decay: the shape of a room correction filter's tail."""
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(taps) * np.exp(-np.arange(taps) / (taps / 6.0)) * 0.2).astype(
        np.float32)


def error_vs_peak(actual, expected):
    return float(np.max(np.abs(actual - expected)) / np.max(np.abs(expected)))


@pytest.mark.parametrize("block,taps", [(64, 1000), (256, 4096), (512, 4096), (128, 129)])
def test_matches_direct_convolution(lib9, block, taps):
    h = room_like(taps)
    x = np.random.default_rng(2).uniform(-0.5, 0.5, 6 * block + taps).astype(np.float32)
    conv = b9.Pconv(lib9, block, taps)
    assert conv.set_filter(h) == 0
    y = conv.process(x)
    # float32 with partition sums of up to 16 terms: well under -100 dB of the output's peak.
    assert error_vs_peak(y, ref.delayed_convolution(x, h, block)) < 1e-5


def test_latency_is_one_partition(lib9):
    block = 64
    conv = b9.Pconv(lib9, block, 256)
    conv.set_filter(np.array([0.0, 0.0, 1.0], dtype=np.float32))
    x = np.zeros(4 * block, dtype=np.float32)
    x[0] = 1.0
    y = conv.process(x)
    assert int(np.argmax(np.abs(y))) == block + 2
    assert y[block + 2] == pytest.approx(1.0, abs=1e-6)
    assert np.max(np.abs(np.delete(y, block + 2))) < 1e-6


@pytest.mark.parametrize("call", [1, 7, 16, 300])
def test_call_size_does_not_change_the_output(lib9, call):
    h = room_like(700)
    x = np.random.default_rng(5).uniform(-0.5, 0.5, 2000).astype(np.float32)
    a = b9.Pconv(lib9, 128, 700)
    a.set_filter(h)
    b = b9.Pconv(lib9, 128, 700)
    b.set_filter(h)
    assert np.array_equal(a.process(x, call=128), b.process(x, call=call))


def test_reset_clears_history_and_keeps_the_filter(lib9):
    h = room_like(300)
    x = np.random.default_rng(6).uniform(-0.5, 0.5, 1024).astype(np.float32)
    conv = b9.Pconv(lib9, 64, 300)
    conv.set_filter(h)
    first = conv.process(x)
    lib9.dsp_pconv_f32_reset(conv.state)
    assert np.array_equal(conv.process(x), first)


def test_starts_silent_until_a_filter_is_loaded(lib9):
    conv = b9.Pconv(lib9, 64, 300)
    y = conv.process(np.ones(512, dtype=np.float32))
    assert not np.any(y)


def test_argument_checks(lib9):
    assert lib9.dsp_pconv_f32_mem_needed(48, 100) == 0      # not a power of two
    assert lib9.dsp_pconv_f32_mem_needed(4, 100) == 0       # too small
    assert lib9.dsp_pconv_f32_mem_needed(2048, 100) == 0    # FFT would exceed 2048
    assert lib9.dsp_pconv_f32_mem_needed(256, 0) == 0
    # 4096 taps at B = 256: 16 partitions, N = 512: 2 * 16 * 512 + 2 * 512 + 256.
    assert lib9.dsp_pconv_f32_mem_needed(256, 4096) == 17664
    state = b9.DspPconvF32()
    mem = np.zeros(17663, dtype=np.float32)
    assert lib9.dsp_pconv_f32_init(state, 256, 4096, b9.dsplib.f32(mem), len(mem)) == -1
    conv = b9.Pconv(lib9, 64, 128)
    assert conv.set_filter(np.zeros(129, dtype=np.float32)) == -1
