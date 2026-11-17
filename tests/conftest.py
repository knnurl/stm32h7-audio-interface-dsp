import pytest

import dsplib


@pytest.fixture(scope="session")
def lib():
    return dsplib.load()
