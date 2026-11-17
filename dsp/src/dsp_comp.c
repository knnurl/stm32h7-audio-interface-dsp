#include "dsp/dsp_comp.h"

#include "dsp/dsp_coef.h"
#include "dsp/dsp_env.h"
#include "dsp/dsp_fastmath.h"

#include <math.h>
#include <string.h>

static float gain_computer(float slope, float threshold_db, float knee_db, float x_db) {
    const float over = x_db - threshold_db;
    if (2.0f * over < -knee_db) {
        return x_db;
    }
    if (knee_db > 0.0f && 2.0f * over <= knee_db) {
        const float k = over + 0.5f * knee_db;
        return x_db + slope * k * k / (2.0f * knee_db);
    }
    return threshold_db + over * (slope + 1.0f);
}

void dsp_comp_f32_set_params(DspCompF32 *comp, const DspCompParams *params) {
    comp->params = *params;
    if (comp->params.ratio < 1.0f) {
        comp->params.ratio = 1.0f;
    }
    if (comp->params.knee_db < 0.0f) {
        comp->params.knee_db = 0.0f;
    }
    comp->slope = 1.0f / comp->params.ratio - 1.0f;
    comp->attack_coef = dsp_env_coef(comp->sample_rate_hz, params->attack_ms);
    comp->release_coef = dsp_env_coef(comp->sample_rate_hz, params->release_ms);
    const int32_t was_on = comp->hpf_on;
    comp->hpf_on = params->sidechain_hpf_hz > 0.0f;
    if (comp->hpf_on) {
        DspBiquadCoefsD d;
        dsp_coef_highpass(&d, comp->sample_rate_hz, params->sidechain_hpf_hz,
                          0.70710678118654752);
        dsp_coef_to_f32(&d, &comp->hpf);
        if (!was_on) {
            memset(&comp->hpf_state, 0, sizeof(comp->hpf_state));
        }
    }
}

void dsp_comp_f32_init(DspCompF32 *comp, float sample_rate_hz, const DspCompParams *params) {
    memset(comp, 0, sizeof(*comp));
    comp->sample_rate_hz = sample_rate_hz;
    dsp_comp_f32_set_params(comp, params);
}

void dsp_comp_f32_reset(DspCompF32 *comp) {
    comp->reduction_db = 0.0f;
    memset(&comp->hpf_state, 0, sizeof(comp->hpf_state));
}

float dsp_comp_f32_static_db(const DspCompF32 *comp, float level_db) {
    return gain_computer(comp->slope, comp->params.threshold_db, comp->params.knee_db, level_db) +
           comp->params.makeup_db;
}

void dsp_comp_f32_process(DspCompF32 *comp, const float *in, float *out, size_t n_frames) {
    const float slope = comp->slope;
    const float threshold = comp->params.threshold_db;
    const float knee = comp->params.knee_db;
    const float makeup = comp->params.makeup_db;
    const float a = comp->attack_coef, r = comp->release_coef;
    float y_l = comp->reduction_db;
    for (size_t i = 0; i < n_frames; ++i) {
        const float x = in[i];
        float sc = x;
        if (comp->hpf_on) {
            dsp_biquad_f32_section(&comp->hpf, &comp->hpf_state, &x, &sc, 1);
            if (!isfinite(comp->hpf_state.z1) || !isfinite(comp->hpf_state.z2)) {
                memset(&comp->hpf_state, 0, sizeof(comp->hpf_state)); /* NaN in: recover. */
                sc = 0.0f;
            }
        }
        if (!isfinite(y_l)) {
            y_l = 0.0f;
        }
        const float x_db = dsp_fast_lin_to_db(sc);
        const float x_l = x_db - gain_computer(slope, threshold, knee, x_db);
        const float c = x_l > y_l ? a : r;
        y_l = x_l + c * (y_l - x_l);
        out[i] = x * dsp_fast_db_to_lin(makeup - y_l);
    }
    comp->reduction_db = y_l;
}
