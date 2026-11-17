"""The comparison tools/target_test.py makes between the board and the PC library, exercised
without a board: the "target" text is made from the PC library in the firmware's format."""
import numpy as np
import pytest

import dsplib
import target_protocol as protocol


def test_bench_lines_parse():
    lines = [
        "dsp-interface fw 0.1.0 cm7",
        "bench gain_f32 fmt=f32 frames=1024 runs=33 min=10240 med=10300 max=20000 crc=0a1b2c3d",
        "bench noise_q31 fmt=q31 frames=1024 runs=33 min=5120 med=5130 max=6000 crc=FFFFFFFF",
        "bench done",
    ]
    benches = protocol.parse_bench(lines)
    assert [b.name for b in benches] == ["gain_f32", "noise_q31"]
    assert benches[0].crc == 0x0A1B2C3D and benches[0].cycles_per_sample == 10.0
    assert benches[1].fmt == "q31" and benches[1].crc == 0xFFFFFFFF


def test_fixed_point_case_matches_by_checksum(lib):
    for index, name, fmt in dsplib.selftest_cases(lib):
        if fmt != dsplib.FMT_Q31:
            continue
        _, output = dsplib.selftest_run(lib, index)
        bench = protocol.parse_bench([protocol.format_bench(name, "q31", output)])[0]
        ok, _ = protocol.compare_fixed(bench, output)
        assert ok
        # The checksum the firmware computes (dsp_crc32) is the one the tool computes (zlib).
        assert bench.crc == lib.dsp_crc32(0, output.ctypes.data, output.nbytes)
        corrupted = output.copy()
        corrupted[100] ^= 1
        ok, _ = protocol.compare_fixed(bench, corrupted)
        assert not ok


def test_float_case_round_trips_through_a_dump(lib):
    for index, name, fmt in dsplib.selftest_cases(lib):
        if fmt != dsplib.FMT_F32:
            continue
        _, output = dsplib.selftest_run(lib, index)
        dumped_name, words = protocol.parse_vec(protocol.format_vec(name, output))
        assert dumped_name == name
        ok, message, _ = protocol.compare_float(words, output)
        assert ok and "bit-identical" in message


def test_float_tolerance(lib):
    output = np.linspace(-0.5, 0.5, 1024, dtype=np.float32)
    close = (output + np.float32(5e-7)).view(np.uint32)   # -126 dBFS
    far = (output + np.float32(5e-6)).view(np.uint32)     # -106 dBFS
    assert protocol.compare_float(close, output)[0]
    assert not protocol.compare_float(far, output)[0]
    bad = output.copy()
    bad[3] = np.nan
    assert not protocol.compare_float(bad.view(np.uint32), output)[0]


def test_incomplete_dump_is_rejected():
    lines = protocol.format_vec("x", np.zeros(16, dtype=np.float32))
    with pytest.raises(ValueError):
        protocol.parse_vec(lines[:-1])          # No `end`.
    with pytest.raises(ValueError):
        protocol.parse_vec(lines[:2] + lines[-1:])  # Words missing.
