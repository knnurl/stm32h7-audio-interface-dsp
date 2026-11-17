"""The self-test cases the firmware also runs. Each case is checked here against its Python
reference, so a target that matches the PC library also matches the reference."""
import numpy as np

import dsplib
from ref import gain as gain_ref
from ref import testsig as testsig_ref


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
