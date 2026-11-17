/* EXERCISE EX1: not implemented yet. See docs/exercises/EX1_dcblock.md.
 * The stubs below only let the library build; tests/exercises/test_ex1_dcblock.py fails until
 * they are replaced. */
#include "dsp/dsp_dcblock.h"

void dsp_dcblock_f32_init(DspDcblockF32 *state, float sample_rate_hz, float cutoff_hz) {
    (void)sample_rate_hz;
    (void)cutoff_hz;
    state->r = 0.0f;
    state->x_prev = 0.0f;
    state->y_prev = 0.0f;
}

void dsp_dcblock_f32_reset(DspDcblockF32 *state) {
    state->x_prev = 0.0f;
    state->y_prev = 0.0f;
}

void dsp_dcblock_f32_process(DspDcblockF32 *state, const float *in, float *out, size_t n_frames) {
    (void)state;
    (void)in;
    (void)out;
    (void)n_frames;
}
