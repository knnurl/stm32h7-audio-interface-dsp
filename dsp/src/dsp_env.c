#include "dsp/dsp_env.h"

#include <math.h>

float dsp_env_coef(float sample_rate_hz, float time_ms) {
    if (time_ms <= 0.0f || sample_rate_hz <= 0.0f) {
        return 0.0f;
    }
    return expf(-1.0f / (time_ms * 0.001f * sample_rate_hz));
}

void dsp_env_peak_init(DspEnvF32 *env, float sample_rate_hz, float attack_ms, float release_ms) {
    env->attack_coef = dsp_env_coef(sample_rate_hz, attack_ms);
    env->release_coef = dsp_env_coef(sample_rate_hz, release_ms);
    env->env = 0.0f;
}

void dsp_env_rms_init(DspEnvF32 *env, float sample_rate_hz, float time_ms) {
    env->attack_coef = dsp_env_coef(sample_rate_hz, time_ms);
    env->release_coef = env->attack_coef;
    env->env = 0.0f;
}

void dsp_env_reset(DspEnvF32 *env) { env->env = 0.0f; }

void dsp_env_peak_process(DspEnvF32 *env, const float *in, float *out, size_t n_frames) {
    float e = env->env;
    const float a = env->attack_coef, r = env->release_coef;
    for (size_t i = 0; i < n_frames; ++i) {
        const float x = fabsf(in[i]);
        const float c = x > e ? a : r;
        e = x + c * (e - x);
        out[i] = e;
    }
    env->env = e;
}

void dsp_env_rms_process(DspEnvF32 *env, const float *in, float *out, size_t n_frames) {
    float ms = env->env; /* Mean square. */
    const float c = env->attack_coef;
    for (size_t i = 0; i < n_frames; ++i) {
        const float x2 = in[i] * in[i];
        ms = x2 + c * (ms - x2);
        out[i] = sqrtf(ms);
    }
    env->env = ms;
}
