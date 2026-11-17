"""Exercise EX6: the owner's half-band filter, measured in the C oversampler. These fail until
tools/design/ex6_halfband.txt exists. Run: python -m pytest tests/exercises/test_ex6_halfband.py
"""
import ctypes
import pathlib

import numpy as np
import pytest

import dsplib
import dsplib_b6 as b6

FS = 48000.0
TAPS_FILE = pathlib.Path(dsplib.ROOT) / "tools/design/ex6_halfband.txt"


@pytest.fixture(scope="module")
def taps():
    assert TAPS_FILE.exists(), f"write your taps to {TAPS_FILE}, one per line"
    h = np.loadtxt(TAPS_FILE, dtype=np.float64)
    assert len(h) % 4 == 3, "length must be 4K + 3"
    return h.astype(np.float32)


@pytest.fixture(scope="module")
def lib6(lib):
    return b6.bind(lib)


def up(lib6, h, x):
    st = b6.DspHalfbandUpF32()
    assert lib6.dsp_halfband_up_init(ctypes.byref(st), dsplib.f32(h), len(h)) == 0
    y = np.zeros(2 * len(x), dtype=np.float32)
    lib6.dsp_halfband_up_process(ctypes.byref(st), dsplib.f32(x), dsplib.f32(y), len(x))
    return y


def down(lib6, h, v):
    st = b6.DspHalfbandDownF32()
    assert lib6.dsp_halfband_down_init(ctypes.byref(st), dsplib.f32(h), len(h)) == 0
    y = np.zeros(len(v) // 2, dtype=np.float32)
    lib6.dsp_halfband_down_process(ctypes.byref(st), dsplib.f32(v), dsplib.f32(y), len(y))
    return y


def tone(f, fs, n, amp=0.5):
    return (amp * np.sin(2 * np.pi * f * np.arange(n) / fs)).astype(np.float32)


def level_db(y):
    return 20 * np.log10(np.sqrt(np.mean(y.astype(np.float64) ** 2)) * np.sqrt(2))


def amplitude(y, f, fs):
    """Least-squares amplitude of a sine of known frequency: exact for any length, unlike an
    RMS over a non-integer number of cycles."""
    t = np.arange(len(y)) / fs
    basis = np.stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)], axis=1)
    (a, b), *_ = np.linalg.lstsq(basis, y.astype(np.float64), rcond=None)
    return np.hypot(a, b)


def test_passband_flat_to_18_khz(lib6, taps):
    gains = []
    for f in np.linspace(100.0, 18000.0, 25):
        y = up(lib6, taps, tone(f, FS, 8192))[2000:]
        gains.append(20 * np.log10(amplitude(y, f, 2 * FS) / 0.5))
    assert max(gains) - min(gains) < 0.01


def test_image_rejection(lib6, taps):
    """A tone at f (up to 18 kHz) has its image at 48 - f kHz (30 kHz and above) after
    upsampling: at least 90 dB down."""
    for f in (6000.0, 12000.0, 18000.0):
        y = up(lib6, taps, tone(f, FS, 16384))[4096:].astype(np.float64)
        spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        freqs = np.fft.rfftfreq(len(y), 1 / (2 * FS))
        sig = spec[np.argmin(abs(freqs - f))]
        img = spec[np.argmin(abs(freqs - (FS - f)))]
        assert 20 * np.log10(sig / img) > 90.0, f


def test_alias_rejection_on_the_way_down(lib6, taps):
    """A tone at 30 to 40 kHz at the high rate folds to 8 to 18 kHz: at least 90 dB down."""
    for f in (30000.0, 35000.0, 40000.0):
        y = down(lib6, taps, tone(f, 2 * FS, 32768))[4096:]
        assert level_db(y) - level_db(tone(f, 2 * FS, 1000)) < -90.0, f


def test_round_trip_latency_matches_the_length(lib6, taps):
    n = len(taps)
    x = np.zeros(400, dtype=np.float32)
    x[50] = 1.0
    y = down(lib6, taps, up(lib6, taps, x))
    assert int(np.argmax(np.abs(y))) == 50 + (n - 1) // 2
