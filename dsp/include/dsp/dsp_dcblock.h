/* DC blocker: a one-pole, one-zero high-pass that removes a constant offset.
 *
 *   y[n] = x[n] - x[n-1] + r * y[n-1],   r = 1 - 2 * pi * cutoff_hz / sample_rate_hz
 *
 * EXERCISE EX1 (docs/exercises/EX1_dcblock.md): the owner writes dsp_dcblock.c. The reference
 * model is tests/ref/dcblock.py and the tests are tests/exercises/test_ex1_dcblock.py.
 *
 * Assumptions: mono; `in` and `out` may be the same buffer; cutoff far below the sample rate.
 * Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): to be measured by the owner.
 */
#ifndef DSP_DCBLOCK_H
#define DSP_DCBLOCK_H

#include <stddef.h>

typedef struct {
    float r;      /* Pole radius. */
    float x_prev; /* x[n-1] */
    float y_prev; /* y[n-1] */
} DspDcblockF32;

void dsp_dcblock_f32_init(DspDcblockF32 *state, float sample_rate_hz, float cutoff_hz);
void dsp_dcblock_f32_reset(DspDcblockF32 *state);
void dsp_dcblock_f32_process(DspDcblockF32 *state, const float *in, float *out, size_t n_frames);

#endif
