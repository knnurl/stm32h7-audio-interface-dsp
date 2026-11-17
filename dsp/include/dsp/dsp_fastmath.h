/* Fast log2 and exp2 for per-sample level detection and gain in the dynamics blocks.
 *
 * log2: the float's exponent plus a polynomial on its mantissa, max error 1.6e-5 (1e-4 dB).
 * exp2: a polynomial on the fractional part, scaled by building the float's exponent, max
 * relative error 1.3e-7 (1.1e-6 dB). Both polynomials are constrained so the result is
 * continuous at every octave boundary (tools/design/b6_coefficients.py designs them).
 *
 * Domain: log2 of values at or below 1e-30, and of NaN, returns log2(1e-30) (-99.66), so silence
 * gives a finite level of about -600 dBFS. exp2 clamps its argument to [-126, 127]; NaN gives
 * 2^-126. Errors as evaluated in float32 (measured, tests/unit/test_fastmath_env.py): log2
 * 2.3e-5 (1.4e-4 dB), exp2 2.4e-7 relative. The design figures above are in double.
 * Bit-identical on every IEEE-754 platform with fused multiply-add off (no library calls).
 */
#ifndef DSP_FASTMATH_H
#define DSP_FASTMATH_H

float dsp_fast_log2f(float x);
float dsp_fast_exp2f(float x);
/* 20 log10(|x|) and 10^(db / 20), built on the two above. */
float dsp_fast_lin_to_db(float x);
float dsp_fast_db_to_lin(float db);
/* tanh(x) = 1 - 2 / (e^(2|x|) + 1), sign restored, with e^(2|x|) from dsp_fast_exp2f: one
 * polynomial and one division instead of the C library's tanhf (budget work, 2026-11-17).
 * Odd, bounded by 1 in magnitude, monotonic to float rounding. Absolute error at most 3e-7
 * (measured, tests/unit/test_fastmath_env.py). |x| >= 9 gives exactly +/-1 (tanh(9) rounds to 1
 * in float32); NaN gives 0. */
float dsp_fast_tanhf(float x);

#endif
