#include "dsp/dsp_svf.h"

#include <math.h>

static const float kPi = 3.14159265358979f;

static float clamp_fc(float sample_rate_hz, float fc_hz) {
    const float hi = 0.45f * sample_rate_hz;
    if (!(fc_hz >= 1.0f)) {
        return 1.0f; /* Also NaN. */
    }
    return fc_hz > hi ? hi : fc_hz;
}

static float clamp_q(float q) {
    if (!(q >= 0.1f)) {
        return 0.1f;
    }
    return q > 50.0f ? 50.0f : q;
}

static void set_gk(DspSvfF32 *svf, float g, float q) {
    svf->g = g;
    svf->k = 1.0f / clamp_q(q);
    svf->a1 = 1.0f / (1.0f + g * (g + svf->k));
    svf->a2 = g * svf->a1;
    svf->a3 = g * svf->a2;
}

void dsp_svf_f32_init(DspSvfF32 *svf, float sample_rate_hz, float fc_hz, float q) {
    dsp_svf_f32_set(svf, sample_rate_hz, fc_hz, q);
    dsp_svf_f32_reset(svf);
}

void dsp_svf_f32_reset(DspSvfF32 *svf) {
    svf->ic1 = 0.0f;
    svf->ic2 = 0.0f;
}

void dsp_svf_f32_set(DspSvfF32 *svf, float sample_rate_hz, float fc_hz, float q) {
    const float fc = clamp_fc(sample_rate_hz, fc_hz);
    set_gk(svf, tanf(kPi * fc / sample_rate_hz), q);
}

float dsp_svf_fast_g(float sample_rate_hz, float fc_hz) {
    const float x = kPi * clamp_fc(sample_rate_hz, fc_hz) / sample_rate_hz;
    const float x2 = x * x;
    return x * (15.0f - x2) / (15.0f - 6.0f * x2);
}

void dsp_svf_f32_set_fast(DspSvfF32 *svf, float sample_rate_hz, float fc_hz, float q) {
    set_gk(svf, dsp_svf_fast_g(sample_rate_hz, fc_hz), q);
}

void dsp_svf_f32_process(DspSvfF32 *svf, int32_t mode, const float *in, float *out,
                         size_t n_frames) {
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = dsp_svf_f32_tick(svf, mode, in[i]);
    }
}
