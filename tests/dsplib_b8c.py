"""ctypes mirrors and bindings for the batch 8c blocks (mixer, crossfeed, meters, and the
K-weighting interface of exercise EX8c). test_abi.py checks every mirror's size against the
compiler's."""
import ctypes

import numpy as np

import dsplib
import dsplib_b8b as b8
from dsplib import _f32_p, DspBiquadCoefsF32, DspBiquadCoefsF64, DspBiquadStateF32

c_float, c_int32, c_uint32, c_double, c_size = (ctypes.c_float, ctypes.c_int32, ctypes.c_uint32,
                                                ctypes.c_double, ctypes.c_size_t)
P = ctypes.POINTER

MIXER_MAX = 8
XF_RING = 256
TP_TAPS = 16
METER_BLOCKS = 30
METER_TRUE_PEAK, METER_LOUDNESS = 1, 2
FLOOR_DB = -120.0
CROSSFEED_MAX_GAIN = np.float32(0.596)

# ITU-R BS.1770-4, tables 1 and 2: the 48 kHz K-weighting (b0, b1, b2, a1, a2).
KWEIGHT_48K = [(1.53512485958697, -2.69169618940638, 1.19839281085285, -1.69065929318241,
                0.73248077421585),
               (1.0, -2.0, 1.0, -1.99004745483398, 0.99007225036621)]
IDENTITY = [(1.0, 0.0, 0.0, 0.0, 0.0)] * 2


class DspMixerChannelF32(ctypes.Structure):
    _fields_ = [("level", c_float), ("pan", c_float), ("send", c_float), ("mute", c_int32),
                ("gain", b8.DspRampF32 * 4)]


class DspMixerF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("ramp_samples", c_int32), ("n_channels", c_int32),
                ("ch", DspMixerChannelF32 * MIXER_MAX)]


class DspCrossfeedF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("ramp_samples", c_int32), ("delay", c_int32),
                ("lp", b8.DspOnePoleF32 * 2), ("ring", (c_float * XF_RING) * 2), ("pos", c_int32),
                ("h", b8.DspRampF32)]


class DspMeterF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("channels", c_int32), ("flags", c_int32),
                ("hold_samples", c_int32), ("decay_coef", c_float), ("held", c_float * 2),
                ("hold_left", c_int32 * 2), ("max_peak", c_float * 2),
                ("rms_coef", c_float), ("ms", c_float * 2),
                ("tp_hist", (c_float * (2 * TP_TAPS)) * 2), ("tp_pos", c_int32),
                ("max_tp", c_float * 2),
                ("kweighted", c_int32), ("kw", DspBiquadCoefsF32 * 2),
                ("kw_state", (DspBiquadStateF32 * 2) * 2), ("block_len", c_int32),
                ("block_fill", c_int32), ("block_sum", c_double),
                ("block_power", c_double * METER_BLOCKS), ("block_pos", c_int32),
                ("blocks_done", c_uint32)]


class DspMeterReading(ctypes.Structure):
    _fields_ = [("peak_db", c_float * 2), ("max_peak_db", c_float * 2), ("rms_db", c_float * 2),
                ("true_peak_db", c_float * 2), ("momentary_lufs", c_float),
                ("short_term_lufs", c_float), ("loudness_blocks", c_uint32),
                ("kweighted", c_int32)]


MIRRORS = [DspMixerF32, DspCrossfeedF32, DspMeterF32, DspMeterReading]


def bind(lib):
    b8.bind(lib)

    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    mx = P(DspMixerF32)
    sig("dsp_mixer_pan_gains", None, c_float, P(c_float), P(c_float))
    sig("dsp_mixer_f32_init", c_int32, mx, c_float, c_int32, c_float)
    sig("dsp_mixer_f32_reset", None, mx)
    sig("dsp_mixer_f32_set_channel", None, mx, c_int32, c_float, c_float, c_float, c_int32)
    sig("dsp_mixer_f32_process", None, mx, P(_f32_p), _f32_p, _f32_p, _f32_p, _f32_p, c_size)

    xf = P(DspCrossfeedF32)
    sig("dsp_crossfeed_f32_init", None, xf, c_float, c_float)
    sig("dsp_crossfeed_f32_reset", None, xf)
    sig("dsp_crossfeed_f32_set_amount", None, xf, c_float)
    sig("dsp_crossfeed_f32_set_cutoff", None, xf, c_float)
    sig("dsp_crossfeed_f32_set_delay_us", None, xf, c_float)
    sig("dsp_crossfeed_f32_process", None, xf, _f32_p, _f32_p, _f32_p, _f32_p, c_size)

    m = P(DspMeterF32)
    sig("dsp_meter_f32_init", c_int32, m, c_float, c_int32, c_int32)
    sig("dsp_meter_f32_set_ballistics", None, m, c_float, c_float, c_float)
    sig("dsp_meter_f32_set_kweight", None, m, P(DspBiquadCoefsF32))
    sig("dsp_meter_f32_reset", None, m)
    sig("dsp_meter_f32_process", None, m, _f32_p, _f32_p, c_size)
    sig("dsp_meter_f32_read", None, m, P(DspMeterReading))
    sig("dsp_meter_f32_power", c_double, m, c_int32)

    sig("dsp_kweight_design", c_int32, c_double, P(DspBiquadCoefsF64))
    return lib


def pan_gains(lib, pan):
    left, right = c_float(), c_float()
    lib.dsp_mixer_pan_gains(pan, ctypes.byref(left), ctypes.byref(right))
    return left.value, right.value


class Mixer:
    def __init__(self, lib, fs, n_channels, ramp_ms):
        self.lib, self.n = lib, n_channels
        self.st = DspMixerF32()
        assert lib.dsp_mixer_f32_init(ctypes.byref(self.st), fs, n_channels, ramp_ms) == 0

    def set(self, ch, level, pan, send, mute=0):
        self.lib.dsp_mixer_f32_set_channel(ctypes.byref(self.st), ch, level, pan, send, mute)

    def reset(self):
        self.lib.dsp_mixer_f32_reset(ctypes.byref(self.st))

    def process(self, inputs, block=16, send=True):
        """inputs: a list of n arrays (or None). Returns main L, main R, send L, send R."""
        n = len(next(x for x in inputs if x is not None))
        ins = [None if x is None else np.ascontiguousarray(x, dtype=np.float32) for x in inputs]
        outs = [np.zeros(n, dtype=np.float32) for _ in range(4)]
        for i in range(0, n, block):
            k = min(block, n - i)
            arr = (_f32_p * self.n)()
            for c, x in enumerate(ins):
                arr[c] = (ctypes.cast(None, _f32_p) if x is None else
                          ctypes.cast(x[i:].ctypes.data, _f32_p))
            o = [ctypes.cast(y[i:].ctypes.data, _f32_p) for y in outs]
            if not send:
                o[2] = o[3] = ctypes.cast(None, _f32_p)
            self.lib.dsp_mixer_f32_process(ctypes.byref(self.st), arr, o[0], o[1], o[2], o[3], k)
        return outs


def crossfeed(lib, fs, amount, xl, xr, block=16, ramp_ms=10.0, fc=None, delay_us=None,
              settle=True):
    st = DspCrossfeedF32()
    lib.dsp_crossfeed_f32_init(ctypes.byref(st), fs, ramp_ms)
    if fc is not None:
        lib.dsp_crossfeed_f32_set_cutoff(ctypes.byref(st), fc)
    if delay_us is not None:
        lib.dsp_crossfeed_f32_set_delay_us(ctypes.byref(st), delay_us)
    lib.dsp_crossfeed_f32_set_amount(ctypes.byref(st), amount)
    if settle:
        lib.dsp_crossfeed_f32_reset(ctypes.byref(st))
    yl, yr = b8.run_stereo(lib.dsp_crossfeed_f32_process, st, xl, xr, block)
    return yl, yr, st


def kweight_sections(sections):
    arr = (DspBiquadCoefsF32 * 2)()
    for s, c in enumerate(sections):
        arr[s] = DspBiquadCoefsF32(*[float(v) for v in c])
    return arr


class Meter:
    def __init__(self, lib, fs, channels=2, flags=METER_TRUE_PEAK | METER_LOUDNESS,
                 kweight=None):
        self.lib = lib
        self.st = DspMeterF32()
        assert lib.dsp_meter_f32_init(ctypes.byref(self.st), fs, channels, flags) == 0
        if kweight is not None:
            lib.dsp_meter_f32_set_kweight(ctypes.byref(self.st), kweight_sections(kweight))

    def process(self, xl, xr=None, block=16):
        xl = np.ascontiguousarray(xl, dtype=np.float32)
        xr = xl if xr is None else np.ascontiguousarray(xr, dtype=np.float32)
        for i in range(0, len(xl), block):
            k = min(block, len(xl) - i)
            self.lib.dsp_meter_f32_process(ctypes.byref(self.st), dsplib.f32(xl[i:i + k]),
                                           dsplib.f32(xr[i:i + k]), k)

    def read(self):
        r = DspMeterReading()
        self.lib.dsp_meter_f32_read(ctypes.byref(self.st), ctypes.byref(r))
        return r

    def power(self, n_blocks):
        return self.lib.dsp_meter_f32_power(ctypes.byref(self.st), n_blocks)
