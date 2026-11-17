#include "dsp/dsp_gain.h"

#include <math.h>

void dsp_gain_f32_init(DspGainF32 *state, float sample_rate_hz, float smoothing_ms) {
    state->gain = 1.0f;
    state->target = 1.0f;
    if (smoothing_ms <= 0.0f || sample_rate_hz <= 0.0f) {
        state->coef = 1.0f;
    } else {
        const float tau_samples = smoothing_ms * 0.001f * sample_rate_hz;
        /* 1 - exp(-1/tau), computed as -expm1: for a long time constant exp() is close to 1,
         * and subtracting it from 1 in float32 would leave the coefficient about 5 digits. */
        state->coef = -expm1f(-1.0f / tau_samples);
    }
}

void dsp_gain_f32_reset(DspGainF32 *state) { state->gain = state->target; }

void dsp_gain_f32_set_linear(DspGainF32 *state, float gain_linear) { state->target = gain_linear; }

void dsp_gain_f32_set_db(DspGainF32 *state, float gain_db) {
    state->target = powf(10.0f, gain_db * 0.05f);
}

void dsp_gain_f32_process(DspGainF32 *state, const float *in, float *out, size_t n_frames) {
    float gain = state->gain;
    const float target = state->target;
    const float coef = state->coef;
    for (size_t i = 0; i < n_frames; ++i) {
        gain += coef * (target - gain);
        out[i] = in[i] * gain;
    }
    /* A float32 one-pole stalls short of its target: once coef * (target - gain) is under
     * half a unit in the last place of the gain, adding it changes nothing. With a 5 ms time
     * constant at 48 kHz it stops 3.6e-6 away (-109 dBFS). When that has happened, finish the
     * move, so a settled gain is exactly the value that was set. */
    if (gain + coef * (target - gain) == gain) {
        gain = target;
    }
    state->gain = gain;
}
