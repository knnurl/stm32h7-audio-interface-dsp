"""Every ctypes mirror has the size the compiler gives its struct. A wrong mirror would make the
other tests read and write the wrong bytes without failing."""
import ctypes

import pytest

import dsplib
import dsplib_b6

MIRRORS = [dsplib.DspBiquadF32, dsplib.DspBiquadQ31, dsplib.DspPeqF32, dsplib.DspToneF32,
           *dsplib_b6.MIRRORS]


@pytest.mark.parametrize("mirror", MIRRORS, ids=lambda m: m.__name__)
def test_mirror_sizes(lib, mirror):
    dsplib_b6.bind(lib)
    size = lib.dsp_abi_sizeof(mirror.__name__.encode())
    assert size != 0, f"dsp_abi.c does not list {mirror.__name__}"
    assert ctypes.sizeof(mirror) == size
