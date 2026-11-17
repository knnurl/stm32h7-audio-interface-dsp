import pytest

import ctllib
import dsplib


@pytest.fixture(scope="session")
def lib():
    return dsplib.load()


@pytest.fixture(scope="session")
def ctl():
    return ctllib.load()


@pytest.fixture
def dev(ctl):
    """A fresh device: control stack and blank simulated flash."""
    return ctllib.Device(ctl)
