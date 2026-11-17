/* Envelope followers.
 *
 * Peak: a branching one-pole on |x|, with an attack coefficient when the input is above the
 * envelope and a release coefficient when it is below.
 * RMS: a one-pole on x^2 with one time constant; the output is the square root.
 * Coefficients are exp(-1 / (tau fs)): `attack_ms` and `release_ms` are time constants (63 % of a
 * step), not times to settle.
 *
 * Assumptions: mono; the output is the envelope, linear, one value per input sample.
 * Latency: 0 samples. Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_ENV_H
#define DSP_ENV_H

#include <stddef.h>

typedef struct {
    float attack_coef;
    float release_coef;
    float env;
} DspEnvF32;

/* A one-pole coefficient for a time constant; 0 for a time of 0 ms or less (instant). */
float dsp_env_coef(float sample_rate_hz, float time_ms);

void dsp_env_peak_init(DspEnvF32 *env, float sample_rate_hz, float attack_ms, float release_ms);
void dsp_env_rms_init(DspEnvF32 *env, float sample_rate_hz, float time_ms);
void dsp_env_reset(DspEnvF32 *env);
void dsp_env_peak_process(DspEnvF32 *env, const float *in, float *out, size_t n_frames);
void dsp_env_rms_process(DspEnvF32 *env, const float *in, float *out, size_t n_frames);

#endif
