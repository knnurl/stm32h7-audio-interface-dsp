#include "dsp/dsp_gate.h"

#include <math.h>
#include <string.h>

void dsp_gate_f32_set_params(DspGateF32 *gate, const DspGateParams *params) {
    gate->params = *params;
    const float fs = gate->sample_rate_hz;
    gate->detector.attack_coef = 0.0f;
    gate->detector.release_coef = dsp_env_coef(fs, params->detector_release_ms);
    gate->close_db = params->open_db - (params->hysteresis_db > 0.0f ? params->hysteresis_db : 0.0f);
    gate->open_lin = powf(10.0f, params->open_db / 20.0f);
    gate->close_lin = powf(10.0f, gate->close_db / 20.0f);
    gate->hold_samples = (int32_t)(params->hold_ms * 0.001f * fs + 0.5f);
    gate->closed_gain = powf(10.0f, (params->range_db < 0.0f ? params->range_db : 0.0f) / 20.0f);
    gate->open_coef = dsp_env_coef(fs, params->attack_ms);
    gate->close_coef = dsp_env_coef(fs, params->release_ms);
}

void dsp_gate_f32_init(DspGateF32 *gate, float sample_rate_hz, const DspGateParams *params) {
    memset(gate, 0, sizeof(*gate));
    gate->sample_rate_hz = sample_rate_hz;
    dsp_gate_f32_set_params(gate, params);
    dsp_gate_f32_reset(gate);
}

void dsp_gate_f32_reset(DspGateF32 *gate) {
    gate->detector.env = 0.0f;
    gate->open = 0;
    gate->hold_left = 0;
    gate->transitions = 0;
    gate->gain = gate->closed_gain;
}

void dsp_gate_f32_process(DspGateF32 *gate, const float *in, float *out, size_t n_frames) {
    float env = gate->detector.env;
    const float release = gate->detector.release_coef;
    float gain = gate->gain;
    for (size_t i = 0; i < n_frames; ++i) {
        const float x = in[i];
        const float ax = fabsf(x);
        env = ax > env ? ax : ax + release * (env - ax);
        if (gate->open) {
            if (env < gate->close_lin) {
                if (gate->hold_left > 0) {
                    --gate->hold_left;
                } else {
                    gate->open = 0;
                    ++gate->transitions;
                }
            } else {
                gate->hold_left = gate->hold_samples;
            }
        } else if (env >= gate->open_lin) {
            gate->open = 1;
            gate->hold_left = gate->hold_samples;
            ++gate->transitions;
        }
        const float target = gate->open ? 1.0f : gate->closed_gain;
        const float c = gate->open ? gate->open_coef : gate->close_coef;
        gain = target + c * (gain - target);
        out[i] = x * gain;
    }
    gate->detector.env = env;
    gate->gain = gain;
}
