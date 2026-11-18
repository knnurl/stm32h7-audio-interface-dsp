"""The self-test cases the firmware also runs. Each case is checked here against its Python
reference, so a target that matches the PC library also matches the reference."""
import ctypes

import numpy as np

import dsplib
from ref import biquad as biquad_ref
from ref import coef
from ref import gain as gain_ref
from ref import testsig as testsig_ref

CASCADE = [coef.highpass(48000.0, 30.0, 0.7071067811865476), coef.peak(48000.0, 1000.0, 1.0, 6.0),
           coef.high_shelf(48000.0, 8000.0, 1.0, -4.0)]


def case_index(lib, name):
    for index, case_name, _ in dsplib.selftest_cases(lib):
        if case_name == name:
            return index
    raise AssertionError(f"no self-test case named {name}")


def test_names_are_unique_and_indices_are_bounded(lib):
    cases = dsplib.selftest_cases(lib)
    names = [name for _, name, _ in cases]
    assert len(names) == len(set(names)) and len(names) >= 2
    assert all(fmt in (dsplib.FMT_F32, dsplib.FMT_Q31) for _, _, fmt in cases)
    assert lib.dsp_selftest_name(len(cases)) is None
    assert lib.dsp_selftest_fmt(len(cases)) == -1


def test_every_case_is_deterministic(lib):
    for index, name, _ in dsplib.selftest_cases(lib):
        _, first = dsplib.selftest_run(lib, index)
        _, second = dsplib.selftest_run(lib, index)
        assert first.tobytes() == second.tobytes(), name
        assert np.any(first != 0), f"{name} produced silence"


def test_gain_f32_case_matches_reference(lib):
    x, y = dsplib.selftest_run(lib, case_index(lib, "gain_f32"))
    assert x.tobytes() == testsig_ref.noise_f32(1, dsplib.SELFTEST_FRAMES, 0.5).tobytes()
    k = gain_ref.coef(48000.0, 5.0)
    half = dsplib.SELFTEST_FRAMES // 2
    first, gain = gain_ref.process(x[:half], 0.0, gain_ref.db_to_linear(-6.0), k)
    second, _ = gain_ref.process(x[half:], gain, 0.25, k)
    dsplib.assert_within_db(y, np.concatenate([first, second]), -120.0)


def test_noise_q31_case_matches_reference(lib):
    _, y = dsplib.selftest_run(lib, case_index(lib, "noise_q31"))
    assert np.array_equal(y, testsig_ref.noise_q31(2, dsplib.SELFTEST_FRAMES))


def test_biquad_case_constants_are_the_designs(lib):
    """The constants in dsp_selftest.c are the float32 roundings and Q31 quantisations of the
    designs; if a design changes, this says so."""
    import re
    import pathlib
    text = (pathlib.Path(dsplib.ROOT) / "dsp/src/dsp_selftest.c").read_text()
    floats = re.findall(r"\{([-0-9.e, f]+)\},", text.split("kCascadeF32")[1].split("};")[0])
    for line, section in zip(floats, CASCADE):
        values = [np.float32(v.strip().rstrip("f")) for v in line.split(",")]
        assert values == list(np.float32(section))
    ints = re.findall(r"\{([-0-9, ]+)\},", text.split("kCascadeQ31")[1].split("};")[0])
    for line, section in zip(ints, CASCADE):
        values = [int(v) for v in line.split(",")]
        q, shift = coef.to_q31(section)
        assert values == q + [shift]


def test_biquad_f32_case_matches_reference(lib):
    x, y = dsplib.selftest_run(lib, case_index(lib, "biquad_f32"))
    expected = biquad_ref.f64_cascade(x, [np.float32(s).astype(np.float64) for s in CASCADE])
    dsplib.assert_within_db(y, expected, -75.0)  # The 30 Hz high-pass: see test_biquad.py.


def test_biquad_q31_cases_are_bit_exact(lib):
    quantised = [coef.to_q31(s) for s in CASCADE]
    for name, ef in (("biquad_q31_round", 0), ("biquad_q31_ef", 1)):
        x, y = dsplib.selftest_run(lib, case_index(lib, name))
        assert np.array_equal(y, biquad_ref.q31_cascade(x, quantised, ef)), name


def test_tone_case_is_the_tone_block(lib):
    x, y = dsplib.selftest_run(lib, case_index(lib, "tone_f32"))
    half = len(x) // 2
    tone = dsplib.DspToneF32()
    lib.dsp_tone_f32_init(ctypes.byref(tone), 48000.0)
    for band, gain in enumerate((6.0, -3.0, 9.0)):
        lib.dsp_tone_f32_set_db(ctypes.byref(tone), band, gain)
    lib.dsp_tone_f32_reset(ctypes.byref(tone))
    out = np.zeros_like(x)
    for i in range(0, half, 16):
        if i == 256:
            lib.dsp_tone_f32_set_db(ctypes.byref(tone), 0, -12.0)
        l_in, r_in = x[i:i + 16].copy(), x[half + i:half + i + 16].copy()
        l_out, r_out = np.zeros_like(l_in), np.zeros_like(r_in)
        lib.dsp_tone_f32_process(ctypes.byref(tone), dsplib.f32(l_in), dsplib.f32(r_in),
                                 dsplib.f32(l_out), dsplib.f32(r_out), 16)
        out[i:i + 16], out[half + i:half + i + 16] = l_out, r_out
    assert out.tobytes() == y.tobytes()


def test_peq_case_is_the_block(lib):
    """peq_f32 (budget option D) equals dsp_peq run through Python with the same settings."""
    x, y = dsplib.selftest_run(lib, case_index(lib, "peq_f32"))
    peq = dsplib.DspPeqF32()
    lib.dsp_peq_f32_init(ctypes.byref(peq), 48000.0, 1)
    lib.dsp_peq_f32_set_highpass(ctypes.byref(peq), 40.0)
    for b, band in enumerate(((2, 100.0, 3.0, 1.0), (1, 400.0, -4.0, 1.0), (1, 3000.0, 2.0, 0.7),
                              (3, 8000.0, -2.0, 1.0))):
        lib.dsp_peq_f32_set_band(ctypes.byref(peq), b, ctypes.byref(dsplib.DspPeqBand(*band)))
    lib.dsp_peq_f32_reset(ctypes.byref(peq))
    assert peq.first_f32 == 3
    out = np.zeros_like(x)
    for i in range(0, len(x), 16):
        xs = x[i:i + 16].copy()
        ys = np.zeros_like(xs)
        lib.dsp_peq_f32_process(ctypes.byref(peq), dsplib.f32(xs), dsplib.f32(ys), 16)
        out[i:i + 16] = ys
    assert out.tobytes() == y.tobytes()


def test_biquad_f64_case_matches_reference(lib):
    x, y = dsplib.selftest_run(lib, case_index(lib, "biquad_f64"))
    dsplib.assert_within_db(y, biquad_ref.f64_cascade(x, CASCADE), -135.0)


def test_batch6_cases_are_the_blocks(lib):
    """Each batch 6 case equals the block run through its Python binding with the same settings
    (catches wiring mistakes in dsp_selftest.c), and stays finite and bounded."""
    import dsplib_b6 as b6
    b6.bind(lib)
    x, _ = dsplib.selftest_run(lib, case_index(lib, "comp_f32"))

    def blocks(fn, state, data):
        out = np.zeros_like(data)
        for i in range(0, len(data), 16):
            xs, ys = data[i:i + 16].copy(), np.zeros(16, dtype=np.float32)
            fn(ctypes.byref(state), dsplib.f32(xs), dsplib.f32(ys), 16)
            out[i:i + 16] = ys
        return out

    comp = b6.DspCompF32()
    lib.dsp_comp_f32_init(ctypes.byref(comp), 48000.0,
                          ctypes.byref(b6.DspCompParams(-20.0, 4.0, 6.0, 1.0, 10.0, 3.0, 80.0)))
    assert blocks(lib.dsp_comp_f32_process, comp, x).tobytes() == \
        dsplib.selftest_run(lib, case_index(lib, "comp_f32"))[1].tobytes()
    gate = b6.DspGateF32()
    lib.dsp_gate_f32_init(ctypes.byref(gate), 48000.0,
                          ctypes.byref(b6.DspGateParams(-30.0, 6.0, 1.0, 0.2, 2.0, -60.0, 1.0)))
    assert blocks(lib.dsp_gate_f32_process, gate, x).tobytes() == \
        dsplib.selftest_run(lib, case_index(lib, "gate_f32"))[1].tobytes()
    for name, mode in (("sat_os4_f32", 2), ("sat_adaa_f32", 3), ("sat_os2_f32", 1)):
        sat = b6.DspSaturatorF32()
        lib.dsp_saturator_f32_init(ctypes.byref(sat), mode, 12.0)
        assert blocks(lib.dsp_saturator_f32_process, sat, x).tobytes() == \
            dsplib.selftest_run(lib, case_index(lib, name))[1].tobytes(), name
    _, y = dsplib.selftest_run(lib, case_index(lib, "limiter_sp_f32"))
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 10 ** (-6 / 20) * (1 + 1e-6)
    _, y = dsplib.selftest_run(lib, case_index(lib, "limiter_f32"))
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 10 ** (-6.5 / 20) * (1 + 1e-6)


def test_budget_decomposition_cases(lib):
    """tanh_libm_f32 and tanh_fast_f32 are tanh(4x); os4_pass_f32 is the 4x oversampler up and
    down with nothing between."""
    import dsplib_b6 as b6
    lib6 = b6.bind(lib)
    x, y = dsplib.selftest_run(lib, case_index(lib, "tanh_libm_f32"))
    assert np.max(np.abs(y - np.tanh(4.0 * x.astype(np.float64)))) < 1e-6
    x, y = dsplib.selftest_run(lib, case_index(lib, "tanh_fast_f32"))
    assert np.max(np.abs(y - np.tanh(4.0 * x.astype(np.float64)))) < 3e-7
    x, y = dsplib.selftest_run(lib, case_index(lib, "os4_pass_f32"))
    os = b6.DspOversampleF32()
    lib6.dsp_oversample_f32_init(ctypes.byref(os), 4)
    expected = np.zeros_like(x)
    buf = np.zeros(64, dtype=np.float32)
    for i in range(0, len(x), 16):
        blk = x[i:i + 16].copy()
        out = np.zeros(16, dtype=np.float32)
        lib6.dsp_oversample_f32_up(ctypes.byref(os), dsplib.f32(blk), dsplib.f32(buf), 16)
        lib6.dsp_oversample_f32_down(ctypes.byref(os), dsplib.f32(buf), dsplib.f32(out), 16)
        expected[i:i + 16] = out
    assert y.tobytes() == expected.tobytes()

