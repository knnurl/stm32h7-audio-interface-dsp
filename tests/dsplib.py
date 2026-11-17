"""The C DSP library, loaded through ctypes.

Used by the pytest suites and by tools/target_test.py, so the host side of every comparison is
the same compiled code. Build it first: `cmake --preset host`, `cmake --build --preset
host-release`.
"""
import ctypes
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent

SELFTEST_FRAMES = 1024
FMT_F32 = 0
FMT_Q31 = 1

_f32_p = ctypes.POINTER(ctypes.c_float)
_i32_p = ctypes.POINTER(ctypes.c_int32)


class DspGainF32(ctypes.Structure):
    _fields_ = [("gain", ctypes.c_float), ("target", ctypes.c_float), ("coef", ctypes.c_float)]


class DspNoise(ctypes.Structure):
    _fields_ = [("state", ctypes.c_uint32)]


class DspDcblockF32(ctypes.Structure):
    _fields_ = [("r", ctypes.c_float), ("x_prev", ctypes.c_float), ("y_prev", ctypes.c_float)]


class DspBiquadCoefsF32(ctypes.Structure):
    _fields_ = [(n, ctypes.c_float) for n in ("b0", "b1", "b2", "a1", "a2")]


class DspBiquadStateF32(ctypes.Structure):
    _fields_ = [("z1", ctypes.c_float), ("z2", ctypes.c_float)]


MAX_SECTIONS = 8


class DspBiquadF32(ctypes.Structure):
    _fields_ = [("n_sections", ctypes.c_size_t),
                ("coefs", DspBiquadCoefsF32 * MAX_SECTIONS),
                ("state", DspBiquadStateF32 * MAX_SECTIONS)]


class DspBiquadCoefsQ31(ctypes.Structure):
    _fields_ = [(n, ctypes.c_int32) for n in ("b0", "b1", "b2", "a1", "a2", "shift")]


class DspBiquadStateQ31(ctypes.Structure):
    _fields_ = [(n, ctypes.c_int32) for n in ("x1", "x2", "y1", "y2", "err")]


class DspBiquadQ31(ctypes.Structure):
    _fields_ = [("n_sections", ctypes.c_size_t), ("error_feedback", ctypes.c_int32),
                ("coefs", DspBiquadCoefsQ31 * MAX_SECTIONS),
                ("state", DspBiquadStateQ31 * MAX_SECTIONS)]


class DspBiquadCoefsF64(ctypes.Structure):
    _fields_ = [(n, ctypes.c_double) for n in ("b0", "b1", "b2", "a1", "a2")]


class DspBiquadStateF64(ctypes.Structure):
    _fields_ = [("z1", ctypes.c_double), ("z2", ctypes.c_double)]


class DspBiquadCoefsD(ctypes.Structure):
    _fields_ = [(n, ctypes.c_double) for n in ("b0", "b1", "b2", "a1", "a2")]

    def as_tuple(self):
        return (self.b0, self.b1, self.b2, self.a1, self.a2)


PEQ_SECTIONS = 5


class DspPeqBand(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int32), ("freq_hz", ctypes.c_float),
                ("gain_db", ctypes.c_float), ("q", ctypes.c_float)]


class DspPeqF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", ctypes.c_float), ("ramp_blocks", ctypes.c_int32),
                ("remaining", ctypes.c_int32),
                ("current", DspBiquadCoefsF64 * PEQ_SECTIONS),
                ("target", DspBiquadCoefsF64 * PEQ_SECTIONS),
                ("step", DspBiquadCoefsF64 * PEQ_SECTIONS),
                ("state", DspBiquadStateF64 * PEQ_SECTIONS)]


class DspToneF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", ctypes.c_float), ("smoothing_ms", ctypes.c_float),
                ("freq_hz", ctypes.c_float * 3), ("target_db", ctypes.c_float * 3),
                ("smoothed_db", ctypes.c_float * 3), ("active", ctypes.c_int32 * 3),
                ("dirty", ctypes.c_int32 * 3), ("coefs", DspBiquadCoefsF64 * 3),
                ("state", (DspBiquadStateF64 * 3) * 2)]


def find_library():
    candidates = [
        ROOT / "build/host/dsp/Release/dsp_host.dll",
        ROOT / "build/host/dsp/dsp_host.dll",
        ROOT / "build/host/dsp/libdsp_host.so",
        ROOT / "build/host/dsp/libdsp_host.dylib",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "The DSP library is not built. Run: cmake --preset host, then "
        "cmake --build --preset host-release"
    )


def load():
    lib = ctypes.CDLL(str(find_library()))
    c_size = ctypes.c_size_t
    c_float = ctypes.c_float

    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    gain_p = ctypes.POINTER(DspGainF32)
    sig("dsp_gain_f32_init", None, gain_p, c_float, c_float)
    sig("dsp_gain_f32_reset", None, gain_p)
    sig("dsp_gain_f32_set_linear", None, gain_p, c_float)
    sig("dsp_gain_f32_set_db", None, gain_p, c_float)
    sig("dsp_gain_f32_process", None, gain_p, _f32_p, _f32_p, c_size)

    noise_p = ctypes.POINTER(DspNoise)
    sig("dsp_noise_seed", None, noise_p, ctypes.c_uint32)
    sig("dsp_noise_q31", None, noise_p, _i32_p, c_size)
    sig("dsp_noise_f32", None, noise_p, _f32_p, c_size, c_float)
    sig("dsp_impulse_f32", None, _f32_p, c_size, c_size, c_float)
    sig("dsp_step_f32", None, _f32_p, c_size, c_size, c_float)
    sig("dsp_sine_f32", None, _f32_p, c_size, c_float, c_float, c_float)

    sig("dsp_crc32", ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, c_size)

    sig("dsp_selftest_count", c_size)
    sig("dsp_selftest_name", ctypes.c_char_p, c_size)
    sig("dsp_selftest_fmt", ctypes.c_int, c_size)
    sig("dsp_selftest_input", None, c_size, ctypes.c_void_p)
    sig("dsp_selftest_run", None, c_size, ctypes.c_void_p, ctypes.c_void_p)

    dc_p = ctypes.POINTER(DspDcblockF32)
    sig("dsp_dcblock_f32_init", None, dc_p, c_float, c_float)
    sig("dsp_dcblock_f32_reset", None, dc_p)
    sig("dsp_dcblock_f32_process", None, dc_p, _f32_p, _f32_p, c_size)
    c_double, c_int32 = ctypes.c_double, ctypes.c_int32
    p = ctypes.POINTER
    sig("dsp_biquad_f32_section", None, p(DspBiquadCoefsF32), p(DspBiquadStateF32), _f32_p,
        _f32_p, c_size)
    sig("dsp_biquad_f64_section", None, p(DspBiquadCoefsF64), p(DspBiquadStateF64), _f32_p,
        _f32_p, c_size)
    sig("dsp_biquad_f32_init", None, p(DspBiquadF32), p(DspBiquadCoefsF32), c_size)
    sig("dsp_biquad_f32_reset", None, p(DspBiquadF32))
    sig("dsp_biquad_f32_process", None, p(DspBiquadF32), _f32_p, _f32_p, c_size)
    sig("dsp_biquad_q31_init", None, p(DspBiquadQ31), p(DspBiquadCoefsQ31), c_size, c_int32)
    sig("dsp_biquad_q31_reset", None, p(DspBiquadQ31))
    sig("dsp_biquad_q31_process", None, p(DspBiquadQ31), _i32_p, _i32_p, c_size)

    cd = p(DspBiquadCoefsD)
    sig("dsp_coef_identity", None, cd)
    for name in ("dsp_coef_peak", "dsp_coef_low_shelf", "dsp_coef_high_shelf"):
        sig(name, None, cd, c_double, c_double, c_double, c_double)
    for name in ("dsp_coef_lowpass", "dsp_coef_highpass", "dsp_coef_notch", "dsp_coef_allpass"):
        sig(name, None, cd, c_double, c_double, c_double)
    for name in ("dsp_coef_lowpass1", "dsp_coef_highpass1"):
        sig(name, None, cd, c_double, c_double)
    sig("dsp_coef_butterworth", c_size, cd, c_size, c_double, c_double, ctypes.c_int,
        ctypes.c_int)
    sig("dsp_coef_magnitude_db", c_double, cd, c_size, c_double, c_double)
    sig("dsp_coef_to_f32", None, cd, p(DspBiquadCoefsF32))
    sig("dsp_coef_to_q31", ctypes.c_int, cd, p(DspBiquadCoefsQ31), p(c_double))

    sig("dsp_peq_f32_init", None, p(DspPeqF32), c_float, c_int32)
    sig("dsp_peq_f32_reset", None, p(DspPeqF32))
    sig("dsp_peq_f32_set_highpass", None, p(DspPeqF32), c_float)
    sig("dsp_peq_f32_set_band", None, p(DspPeqF32), c_int32, p(DspPeqBand))
    sig("dsp_peq_f32_process", None, p(DspPeqF32), _f32_p, _f32_p, c_size)

    sig("dsp_tone_f32_init", None, p(DspToneF32), c_float)
    sig("dsp_tone_f32_set_freqs", None, p(DspToneF32), c_float, c_float, c_float)
    sig("dsp_tone_f32_set_db", None, p(DspToneF32), c_int32, c_float)
    sig("dsp_tone_f32_reset", None, p(DspToneF32))
    sig("dsp_tone_f32_process", None, p(DspToneF32), _f32_p, _f32_p, _f32_p, _f32_p, c_size)
    return lib


def design(lib, name, *args):
    """Calls a dsp_coef_* design function; returns the section as a tuple of 5 floats."""
    out = DspBiquadCoefsD()
    getattr(lib, f"dsp_coef_{name}")(ctypes.byref(out), *args)
    return out.as_tuple()


def coefs_d(section):
    return DspBiquadCoefsD(*[float(v) for v in section])


def f32(array):
    """A pointer to a float32 numpy array's data."""
    assert array.dtype == np.float32 and array.flags["C_CONTIGUOUS"]
    return array.ctypes.data_as(_f32_p)


def i32(array):
    assert array.dtype == np.int32 and array.flags["C_CONTIGUOUS"]
    return array.ctypes.data_as(_i32_p)


def selftest_cases(lib):
    """[(index, name, fmt)] for every self-test case in the library."""
    return [
        (i, lib.dsp_selftest_name(i).decode(), lib.dsp_selftest_fmt(i))
        for i in range(lib.dsp_selftest_count())
    ]


def selftest_run(lib, index):
    """Runs one self-test case. Returns (input, output) as arrays of the case's format."""
    fmt = lib.dsp_selftest_fmt(index)
    dtype = np.float32 if fmt == FMT_F32 else np.int32
    x = np.zeros(SELFTEST_FRAMES, dtype=dtype)
    y = np.zeros(SELFTEST_FRAMES, dtype=dtype)
    lib.dsp_selftest_input(index, x.ctypes.data_as(ctypes.c_void_p))
    lib.dsp_selftest_run(index, x.ctypes.data_as(ctypes.c_void_p),
                         y.ctypes.data_as(ctypes.c_void_p))
    return x, y


def error_db(actual, expected):
    """The largest absolute error, in dB relative to full scale (1.0). -inf when identical."""
    err = float(np.max(np.abs(np.asarray(actual, dtype=np.float64)
                              - np.asarray(expected, dtype=np.float64))))
    return -np.inf if err == 0.0 else 20.0 * np.log10(err)


def assert_within_db(actual, expected, limit_db):
    worst = error_db(actual, expected)
    assert worst <= limit_db, f"error {worst:.1f} dBFS exceeds the limit of {limit_db} dBFS"
