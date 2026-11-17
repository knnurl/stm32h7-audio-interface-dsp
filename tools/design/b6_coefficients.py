"""Designs the fixed coefficients batch 6 compiles into the library, and prints them as C.

    python tools/design/b6_coefficients.py

1. Fast log2 and exp2 polynomials (dsp_fastmath.c). Constrained so the curve is continuous at
   octave boundaries:  log2(1 + t) ~ t + t (t - 1) P(t),  2^f ~ 1 + f + f (f - 1) Q(f),  with
   P and Q cubic, fitted for minimum maximum error (iterated weighted least squares).
2. Half-band low-pass filters for 2x oversampling (dsp_oversample.c), equiripple (Parks-McClellan
   via scipy.signal.remez):
     stage 1 (base rate to 2x, 83 taps):  passband to 0.2083 fs_out (20 kHz at 96 kHz), stopband from
                                 0.2917 fs_out (28 kHz), the alias image of 20 kHz.
     stage 2 (2x to 4x, 23 taps):         passband to 0.1042 fs_out, stopband from 0.3958 fs_out.
   A half-band filter has every other tap zero except the centre (0.5), which is what makes it
   cheap; remez on a symmetric specification gives that structure to within rounding, and the
   script forces it.
"""
import numpy as np
from scipy import signal


def minimax_fit(t, target, basis, iterations=60):
    w = np.ones_like(t)
    for _ in range(iterations):
        a = basis * w[:, None]
        coef, *_ = np.linalg.lstsq(a, target * w, rcond=None)
        err = np.abs(basis @ coef - target)
        w = w * (1.0 + err / err.max())
        w /= w.mean()
    return coef, np.max(np.abs(basis @ coef - target))


def fast_math():
    t = np.cos(np.linspace(0, np.pi, 4001)) * 0.5 + 0.5  # Chebyshev-spaced on [0, 1]
    # log2(1 + t) - t = t (t - 1) P(t)
    target = np.log2(1 + t) - t
    g = t * (t - 1)
    basis = np.stack([g, g * t, g * t ** 2, g * t ** 3], axis=1)
    keep = g != 0
    p, _ = minimax_fit(t[keep], target[keep], basis[keep])
    err_log = np.max(np.abs(t + basis @ p - np.log2(1 + t)))
    # 2^f - 1 - f = f (f - 1) Q(f), relative error
    target = 2 ** t - 1 - t
    q, _ = minimax_fit(t[keep], target[keep], basis[keep])
    approx = 1 + t + basis @ q
    err_exp = np.max(np.abs(approx / 2 ** t - 1))
    return p, err_log, q, err_exp


def halfband(numtaps, pass_edge, stop_edge):
    h = signal.remez(numtaps, [0, pass_edge, stop_edge, 0.5], [1, 0], weight=[1, 1], fs=1.0)
    centre = (numtaps - 1) // 2
    for i in range(numtaps):
        if (i - centre) % 2 == 0 and i != centre:
            h[i] = 0.0
    h[centre] = 0.5
    w, resp = signal.freqz(h, worN=1 << 16, fs=1.0)
    mag = np.abs(resp)
    passband = mag[w <= pass_edge]
    stopband = mag[w >= stop_edge]
    ripple_db = 20 * np.log10(passband.max() / passband.min())
    atten_db = -20 * np.log10(stopband.max())
    return h, ripple_db, atten_db


def c_array(name, values, per_line=4, kind="float", suffix="f"):
    fmt = "{:.9e}" if kind == "float" else "{:.17g}"
    items = [fmt.format(v) + suffix for v in values]
    lines = []
    for i in range(0, len(items), per_line):
        lines.append("    " + ", ".join(items[i:i + per_line]) + ",")
    return f"static const {kind} {name}[{len(values)}] = {{\n" + "\n".join(lines) + "\n};"


def main():
    p, err_log, q, err_exp = fast_math()
    print(f"/* log2: max abs error {err_log:.3e} (= {6.0206 * err_log:.2e} dB) */")
    print(c_array("kLog2Poly", p, kind="float"))
    print(f"/* exp2: max rel error {err_exp:.3e} (= {20 * np.log10(1 + err_exp):.2e} dB) */")
    print(c_array("kExp2Poly", q, kind="float"))
    for name, numtaps, pe, se in (("kHalfband1", 83, 0.2083, 0.2917),
                                  ("kHalfband2", 23, 0.1042, 0.3958)):
        h, ripple, atten = halfband(numtaps, pe, se)
        print(f"/* {name}: {numtaps} taps, passband ripple {ripple:.4f} dB, "
              f"stopband {atten:.1f} dB */")
        print(c_array(name, h, per_line=4, kind="float"))


if __name__ == "__main__":
    main()
