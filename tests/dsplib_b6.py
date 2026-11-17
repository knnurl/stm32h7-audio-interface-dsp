"""ctypes mirrors and bindings for the batch 6 blocks (dynamics, oversampling, saturation,
limiter). Kept apart from dsplib.py so each batch's bindings stay readable. test_abi.py checks
every mirror's size against the compiler's."""
import ctypes

from dsplib import _f32_p, DspBiquadCoefsF32, DspBiquadStateF32

c_float, c_int32, c_uint32, c_double, c_size = (ctypes.c_float, ctypes.c_int32, ctypes.c_uint32,
                                                ctypes.c_double, ctypes.c_size_t)
P = ctypes.POINTER
HB_MAX = 48
OS_BLOCK = 64
LIM_MAX = 480
LIM_WINDOW = LIM_MAX + 3
LIM_DELAY = LIM_MAX + 24


class DspEnvF32(ctypes.Structure):
    _fields_ = [("attack_coef", c_float), ("release_coef", c_float), ("env", c_float)]


class DspCompParams(ctypes.Structure):
    _fields_ = [(n, c_float) for n in ("threshold_db", "ratio", "knee_db", "attack_ms",
                                       "release_ms", "makeup_db", "sidechain_hpf_hz")]


class DspCompF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("params", DspCompParams), ("slope", c_float),
                ("attack_coef", c_float), ("release_coef", c_float), ("reduction_db", c_float),
                ("hpf_on", c_int32), ("hpf", DspBiquadCoefsF32), ("hpf_state", DspBiquadStateF32)]


class DspGateParams(ctypes.Structure):
    _fields_ = [(n, c_float) for n in ("open_db", "hysteresis_db", "hold_ms", "attack_ms",
                                       "release_ms", "range_db", "detector_release_ms")]


class DspGateF32(ctypes.Structure):
    _fields_ = [("params", DspGateParams), ("sample_rate_hz", c_float), ("detector", DspEnvF32),
                ("close_db", c_float), ("open_lin", c_float), ("close_lin", c_float),
                ("hold_samples", c_int32), ("hold_left", c_int32), ("open", c_int32),
                ("transitions", c_uint32), ("gain", c_float), ("closed_gain", c_float),
                ("open_coef", c_float), ("close_coef", c_float)]


class DspHalfbandUpF32(ctypes.Structure):
    _fields_ = [("n_taps", c_int32), ("delay", c_int32), ("symmetric", c_int32),
                ("taps", c_float * HB_MAX),
                ("hist", c_float * (2 * HB_MAX)), ("pos", c_int32)]


class DspHalfbandDownF32(ctypes.Structure):
    _fields_ = [("n_taps", c_int32), ("delay", c_int32), ("symmetric", c_int32),
                ("taps", c_float * HB_MAX),
                ("even", c_float * (2 * HB_MAX)), ("even_pos", c_int32),
                ("odd", c_float * (2 * HB_MAX)), ("odd_pos", c_int32)]


class DspOversampleF32(ctypes.Structure):
    _fields_ = [("factor", c_int32), ("up1", DspHalfbandUpF32), ("up2", DspHalfbandUpF32),
                ("down1", DspHalfbandDownF32), ("down2", DspHalfbandDownF32),
                ("scratch", c_float * (2 * OS_BLOCK))]


class DspSaturatorF32(ctypes.Structure):
    _fields_ = [("mode", c_int32), ("drive", c_float), ("norm", c_float), ("adaa_x", c_double),
                ("adaa_f", c_double), ("os", DspOversampleF32), ("buf", c_float * (4 * OS_BLOCK))]


class DspLimiterF32(ctypes.Structure):
    _fields_ = [("sample_rate_hz", c_float), ("ceiling", c_float), ("release_coef", c_float),
                ("lookahead", c_int32), ("delay_len", c_int32),
                ("detector", DspOversampleF32 * 2), ("tp_buf", c_float * (4 * OS_BLOCK)),
                ("peak", c_float * OS_BLOCK), ("clean", (c_float * OS_BLOCK) * 2),
                ("delay", (c_float * LIM_DELAY) * 2), ("delay_pos", c_int32),
                ("queue_val", c_float * (LIM_WINDOW + 1)),
                ("queue_idx", c_uint32 * (LIM_WINDOW + 1)), ("queue_head", c_int32),
                ("queue_count", c_int32), ("t", c_uint32), ("held", c_float),
                ("box", c_float * LIM_MAX), ("box_pos", c_int32), ("box_sum", c_double),
                ("gain", c_float), ("min_gain", c_float)]


MIRRORS = [DspEnvF32, DspCompF32, DspGateF32, DspHalfbandUpF32, DspHalfbandDownF32,
           DspOversampleF32, DspSaturatorF32, DspLimiterF32]


def bind(lib):
    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    sig("dsp_abi_sizeof", c_size, ctypes.c_char_p)
    sig("dsp_fast_log2f", c_float, c_float)
    sig("dsp_fast_exp2f", c_float, c_float)
    sig("dsp_fast_lin_to_db", c_float, c_float)
    sig("dsp_fast_db_to_lin", c_float, c_float)
    sig("dsp_fast_tanhf", c_float, c_float)

    sig("dsp_env_coef", c_float, c_float, c_float)
    sig("dsp_env_peak_init", None, P(DspEnvF32), c_float, c_float, c_float)
    sig("dsp_env_rms_init", None, P(DspEnvF32), c_float, c_float)
    sig("dsp_env_reset", None, P(DspEnvF32))
    sig("dsp_env_peak_process", None, P(DspEnvF32), _f32_p, _f32_p, c_size)
    sig("dsp_env_rms_process", None, P(DspEnvF32), _f32_p, _f32_p, c_size)

    sig("dsp_comp_f32_init", None, P(DspCompF32), c_float, P(DspCompParams))
    sig("dsp_comp_f32_set_params", None, P(DspCompF32), P(DspCompParams))
    sig("dsp_comp_f32_reset", None, P(DspCompF32))
    sig("dsp_comp_f32_static_db", c_float, P(DspCompF32), c_float)
    sig("dsp_comp_f32_process", None, P(DspCompF32), _f32_p, _f32_p, c_size)

    sig("dsp_gate_f32_init", None, P(DspGateF32), c_float, P(DspGateParams))
    sig("dsp_gate_f32_reset", None, P(DspGateF32))
    sig("dsp_gate_f32_process", None, P(DspGateF32), _f32_p, _f32_p, c_size)

    sig("dsp_halfband_up_init", c_int32, P(DspHalfbandUpF32), _f32_p, c_int32)
    sig("dsp_halfband_down_init", c_int32, P(DspHalfbandDownF32), _f32_p, c_int32)
    sig("dsp_halfband_up_process", None, P(DspHalfbandUpF32), _f32_p, _f32_p, c_size)
    sig("dsp_halfband_down_process", None, P(DspHalfbandDownF32), _f32_p, _f32_p, c_size)
    sig("dsp_halfband_stage1", P(c_float), P(c_int32))
    sig("dsp_halfband_stage2", P(c_float), P(c_int32))
    sig("dsp_oversample_f32_init", None, P(DspOversampleF32), c_int32)
    sig("dsp_oversample_f32_reset", None, P(DspOversampleF32))
    sig("dsp_oversample_f32_up", None, P(DspOversampleF32), _f32_p, _f32_p, c_size)
    sig("dsp_oversample_f32_down", None, P(DspOversampleF32), _f32_p, _f32_p, c_size)
    sig("dsp_oversample_f32_latency", c_float, P(DspOversampleF32))

    sig("dsp_saturator_f32_init", None, P(DspSaturatorF32), c_int32, c_float)
    sig("dsp_saturator_f32_set_drive", None, P(DspSaturatorF32), c_float)
    sig("dsp_saturator_f32_reset", None, P(DspSaturatorF32))
    sig("dsp_saturator_f32_shape", c_float, P(DspSaturatorF32), c_float)
    sig("dsp_saturator_f32_process", None, P(DspSaturatorF32), _f32_p, _f32_p, c_size)
    sig("dsp_saturator_f32_latency", c_float, P(DspSaturatorF32))

    sig("dsp_limiter_f32_init", None, P(DspLimiterF32), c_float, c_float, c_float, c_float)
    sig("dsp_limiter_f32_reset", None, P(DspLimiterF32))
    sig("dsp_limiter_f32_latency", c_int32, P(DspLimiterF32))
    sig("dsp_limiter_f32_take_min_gain", c_float, P(DspLimiterF32))
    sig("dsp_limiter_f32_process", None, P(DspLimiterF32), _f32_p, _f32_p, _f32_p, _f32_p, c_size)
    return lib
