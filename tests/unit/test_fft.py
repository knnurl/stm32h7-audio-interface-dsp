"""dsp_fft: the packed real FFT against numpy in double precision, the inverse, and the layout."""
import numpy as np
import pytest

import dsplib_b9 as b9
from ref import pconv as ref

SIZES = [16, 32, 64, 128, 256, 512, 1024, 2048]


@pytest.fixture(scope="module")
def lib9(lib):
    return b9.bind(lib)


def rel_error(actual, expected):
    expected = np.asarray(expected, dtype=np.float64)
    return float(np.linalg.norm(np.asarray(actual, dtype=np.float64) - expected)
                 / np.linalg.norm(expected))


@pytest.mark.parametrize("n", SIZES)
def test_forward_matches_numpy(lib9, n):
    x = np.random.default_rng(n).uniform(-1.0, 1.0, n).astype(np.float32)
    got = b9.Rfft(lib9, n).forward(x)
    # float32 radix-2: the error grows about as sqrt(log2 n) times the float epsilon (6e-8).
    assert rel_error(got, ref.rfft_packed(x)) < 1e-6


@pytest.mark.parametrize("n", SIZES)
def test_inverse_returns_n_times_the_signal(lib9, n):
    x = np.random.default_rng(100 + n).uniform(-1.0, 1.0, n).astype(np.float32)
    fft = b9.Rfft(lib9, n)
    back = fft.inverse(fft.forward(x)) / n
    assert rel_error(back, x) < 1e-6


@pytest.mark.parametrize("n", [16, 512])
def test_inverse_of_a_given_spectrum_matches_numpy(lib9, n):
    rng = np.random.default_rng(7)
    packed = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    expected = np.fft.irfft(ref.unpack(packed), n) * n
    assert rel_error(b9.Rfft(lib9, n).inverse(packed), expected) < 1e-6


def test_layout_dc_nyquist_and_one_bin(lib9):
    n = 64
    fft = b9.Rfft(lib9, n)
    t = np.arange(n)
    spec = fft.forward((0.5 + 0.25 * (-1.0) ** t + np.cos(2 * np.pi * 5 * t / n))
                       .astype(np.float32))
    assert spec[0] == pytest.approx(0.5 * n, abs=1e-4)   # DC
    assert spec[1] == pytest.approx(0.25 * n, abs=1e-4)  # Nyquist
    assert spec[2 * 5] == pytest.approx(n / 2, abs=1e-4)  # Re X[5]
    others = np.delete(spec[2:], [2 * 5 - 2, 2 * 5 - 1])
    assert np.max(np.abs(others)) < 1e-4


def test_in_place_equals_out_of_place(lib9):
    n = 256
    fft = b9.Rfft(lib9, n)
    x = np.random.default_rng(3).uniform(-1, 1, n).astype(np.float32)
    buf = x.copy()
    lib9.dsp_rfft_f32_forward(fft.state, b9.dsplib.f32(buf), b9.dsplib.f32(buf))
    assert np.array_equal(buf, fft.forward(x))


@pytest.mark.parametrize("n", [0, 8, 24, 4096, -16])
def test_rejects_bad_sizes(lib9, n):
    state = b9.DspRfftF32()
    assert lib9.dsp_rfft_f32_init(state, n) == -1
