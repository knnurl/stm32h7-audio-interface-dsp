/* Deterministic test signals. The target generates the same input as the PC without a file, so
 * the two can be compared by a checksum.
 *
 * Noise, impulse and step are bit-exact on every platform: they use integer arithmetic and
 * exactly representable scalings only. The sine calls the C library and is not: never use it
 * where outputs are compared by checksum.
 */
#ifndef DSP_TESTSIG_H
#define DSP_TESTSIG_H

#include <stddef.h>
#include <stdint.h>

/* A 32-bit linear congruential generator (multiplier 1664525, increment 1013904223). White
 * enough for test input; not for dither (its low bits have short periods). */
typedef struct {
    uint32_t state;
} DspNoise;

void dsp_noise_seed(DspNoise *noise, uint32_t seed);
/* Uniform in [-1, 1) as Q31. */
void dsp_noise_q31(DspNoise *noise, int32_t *out, size_t n_frames);
/* The Q31 value converted to float (rounded to nearest) and scaled: uniform in about
 * [-amplitude, amplitude]. Bit-exact when the amplitude is a power of two. */
void dsp_noise_f32(DspNoise *noise, float *out, size_t n_frames, float amplitude);

void dsp_impulse_f32(float *out, size_t n_frames, size_t position, float amplitude);
/* Zero before `position`, `amplitude` from it on. */
void dsp_step_f32(float *out, size_t n_frames, size_t position, float amplitude);
/* Not bit-exact across platforms (sinf). */
void dsp_sine_f32(float *out, size_t n_frames, float freq_hz, float sample_rate_hz,
                  float amplitude);

#endif
