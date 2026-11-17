#include "dsp/dsp_testsig.h"

#include <math.h>

static uint32_t noise_next(DspNoise *noise) {
    noise->state = noise->state * 1664525u + 1013904223u;
    return noise->state;
}

void dsp_noise_seed(DspNoise *noise, uint32_t seed) { noise->state = seed; }

void dsp_noise_q31(DspNoise *noise, int32_t *out, size_t n_frames) {
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = (int32_t)noise_next(noise);
    }
}

void dsp_noise_f32(DspNoise *noise, float *out, size_t n_frames, float amplitude) {
    const float scale = amplitude * (1.0f / 2147483648.0f);
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = (float)(int32_t)noise_next(noise) * scale;
    }
}

void dsp_impulse_f32(float *out, size_t n_frames, size_t position, float amplitude) {
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = i == position ? amplitude : 0.0f;
    }
}

void dsp_step_f32(float *out, size_t n_frames, size_t position, float amplitude) {
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = i >= position ? amplitude : 0.0f;
    }
}

void dsp_sine_f32(float *out, size_t n_frames, float freq_hz, float sample_rate_hz,
                  float amplitude) {
    const float step = 6.283185307179586f * freq_hz / sample_rate_hz;
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = amplitude * sinf(step * (float)i);
    }
}
