#include "dsp/dsp_crossfeed.h"

void dsp_crossfeed_f32_init(DspCrossfeedF32 *xf, float sample_rate_hz, float ramp_ms) {
    xf->sample_rate_hz = sample_rate_hz;
    xf->ramp_samples = (int32_t)(ramp_ms * 0.001f * sample_rate_hz + 0.5f);
    dsp_ramp_jump(&xf->g, 0.0f);
    dsp_ramp_jump(&xf->norm, 1.0f);
    dsp_crossfeed_f32_set_cutoff(xf, 700.0f);
    dsp_crossfeed_f32_set_delay_us(xf, 0.0f);
    dsp_crossfeed_f32_reset(xf);
}

void dsp_crossfeed_f32_reset(DspCrossfeedF32 *xf) {
    for (int ch = 0; ch < 2; ++ch) {
        xf->lp[ch].z = 0.0f;
        for (int32_t i = 0; i < kDspCrossfeedRing; ++i) {
            xf->ring[ch][i] = 0.0f;
        }
    }
    xf->pos = 0;
    dsp_ramp_jump(&xf->g, xf->g.target);
    dsp_ramp_jump(&xf->norm, xf->norm.target);
}

void dsp_crossfeed_f32_set_amount(DspCrossfeedF32 *xf, float amount) {
    const float a = amount < 0.0f ? 0.0f : (amount > 1.0f ? 1.0f : amount);
    const float g = a * DSP_CROSSFEED_MAX_GAIN;
    dsp_ramp_set(&xf->g, g, xf->ramp_samples);
    dsp_ramp_set(&xf->norm, 1.0f / (1.0f + g), xf->ramp_samples);
}

void dsp_crossfeed_f32_set_cutoff(DspCrossfeedF32 *xf, float fc_hz) {
    const float a = dsp_onepole_coef(xf->sample_rate_hz, fc_hz);
    xf->lp[0].a = a;
    xf->lp[1].a = a;
}

void dsp_crossfeed_f32_set_delay_us(DspCrossfeedF32 *xf, float delay_us) {
    int32_t d = (int32_t)(delay_us * 1e-6f * xf->sample_rate_hz + 0.5f);
    xf->delay = d < 0 ? 0 : (d > kDspCrossfeedRing - 1 ? kDspCrossfeedRing - 1 : d);
}

void dsp_crossfeed_f32_process(DspCrossfeedF32 *xf, const float *in_l, const float *in_r,
                               float *out_l, float *out_r, size_t n_frames) {
    const int32_t mask = kDspCrossfeedRing - 1;
    const int32_t still = !dsp_ramp_moving(&xf->g);
    const int32_t bypass = still && xf->g.cur == 0.0f;
    int32_t pos = xf->pos;
    for (size_t i = 0; i < n_frames; ++i) {
        const float xl = in_l[i], xr = in_r[i];
        const float lpl = dsp_onepole_lp(&xf->lp[0], xl);
        const float lpr = dsp_onepole_lp(&xf->lp[1], xr);
        xf->ring[0][pos] = lpl;
        xf->ring[1][pos] = lpr;
        const int32_t back = (pos - xf->delay) & mask;
        pos = (pos + 1) & mask;
        if (bypass) {
            out_l[i] = xl;
            out_r[i] = xr;
            continue;
        }
        const float g = dsp_ramp_next(&xf->g);
        const float n = dsp_ramp_next(&xf->norm);
        const float g1 = 1.0f + g;
        out_l[i] = n * (g1 * xl - g * lpl + g * xf->ring[1][back]);
        out_r[i] = n * (g1 * xr - g * lpr + g * xf->ring[0][back]);
    }
    xf->pos = pos;
}
