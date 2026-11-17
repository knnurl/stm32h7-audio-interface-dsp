"""Reference model of dsp_tone's filtering: the three bands designed in float64 from given gains,
run in float64. The smoothing of the gains is checked on its own (tests/unit/test_tone.py); for
the filtering comparison the test reads the C block's smoothed gains block by block and designs
from those, so the two are compared on identical gains."""
import numpy as np
from scipy import signal

from ref import coef

BANDS = (100.0, 1000.0, 10000.0)


def sections(fs, gains_db, freqs=BANDS):
    out = []
    if gains_db[0] != 0.0:
        out.append(coef.low_shelf(fs, freqs[0], 1.0, gains_db[0]))
    if gains_db[1] != 0.0:
        out.append(coef.peak(fs, freqs[1], 0.7, gains_db[1]))
    if gains_db[2] != 0.0:
        out.append(coef.high_shelf(fs, freqs[2], 1.0, gains_db[2]))
    return out


def magnitude_db(fs, gains_db, f):
    secs = sections(fs, gains_db)
    return coef.magnitude_db(secs, fs, f) if secs else np.zeros_like(np.asarray(f, float))


class Blockwise:
    """Float64 filtering with per-block coefficients and carried TDF-II state (scipy's lfilter is
    transposed direct form II, so its zi is the same state as the C code's)."""

    def __init__(self, fs):
        self.fs = fs
        self.zi = [np.zeros(2) for _ in range(3)]

    def process(self, x, gains_db, active):
        y = np.asarray(x, dtype=np.float64)
        designs = [lambda g: coef.low_shelf(self.fs, BANDS[0], 1.0, g),
                   lambda g: coef.peak(self.fs, BANDS[1], 0.7, g),
                   lambda g: coef.high_shelf(self.fs, BANDS[2], 1.0, g)]
        for band in range(3):
            if not active[band]:
                self.zi[band] = np.zeros(2)
                continue
            b0, b1, b2, a1, a2 = designs[band](gains_db[band])
            y, self.zi[band] = signal.lfilter([b0, b1, b2], [1.0, a1, a2], y, zi=self.zi[band])
        return y
