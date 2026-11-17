/* Biquad filter sections, in float and in Q31.
 *
 * Float: transposed direct form II.
 *   y = b0 x + z1;   z1 = b1 x - a1 y + z2;   z2 = b2 x - a2 y
 * Two state words per section; in float the state carries the signal with full relative
 * precision, so this is the usual choice for float32.
 *
 * Q31: direct form I with a 64-bit accumulator, coefficients scaled by 2^(30 - shift).
 *   acc = b0 x + b1 x1 + b2 x2 - a1 y1 - a2 y2          (Q31 x Q(30-shift) products)
 *   y   = acc >> (30 - shift), saturated to 32 bits
 * Direct form I because its state is the input and output samples themselves: they cannot
 * overflow, and the only rounding is the one at the output. `shift` (0 to 7) is chosen per
 * section by dsp_coef_to_q31 so that every coefficient fits and the accumulator cannot
 * overflow: the sum of |coefficients| times 2^31 stays below 2^63.
 * Rounding: without error feedback, round half up (add half, then arithmetic shift). With
 * first-order error feedback, the bits shifted out are kept and added to the next sample's
 * accumulator, which moves the rounding noise's spectrum away from DC.
 * Assumes `>>` on a negative int64 is an arithmetic shift (implementation-defined in C11; GCC
 * and MSVC both do it).
 *
 * Assumptions: mono; `in` and `out` may be the same buffer; a cascade runs section by section
 * over the whole block. Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): not yet measured (needs the board).
 */
#ifndef DSP_BIQUAD_H
#define DSP_BIQUAD_H

#include <stddef.h>
#include <stdint.h>

enum { kDspBiquadMaxSections = 8 };

typedef struct {
    float b0, b1, b2, a1, a2; /* Normalised: a0 = 1. */
} DspBiquadCoefsF32;

typedef struct {
    float z1, z2;
} DspBiquadStateF32;

typedef struct {
    size_t n_sections;
    DspBiquadCoefsF32 coefs[kDspBiquadMaxSections];
    DspBiquadStateF32 state[kDspBiquadMaxSections];
} DspBiquadF32;

typedef struct {
    int32_t b0, b1, b2, a1, a2; /* Scaled by 2^(30 - shift). */
    int32_t shift;
} DspBiquadCoefsQ31;

typedef struct {
    int32_t x1, x2, y1, y2;
    int32_t err; /* Error feedback: the bits shifted out last sample, 0 to 2^(30-shift) - 1. */
} DspBiquadStateQ31;

typedef struct {
    size_t n_sections;
    int32_t error_feedback; /* 0 or 1. */
    DspBiquadCoefsQ31 coefs[kDspBiquadMaxSections];
    DspBiquadStateQ31 state[kDspBiquadMaxSections];
} DspBiquadQ31;

/* Float input and output, double-precision coefficients and state (TDF-II). For sections
 * whose poles sit close to z = 1 (low corner frequencies), where float32 state noise is
 * amplified by up to 1 / (1 + a1 + a2): docs/results/b3_filter_noise.md. The M7 has a
 * double-precision FPU; the cycle cost against the float kernel is measured on the board. */
typedef struct {
    double b0, b1, b2, a1, a2;
} DspBiquadCoefsF64;

typedef struct {
    double z1, z2;
} DspBiquadStateF64;

void dsp_biquad_f64_section(const DspBiquadCoefsF64 *coefs, DspBiquadStateF64 *state,
                            const float *in, float *out, size_t n_frames);

/* One float section over a block, for blocks that keep their own state (tone, PEQ). */
void dsp_biquad_f32_section(const DspBiquadCoefsF32 *coefs, DspBiquadStateF32 *state,
                            const float *in, float *out, size_t n_frames);

/* Up to kDspBiquadMaxSections sections; more are ignored. State cleared. */
void dsp_biquad_f32_init(DspBiquadF32 *filter, const DspBiquadCoefsF32 *coefs, size_t n_sections);
void dsp_biquad_f32_reset(DspBiquadF32 *filter);
void dsp_biquad_f32_process(DspBiquadF32 *filter, const float *in, float *out, size_t n_frames);

void dsp_biquad_q31_init(DspBiquadQ31 *filter, const DspBiquadCoefsQ31 *coefs, size_t n_sections,
                         int32_t error_feedback);
void dsp_biquad_q31_reset(DspBiquadQ31 *filter);
void dsp_biquad_q31_process(DspBiquadQ31 *filter, const int32_t *in, int32_t *out,
                            size_t n_frames);

#endif
