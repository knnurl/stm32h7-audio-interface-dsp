"""Budget option D study: can the upper PEQ bands run in float32 above some corner frequency?

    python tools/studies/peq_f32_noise.py [--out docs/results/peq_f32_noise.md]

For a peak and a high shelf at corner frequencies from 500 Hz to 20 kHz, every Q (or shelf
slope) at the ends of the registry range, gains of -15 and +15 dB, at 48 and 96 kHz, it reports:
  arithmetic SNR  the library's float32 TDF-II kernel against float64 running the same float32
                  coefficients, on white noise at -1 dBFS and at -60 dBFS (worst of the two):
                  the noise the float32 state adds, as in docs/results/b3_filter_noise.md;
  response error  the largest difference, 20 Hz to 20 kHz, between the response with float32
                  coefficients and with double ones: what rounding the coefficients changes.
The PEQ's double sections are the reference: they reach about 152 dB, the float32 output's own
rounding (b3_filter_noise.md). The criterion for float32 (SPEC decision log, 2026-11-18): at
least 110 dB of arithmetic SNR (under the PCM3168A DAC's 112 dB dynamic range [Verify]) and a
response within 0.01 dB of the double design, at every setting in the band's range.
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
CORNERS_HZ = (500.0, 700.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0, 4000.0, 5000.0, 10000.0,
              16000.0, 20000.0)
QS = (0.1, 0.7, 10.0)
GAINS_DB = (-15.0, 15.0)
SNR_MIN_DB = 110.0
RESPONSE_MAX_DB = 0.01


def run_f32(lib, section, x):
    c = dsplib.DspBiquadCoefsF32(*[float(F32(v)) for v in section])
    st = dsplib.DspBiquadStateF32()
    y = np.zeros_like(x)
    lib.dsp_biquad_f32_section(ctypes.byref(c), ctypes.byref(st), dsplib.f32(x), dsplib.f32(y),
                               len(x))
    return y


def snr_db(out, ref, start):
    ref = np.asarray(ref[start:], dtype=np.float64)
    err = np.asarray(out[start:], dtype=np.float64) - ref
    pe = np.mean(err ** 2)
    return np.inf if pe == 0 else 10 * np.log10(np.mean(ref ** 2) / pe)


def arithmetic_snr(lib, section, fs):
    n = int(fs)
    start = n // 4
    s32 = np.float32(section).astype(np.float64)
    worst = np.inf
    for level_db in (-1.0, -60.0):
        x = (10 ** (level_db / 20) * np.random.default_rng(7).uniform(-1, 1, n)).astype(F32)
        ref = ref_biquad.f64_cascade(x.astype(np.float64), [s32])
        worst = min(worst, snr_db(run_f32(lib, section, x), ref, start))
    return worst


def response_error_db(section, fs):
    f = np.geomspace(20.0, min(20000.0, 0.49 * fs), 2000)
    s32 = np.float32(section).astype(np.float64)
    diff = coef.magnitude_db([s32], fs, f) - coef.magnitude_db([section], fs, f)
    return float(np.max(np.abs(diff)))


def designs(fs, f0):
    for q in QS:
        for g in GAINS_DB:
            yield f"peak Q {q:g} {g:+g} dB", coef.peak(fs, f0, q, g)
    for s in (0.1, 1.0):  # Shelf slope: the registry's Q range doubles as S; S above 1 overshoots.
        for g in GAINS_DB:
            yield f"high shelf S {s:g} {g:+g} dB", coef.high_shelf(fs, f0, s, g)


def study(lib):
    rows = []
    for fs in (48000.0, 96000.0):
        for f0 in CORNERS_HZ:
            if f0 >= 0.45 * fs:
                continue
            worst_snr, worst_snr_name = np.inf, ""
            worst_resp, worst_resp_name = 0.0, ""
            for name, section in designs(fs, f0):
                snr = arithmetic_snr(lib, section, fs)
                resp = response_error_db(section, fs)
                if snr < worst_snr:
                    worst_snr, worst_snr_name = snr, name
                if resp > worst_resp:
                    worst_resp, worst_resp_name = resp, name
            rows.append((fs, f0, worst_snr, worst_snr_name, worst_resp, worst_resp_name))
    return rows


def pair_snr(lib, fs, corner_hz, slope, gain_db, level_db):
    """Band 3 a peak at the corner (Q 10, +15 dB) then band 4 a high shelf at the corner, the two
    as the registry types them, through the float32 kernel the PEQ uses for them (the PEQ itself
    would raise a corner under DSP_PEQ_F32_MIN_HZ)."""
    n = int(fs)
    x = (10 ** (level_db / 20) * np.random.default_rng(7).uniform(-1, 1, n)).astype(F32)
    sections = [coef.peak(fs, corner_hz, 10.0, 15.0),
                coef.high_shelf(fs, corner_hz, slope, gain_db)]
    y = run_f32(lib, sections[1], run_f32(lib, sections[0], x))
    rounded = [np.float32(sec).astype(np.float64) for sec in sections]
    ref = ref_biquad.f64_cascade(x.astype(np.float64), rounded)
    return snr_db(y, ref, n // 4)


def pairs(lib):
    rows = []
    for corner in (2000.0, 2500.0, 3000.0, 4000.0):
        worst = min(pair_snr(lib, 48000.0, corner, s, g, lv) for s in (0.1, 1.0)
                    for g in GAINS_DB for lv in (-1.0, -60.0))
        rows.append((corner, worst))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "docs/results/peq_f32_noise.md"))
    args = parser.parse_args()
    lib = dsplib.load()
    rows = study(lib)
    lines = [
        "# Budget option D: float32 sections for the upper PEQ bands",
        "",
        "Worst case over peak (Q 0.1, 0.7, 10) and high shelf (S 0.1, 1), gain -15 and +15 dB,",
        "of one float32 TDF-II section. Arithmetic SNR: white noise at -1 and -60 dBFS against",
        "float64 with the same float32 coefficients. Response error: float32 against double",
        "coefficients,",
        f"20 Hz to 20 kHz. Pass: SNR at least {SNR_MIN_DB:g} dB and response within "
        f"{RESPONSE_MAX_DB:g} dB.",
        "Generated by `python tools/studies/peq_f32_noise.py`.",
        "",
        "| fs | Corner | Worst SNR (dB) | at | Worst response error (dB) | at | Pass |",
        "|---|---|---|---|---|---|---|",
    ]
    for fs, f0, snr, sn, resp, rn in rows:
        ok = snr >= SNR_MIN_DB and resp <= RESPONSE_MAX_DB
        lines.append(f"| {fs / 1000:g} kHz | {f0:g} Hz | {snr:.1f} | {sn} | {resp:.5f} | {rn} | "
                     f"{'yes' if ok else 'no'} |")
        print(lines[-1])
    lines += [
        "",
        "## Bands 3 and 4 together at 48 kHz (float32 kernel, as `dsp_peq` runs them)",
        "",
        "Band 3 a peak at the corner (Q 10, +15 dB), band 4 a high shelf at the corner (S 0.1 and",
        "1, -15 and +15 dB), as the registry types them; worst over the shelf settings and the two",
        "input levels.",
        "",
        "| Corner | Worst SNR (dB) | Pass |",
        "|---|---|---|",
    ]
    for corner, snr in pairs(lib):
        lines.append(f"| {corner:g} Hz | {snr:.1f} | {'yes' if snr >= SNR_MIN_DB else 'no'} |")
        print(lines[-1])
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
