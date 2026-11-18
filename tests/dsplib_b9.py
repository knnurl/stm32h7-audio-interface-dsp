"""ctypes mirrors and bindings for batch 9's blocks: the real FFT and the partitioned convolver."""
import ctypes

import numpy as np

import dsplib
from dsplib import _f32_p

c_int32, c_size = ctypes.c_int32, ctypes.c_size_t
P = ctypes.POINTER


class DspRfftF32(ctypes.Structure):
    _fields_ = [("n", c_int32), ("log2_m", c_int32)]


class DspPconvF32(ctypes.Structure):
    _fields_ = [("fft", DspRfftF32), ("block", c_int32), ("parts", c_int32), ("head", c_int32),
                ("fill", c_int32), ("h", _f32_p), ("fdl", _f32_p), ("in_", _f32_p),
                ("work", _f32_p), ("out", _f32_p)]


MIRRORS = [DspRfftF32, DspPconvF32]


def bind(lib):
    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    sig("dsp_rfft_f32_init", c_int32, P(DspRfftF32), c_int32)
    sig("dsp_rfft_f32_forward", None, P(DspRfftF32), _f32_p, _f32_p)
    sig("dsp_rfft_f32_inverse", None, P(DspRfftF32), _f32_p, _f32_p)
    pc = P(DspPconvF32)
    sig("dsp_pconv_f32_mem_needed", c_int32, c_int32, c_int32)
    sig("dsp_pconv_f32_init", c_int32, pc, c_int32, c_int32, _f32_p, c_int32)
    sig("dsp_pconv_f32_set_filter", c_int32, pc, _f32_p, c_int32)
    sig("dsp_pconv_f32_reset", None, pc)
    sig("dsp_pconv_f32_process", None, pc, _f32_p, _f32_p, c_size)
    return lib


class Rfft:
    def __init__(self, lib, n):
        self.lib, self.n = lib, n
        self.state = DspRfftF32()
        assert lib.dsp_rfft_f32_init(ctypes.byref(self.state), n) == 0

    def forward(self, x):
        x = np.ascontiguousarray(x, dtype=np.float32)
        y = np.zeros(self.n, dtype=np.float32)
        self.lib.dsp_rfft_f32_forward(ctypes.byref(self.state), dsplib.f32(x), dsplib.f32(y))
        return y

    def inverse(self, spec):
        spec = np.ascontiguousarray(spec, dtype=np.float32)
        y = np.zeros(self.n, dtype=np.float32)
        self.lib.dsp_rfft_f32_inverse(ctypes.byref(self.state), dsplib.f32(spec), dsplib.f32(y))
        return y


class Pconv:
    """A convolver with its memory kept alive."""

    def __init__(self, lib, block, taps):
        self.lib = lib
        need = lib.dsp_pconv_f32_mem_needed(block, taps)
        assert need > 0
        self.mem = np.zeros(need, dtype=np.float32)
        self.state = DspPconvF32()
        assert lib.dsp_pconv_f32_init(ctypes.byref(self.state), block, taps,
                                      dsplib.f32(self.mem), need) == 0

    def set_filter(self, h):
        self.h = np.ascontiguousarray(h, dtype=np.float32)
        return self.lib.dsp_pconv_f32_set_filter(ctypes.byref(self.state), dsplib.f32(self.h),
                                                 len(self.h))

    def process(self, x, call=16):
        x = np.ascontiguousarray(x, dtype=np.float32)
        y = np.zeros_like(x)
        for i in range(0, len(x), call):
            xi = x[i:i + call].copy()
            yi = np.zeros_like(xi)
            self.lib.dsp_pconv_f32_process(ctypes.byref(self.state), dsplib.f32(xi),
                                           dsplib.f32(yi), len(xi))
            y[i:i + call] = yi
        return y
