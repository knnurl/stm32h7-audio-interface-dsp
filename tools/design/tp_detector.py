"""Designs the limiter's true-peak detector: a 4x Nyquist interpolator (a windowed sinc cut at
the base rate's Nyquist, so every fourth tap but the centre is zero and phase 0 is the input
sample itself; only three phases are computed).

For each candidate it measures, for sines up to 20 kHz at 48 kHz over many starting phases, how
far the largest 4x sample falls below the sine's true peak (the under-read), next to the ideal 4x
interpolator's cos(pi f / 4 fs), and prints the taps of the chosen design. Run:
    python tools/design/tp_detector.py
"""
import numpy as np
from scipy import signal

FS = 48000.0
FREQS = [1000, 5000, 10000, 15000, 18000, 19000, 20000]


def design(taps_per_phase, beta):
    n = 4 * taps_per_phase - 1  # odd, centre at a multiple of 4 offset by the Nyquist zeros
    h = signal.firwin(n, 1.0 / 4.0, window=("kaiser", beta), scale=False) * 4.0
    c = n // 2
    for k in range(n):
        if (k - c) % 4 == 0:
            h[k] = 1.0 if k == c else 0.0
    return h


def interpolate(h, x):
    up = np.zeros(4 * len(x))
    up[::4] = x
    return np.convolve(up, h)[len(h) // 2: len(h) // 2 + len(up)]


def under_read_db(h, f, phases=48, n=600):
    worst = 0.0
    for p in np.linspace(0, 2 * np.pi, phases, endpoint=False):
        x = np.sin(2 * np.pi * f * np.arange(n) / FS + p)
        y = interpolate(h, x)[4 * 100: -4 * 100]  # steady part only
        worst = max(worst, -20 * np.log10(np.max(np.abs(y))))
    return worst


def ideal_db(f):
    return -20 * np.log10(np.cos(np.pi * f / (4 * FS)))


def main():
    print("ideal 4x:", {f: round(ideal_db(f), 3) for f in FREQS})
    chosen = None
    for taps, beta in [(8, 3.4), (12, 4.1), (16, 4.1), (20, 4.5), (24, 5.0)]:
        h = design(taps, beta)
        w, resp = signal.freqz(h / 4.0, worN=16384, fs=4 * FS)
        pb = 20 * np.log10(np.abs(resp[w <= 20000]))
        sb = 20 * np.log10(np.abs(resp[w >= 28000]) + 1e-12)
        reads = {f: round(under_read_db(h, f), 3) for f in FREQS}
        worst_extra = max(reads[f] - ideal_db(f) for f in FREQS)
        print(f"{taps:2d} taps/phase (length {len(h)}), kaiser {beta}: passband "
              f"{pb.min():+.3f}..{pb.max():+.3f} dB to 20 kHz, stopband {sb.max():.1f} dB from "
              f"28 kHz; under-read {reads}; worst beyond ideal {worst_extra:+.3f} dB")
        if chosen is None and worst_extra < 0.05:
            chosen = (taps, beta, h)
    if chosen:
        taps, beta, h = chosen
        print(f"\nchosen: {taps} taps per phase, kaiser {beta}; three phases, taps:")
        c = len(h) // 2
        for phase in (1, 2, 3):
            # Output phase k (k/4 of a sample after input m) uses h[c - k + 4 j] against x[m - j].
            coeffs = [h[c + phase - 4 * j] if 0 <= c + phase - 4 * j < len(h) else 0.0
                      for j in range(-taps // 2, taps // 2 + 1)]
            print(phase, ", ".join(f"{v:.9e}f" for v in coeffs))
    return 0


if __name__ == "__main__":
    main()
