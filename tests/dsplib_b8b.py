"""ctypes mirrors and bindings for the batch 8b blocks (delay line, LFO, state-variable filter,
the effects, the effect slot, the reverb). test_abi.py checks every mirror's size against the
compiler's."""
import ctypes

import numpy as np

import dsplib
import dsplib_b6 as b6
from dsplib import _f32_p

c_float, c_int32, c_uint32, c_double, c_size = (ctypes.c_float, ctypes.c_int32, ctypes.c_uint32,
                                                ctypes.c_double, ctypes.c_size_t)
P = ctypes.POINTER


class DspDelaylineF32(ctypes.Structure):
    _fields_ = [("buf", _f32_p), ("len", c_int32), ("write", c_int32)]


class DspDelaylineApF32(ctypes.Structure):
    _fields_ = [("y1", c_float)]


class DspLfoF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("shape", c_int32), ("edge", c_float),
                ("edge_gain", c_float), ("phase", c_uint32), ("inc", c_uint32)]


class DspSvfF32(ctypes.Structure):
    _fields_ = [(n, c_float) for n in ("g", "k", "a1", "a2", "a3", "ic1", "ic2")]


MIRRORS = [DspDelaylineF32, DspDelaylineApF32, DspLfoF32, DspSvfF32]

INTERP_LINEAR, INTERP_LAGRANGE, INTERP_ALLPASS = 0, 1, 2
LFO_SINE, LFO_TRIANGLE, LFO_SQUARE, LFO_RAMP = 0, 1, 2, 3
SVF_LOW, SVF_BAND, SVF_HIGH, SVF_NOTCH = 0, 1, 2, 3


def bind(lib):
    b6.bind(lib)

    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    dl = P(DspDelaylineF32)
    sig("dsp_delayline_f32_init", c_int32, dl, _f32_p, c_int32)
    sig("dsp_delayline_f32_reset", None, dl)
    sig("dsp_delayline_f32_read_linear", c_float, dl, c_float)
    sig("dsp_delayline_f32_read_lagrange", c_float, dl, c_float)
    sig("dsp_delayline_f32_read_allpass", c_float, dl, P(DspDelaylineApF32), c_float)
    sig("dsp_delayline_f32_process", None, dl, P(DspDelaylineApF32), c_int32, _f32_p, _f32_p,
        _f32_p, c_size)

    lfo = P(DspLfoF32)
    sig("dsp_lfo_f32_init", None, lfo, c_float, c_int32)
    sig("dsp_lfo_f32_set_shape", None, lfo, c_int32)
    sig("dsp_lfo_f32_set_edge", None, lfo, c_float)
    sig("dsp_lfo_f32_set_rate", None, lfo, c_float)
    sig("dsp_lfo_f32_set_tempo", None, lfo, c_float, c_float)
    sig("dsp_lfo_f32_set_phase", None, lfo, c_double)
    sig("dsp_lfo_f32_phase", c_double, lfo)
    sig("dsp_lfo_f32_sync", None, lfo, c_double, c_float, c_float)
    sig("dsp_lfo_f32_value_at", c_float, lfo, c_uint32)
    sig("dsp_lfo_f32_process", None, lfo, _f32_p, c_size)

    svf = P(DspSvfF32)
    sig("dsp_svf_f32_init", None, svf, c_float, c_float, c_float)
    sig("dsp_svf_f32_reset", None, svf)
    sig("dsp_svf_f32_set", None, svf, c_float, c_float, c_float)
    sig("dsp_svf_f32_set_fast", None, svf, c_float, c_float, c_float)
    sig("dsp_svf_fast_g", c_float, c_float, c_float)
    sig("dsp_svf_f32_process", None, svf, c_int32, _f32_p, _f32_p, c_size)
    return lib


class Delayline:
    """A delay line with its memory kept alive."""

    def __init__(self, lib, length):
        self.lib = lib
        self.mem = np.zeros(length, dtype=np.float32)
        self.dl = DspDelaylineF32()
        self.ap = DspDelaylineApF32()
        assert lib.dsp_delayline_f32_init(ctypes.byref(self.dl), dsplib.f32(self.mem), length) == 0

    def process(self, interp, x, delay):
        x = np.ascontiguousarray(x, dtype=np.float32)
        d = np.ascontiguousarray(delay, dtype=np.float32)
        y = np.zeros_like(x)
        self.lib.dsp_delayline_f32_process(ctypes.byref(self.dl), ctypes.byref(self.ap), interp,
                                           dsplib.f32(x), dsplib.f32(d), dsplib.f32(y), len(x))
        return y
