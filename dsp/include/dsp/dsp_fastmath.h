/* Fast log2 and exp2 for per-sample level detection and gain in the dynamics blocks.
 *
 * log2: the float's exponent plus a polynomial on its mantissa, max error 1.6e-5 (1e-4 dB).
 * exp2: a polynomial on the fractional part, scaled by building the float's exponent, max
 * relative error 1.3e-7 (1.1e-6 dB). Both polynomials are constrained so the result is
 * continuous at every octave boundary (tools/design/b6_coefficients.py designs them).
 *
 * Domain: log2 of values at or below 1e-30, and of NaN, returns log2(1e-30) (-99.66), so silence
 * gives a finite level of about -600 dBFS. exp2 clamps its argument to [-126, 127]; NaN gives
 * 2^-126. Errors as evaluated in float32: log2 1.7e-5, exp2 2.4e-7 relative (the design figures
 * above are in double).
 * Bit-identical on every IEEE-754 platform with fused multiply-add off (no library calls).
 */
#ifndef DSP_FASTMATH_H
#define DSP_FASTMATH_H

float dsp_fast_log2f(float x);
float dsp_fast_exp2f(float x);
/* 20 log10(|x|) and 10^(db / 20), built on the two above. */
float dsp_fast_lin_to_db(float x);
float dsp_fast_db_to_lin(float db);

#endif
