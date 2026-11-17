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


class DspRampF32(ctypes.Structure):
    _fields_ = [("cur", c_float), ("target", c_float), ("step", c_float), ("left", c_int32)]


class DspOnePoleF32(ctypes.Structure):
    _fields_ = [("a", c_float), ("z", c_float)]


SUB = 16
PHASER_MAX = 8
OD_TABLE = 37
LINES = 8


class DspFxEchoF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("line", DspDelaylineF32 * 2),
                ("max_delay", c_float), ("delay", c_float), ("delay_target", c_float),
                ("glide_step", c_float), ("glide_left", c_int32), ("feedback", c_float),
                ("ping_pong", c_int32), ("lp", DspOnePoleF32 * 2), ("hp", DspOnePoleF32 * 2),
                ("wet", DspRampF32)]


class DspFxChorusF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("line", DspDelaylineF32 * 2),
                ("lfo", DspLfoF32), ("right_offset", c_uint32), ("amount", DspRampF32)]


class DspFxFlangerF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("line", DspDelaylineF32 * 2),
                ("lfo", DspLfoF32), ("feedback", c_float), ("amount", DspRampF32)]


class DspFxPhaserF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("lfo", DspLfoF32),
                ("stages", c_int32), ("feedback", c_float), ("amount", DspRampF32),
                ("coef", c_float * 2), ("state", (c_float * PHASER_MAX) * 2),
                ("last", c_float * 2)]


class DspFxTremoloF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("lfo", DspLfoF32),
                ("right_offset", c_uint32), ("depth", DspRampF32)]


class DspFxSweepF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("svf", DspSvfF32 * 2),
                ("q", c_float), ("position", DspRampF32)]


class DspFxOverdriveF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("sat", b6.DspSaturatorF32 * 2),
                ("pre", DspOnePoleF32 * 2), ("dc", DspOnePoleF32 * 2), ("post", DspOnePoleF32 * 2),
                ("asymmetric", c_int32), ("level", c_float), ("drive_db", c_float),
                ("amount", DspRampF32), ("comp", c_float * OD_TABLE), ("buf", c_float * SUB)]


class DspFxCrusherF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("dry", c_float), ("bits", c_float),
                ("rate_hz", c_float), ("dither", c_int32), ("amount", DspRampF32),
                ("phase", c_float), ("held", c_float * 2), ("noise", dsplib.DspNoise),
                ("rnd", c_float * (4 * SUB))]


class DspFxSlotF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("pool", _f32_p), ("pool_len", c_int32),
                ("available", c_int32 * 8), ("selected", c_int32), ("active", c_int32),
                ("on", c_int32), ("trails", c_int32), ("amount", c_float), ("running", c_int32),
                ("dirty_len", c_int32), ("clear_pos", c_int32), ("quiet", c_int32),
                ("fade", c_int32), ("g_in", DspRampF32), ("g_wet", DspRampF32),
                ("g_dry", DspRampF32), ("x_in", (c_float * SUB) * 2), ("wet", (c_float * SUB) * 2),
                ("echo", DspFxEchoF32), ("chorus", DspFxChorusF32), ("flanger", DspFxFlangerF32),
                ("phaser", DspFxPhaserF32), ("tremolo", DspFxTremoloF32), ("sweep", DspFxSweepF32),
                ("overdrive", DspFxOverdriveF32), ("crusher", DspFxCrusherF32)]


class DspReverbF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("line", DspDelaylineF32 * LINES),
                ("pre", DspDelaylineF32 * 2), ("len", c_int32 * LINES), ("b0", c_float * LINES),
                ("a1", c_float * LINES), ("z", c_float * LINES), ("mod", DspLfoF32 * 2),
                ("mod_depth", c_float), ("high_anchor_hz", c_float), ("rt60_low_s", c_float),
                ("rt60_high_s", c_float),
                ("predelay", c_int32), ("max_predelay", c_int32)]


MIRRORS = [DspDelaylineF32, DspDelaylineApF32, DspLfoF32, DspSvfF32, DspRampF32, DspOnePoleF32,
           DspFxEchoF32, DspFxChorusF32, DspFxFlangerF32, DspFxPhaserF32, DspFxTremoloF32,
           DspFxSweepF32, DspFxOverdriveF32, DspFxCrusherF32, DspFxSlotF32, DspReverbF32]

FX_ECHO, FX_CHORUS, FX_FLANGER, FX_PHASER, FX_TREMOLO, FX_SWEEP, FX_OVERDRIVE, FX_CRUSHER = range(8)

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

    stereo = [_f32_p, _f32_p, _f32_p, _f32_p, c_size]
    sig("dsp_onepole_coef", c_float, c_float, c_float)
    e = P(DspFxEchoF32)
    sig("dsp_fx_echo_f32_init", c_int32, e, c_float, _f32_p, c_int32)
    sig("dsp_fx_echo_f32_reset", None, e, c_int32)
    sig("dsp_fx_echo_f32_set_amount", None, e, c_float)
    sig("dsp_fx_echo_f32_set_time_ms", None, e, c_float)
    sig("dsp_fx_echo_f32_set_feedback", None, e, c_float)
    sig("dsp_fx_echo_f32_set_tone", None, e, c_float)
    sig("dsp_fx_echo_f32_set_ping_pong", None, e, c_int32)
    sig("dsp_fx_echo_f32_max_time_ms", c_float, e)
    sig("dsp_fx_echo_f32_process", None, e, *stereo)

    c = P(DspFxChorusF32)
    sig("dsp_fx_chorus_f32_mem_needed", c_int32, c_float)
    sig("dsp_fx_chorus_f32_init", c_int32, c, c_float, _f32_p, c_int32)
    sig("dsp_fx_chorus_f32_reset", None, c, c_int32)
    sig("dsp_fx_chorus_f32_set_amount", None, c, c_float)
    sig("dsp_fx_chorus_f32_set_spread", None, c, c_float)
    sig("dsp_fx_chorus_f32_process", None, c, *stereo)
    f = P(DspFxFlangerF32)
    sig("dsp_fx_flanger_f32_mem_needed", c_int32, c_float)
    sig("dsp_fx_flanger_f32_init", c_int32, f, c_float, _f32_p, c_int32)
    sig("dsp_fx_flanger_f32_reset", None, f, c_int32)
    sig("dsp_fx_flanger_f32_set_amount", None, f, c_float)
    sig("dsp_fx_flanger_f32_set_feedback", None, f, c_float)
    sig("dsp_fx_flanger_f32_process", None, f, *stereo)
    ph = P(DspFxPhaserF32)
    sig("dsp_fx_phaser_f32_init", None, ph, c_float)
    sig("dsp_fx_phaser_f32_reset", None, ph)
    sig("dsp_fx_phaser_f32_set_amount", None, ph, c_float)
    sig("dsp_fx_phaser_f32_set_stages", None, ph, c_int32)
    sig("dsp_fx_phaser_f32_set_feedback", None, ph, c_float)
    sig("dsp_fx_phaser_coef", c_float, c_float, c_float)
    sig("dsp_fx_phaser_f32_process", None, ph, *stereo)

    t = P(DspFxTremoloF32)
    sig("dsp_fx_tremolo_f32_init", None, t, c_float)
    sig("dsp_fx_tremolo_f32_reset", None, t)
    sig("dsp_fx_tremolo_f32_set_amount", None, t, c_float)
    sig("dsp_fx_tremolo_f32_set_rate", None, t, c_float)
    sig("dsp_fx_tremolo_f32_set_shape", None, t, c_int32, c_float)
    sig("dsp_fx_tremolo_f32_set_stereo_phase", None, t, c_float)
    sig("dsp_fx_tremolo_f32_sync", None, t, c_double, c_float, c_float)
    sig("dsp_fx_tremolo_f32_process", None, t, *stereo)

    sw = P(DspFxSweepF32)
    sig("dsp_fx_sweep_f32_init", None, sw, c_float)
    sig("dsp_fx_sweep_f32_reset", None, sw)
    sig("dsp_fx_sweep_f32_set_amount", None, sw, c_float)
    sig("dsp_fx_sweep_f32_set_resonance", None, sw, c_float)
    sig("dsp_fx_sweep_map", None, c_float, P(c_int32), P(c_float), P(c_float))
    sig("dsp_fx_sweep_f32_process", None, sw, *stereo)
    od = P(DspFxOverdriveF32)
    sig("dsp_fx_overdrive_f32_init", None, od, c_float)
    sig("dsp_fx_overdrive_f32_reset", None, od)
    sig("dsp_fx_overdrive_f32_set_amount", None, od, c_float)
    sig("dsp_fx_overdrive_f32_set_tone", None, od, c_float)
    sig("dsp_fx_overdrive_f32_set_asymmetric", None, od, c_int32)
    sig("dsp_fx_overdrive_f32_set_level_db", None, od, c_float)
    sig("dsp_fx_overdrive_f32_latency", c_float, od)
    sig("dsp_fx_overdrive_f32_process", None, od, *stereo)
    cr = P(DspFxCrusherF32)
    sig("dsp_fx_crusher_f32_init", None, cr, c_float)
    sig("dsp_fx_crusher_f32_reset", None, cr)
    sig("dsp_fx_crusher_f32_set_amount", None, cr, c_float)
    sig("dsp_fx_crusher_f32_set_bits", None, cr, c_float)
    sig("dsp_fx_crusher_f32_set_rate", None, cr, c_float)
    sig("dsp_fx_crusher_f32_set_dither", None, cr, c_int32)
    sig("dsp_fx_crusher_f32_process", None, cr, *stereo)

    sl = P(DspFxSlotF32)
    sig("dsp_fxslot_f32_init", c_int32, sl, c_float, _f32_p, c_int32)
    sig("dsp_fxslot_f32_reset", None, sl)
    sig("dsp_fxslot_f32_select", None, sl, c_int32)
    sig("dsp_fxslot_f32_set_on", None, sl, c_int32)
    sig("dsp_fxslot_f32_set_trails", None, sl, c_int32)
    sig("dsp_fxslot_f32_set_amount", None, sl, c_float)
    sig("dsp_fxslot_f32_running", c_int32, sl)
    sig("dsp_fxslot_f32_process", None, sl, *stereo)

    rv = P(DspReverbF32)
    sig("dsp_reverb_f32_mem_needed", c_int32, c_float)
    sig("dsp_reverb_f32_init", c_int32, rv, c_float, _f32_p, c_int32)
    sig("dsp_reverb_f32_reset", None, rv, c_int32)
    sig("dsp_reverb_f32_set_decay", None, rv, c_float, c_float)
    sig("dsp_reverb_f32_set_predelay_ms", None, rv, c_float)
    sig("dsp_reverb_f32_process", None, rv, *stereo)
    return lib


def run_stereo(fn, state, left, right=None, block=16):
    """Runs a stereo process function in blocks, as the audio interrupt will."""
    left = np.ascontiguousarray(left, dtype=np.float32)
    right = left.copy() if right is None else np.ascontiguousarray(right, dtype=np.float32)
    out_l, out_r = np.zeros_like(left), np.zeros_like(right)
    for i in range(0, len(left), block):
        l, r = left[i:i + block].copy(), right[i:i + block].copy()
        ol, orr = np.zeros_like(l), np.zeros_like(r)
        fn(ctypes.byref(state), dsplib.f32(l), dsplib.f32(r), dsplib.f32(ol), dsplib.f32(orr),
           len(l))
        out_l[i:i + block], out_r[i:i + block] = ol, orr
    return out_l, out_r


class WithMemory:
    """A block's state together with the float memory it was given, kept alive."""

    def __init__(self, state, mem):
        self.state = state
        self.mem = mem


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
