"""Batch 3 study: arithmetic noise of low-frequency biquads in each number format.

    python tools/studies/b3_filter_noise.py [--out docs/results/b3_filter_noise.md]

For each filter, sample rate and input level it reports the signal-to-noise ratio of:
  f32 TDF-II   the library's float kernel (C, through ctypes)
  f32 DF-I     direct form I in float32, emulated in numpy (one rounding per operation)
  f64 TDF-II   the library's double-state kernel: float in and out, double inside
  q31 DF-I     the library's Q31 kernel, rounding to nearest
  q31 DF-I EF  the same with first-order error feedback
For f64 the output is rounded to float32, so the column shows the float32 output's own
rounding, which is the floor any float path has; the double arithmetic is far below it.
Noise means arithmetic noise only: each format's reference is the float64 cascade run with that
format's own quantised coefficients on that format's own quantised input, so coefficient
quantisation (a fixed change of response) is not counted as noise.
SNR = power of the reference / power of (output - reference), over the last 75 % of 1 s.
"""
import argparse
import ctypes
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

import dsplib  # noqa: E402
from ref import biquad as ref_biquad  # noqa: E402
from ref import coef  # noqa: E402

F32 = np.float32


def run_f32_tdf2(lib, section, x):
    c = dsplib.DspBiquadCoefsF32(*[float(F32(v)) for v in section])
    st = dsplib.DspBiquadStateF32()
    y = np.zeros_like(x)
    lib.dsp_biquad_f32_section(ctypes.byref(c), ctypes.byref(st), dsplib.f32(x), dsplib.f32(y),
                               len(x))
    return y


def run_f32_df1(section, x):
    b0, b1, b2, a1, a2 = (F32(v) for v in section)
    x1 = x2 = y1 = y2 = F32(0)
    y = np.empty_like(x)
    for i, xi in enumerate(x):
        acc = F32(b0 * xi)
        acc = F32(acc + F32(b1 * x1))
        acc = F32(acc + F32(b2 * x2))
        acc = F32(acc - F32(a1 * y1))
        acc = F32(acc - F32(a2 * y2))
        x2, x1, y2, y1 = x1, xi, y1, acc
        y[i] = acc
    return y


def run_f64(lib, section, x):
    c = dsplib.DspBiquadCoefsF64(*[float(v) for v in section])
    st = dsplib.DspBiquadStateF64()
    y = np.zeros_like(x)
    lib.dsp_biquad_f64_section(ctypes.byref(c), ctypes.byref(st), dsplib.f32(x), dsplib.f32(y),
                               len(x))
    return y


def run_q31(lib, q, shift, ef, x):
    c = (dsplib.DspBiquadCoefsQ31 * 1)(dsplib.DspBiquadCoefsQ31(*q, shift))
    filt = dsplib.DspBiquadQ31()
    lib.dsp_biquad_q31_init(ctypes.byref(filt), c, 1, ef)
    y = np.zeros_like(x)
    lib.dsp_biquad_q31_process(ctypes.byref(filt), dsplib.i32(x), dsplib.i32(y), len(x))
    return y


def snr_db(out, ref, start):
    ref = np.asarray(ref[start:], dtype=np.float64)
    err = np.asarray(out[start:], dtype=np.float64) - ref
    pe = np.mean(err ** 2)
    return np.inf if pe == 0 else 10 * np.log10(np.mean(ref ** 2) / pe)


def study(lib, name, section, fs, level_db):
    n = int(fs)
    start = n // 4
    t = np.arange(n)
    x64 = 10 ** (level_db / 20) * np.sin(2 * np.pi * 1000.0 * t / fs)
    x32 = x64.astype(F32)
    xq = np.round(x64 * 2 ** 31).clip(-2 ** 31, 2 ** 31 - 1).astype(np.int32)
    s32 = np.float32(section).astype(np.float64)
    q, shift = coef.to_q31(section)
    sq = np.array(q, dtype=np.float64) / 2.0 ** (30 - shift)

    ref32 = ref_biquad.f64_cascade(x32.astype(np.float64), [s32])
    ref64 = ref_biquad.f64_cascade(x32.astype(np.float64), [section])
    refq = ref_biquad.f64_cascade(xq / 2.0 ** 31, [sq])
    row = {
        "f64 TDF-II": snr_db(run_f64(lib, section, x32), ref64, start),
        "f32 TDF-II": snr_db(run_f32_tdf2(lib, section, x32), ref32, start),
        "f32 DF-I": snr_db(run_f32_df1(section, x32), ref32, start),
        "q31 DF-I": snr_db(run_q31(lib, q, shift, 0, xq) / 2.0 ** 31, refq, start),
        "q31 DF-I EF": snr_db(run_q31(lib, q, shift, 1, xq) / 2.0 ** 31, refq, start),
    }
    return row, shift


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "docs/results/b3_filter_noise.md"))
    args = parser.parse_args()
    lib = dsplib.load()

    filters = []
    for fs in (48000.0, 96000.0):
        filters.append(("HPF 20 Hz, Butterworth 2nd order", fs, coef.highpass(fs, 20.0, 0.7071)))
        for q in (0.7, 2.0, 10.0):
            filters.append((f"Peak 40 Hz +6 dB, Q {q}", fs, coef.peak(fs, 40.0, q, 6.0)))
        filters.append(("Tone bass: low shelf 100 Hz +12 dB", fs, coef.low_shelf(fs, 100.0, 1.0, 12.0)))
        filters.append(("Peak 1 kHz +6 dB, Q 1 (for comparison)", fs, coef.peak(fs, 1000.0, 1.0, 6.0)))
    columns = ["f32 TDF-II", "f32 DF-I", "f64 TDF-II", "q31 DF-I", "q31 DF-I EF"]
    lines = [
        "# Batch 3: arithmetic noise of low-frequency biquads",
        "",
        "Signal-to-noise ratio in dB (higher is better) of one biquad section on a 1 kHz sine.",
        "Arithmetic noise only: each format is compared with float64 running that format's own",
        "quantised coefficients. Generated by `python tools/studies/b3_filter_noise.py`.",
        "",
        "| Filter | fs | Input | Q31 shift | " + " | ".join(columns) + " |",
        "|---|---|---|---|" + "---|" * len(columns),
    ]
    for name, fs, section in filters:
        for level in (-60.0, -1.0):
            row, shift = study(lib, name, section, fs, level)
            cells = " | ".join(f"{row[c]:.1f}" for c in columns)
            lines.append(f"| {name} | {fs / 1000:g} kHz | {level:g} dBFS | {shift} | {cells} |")
            print(lines[-1])
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
