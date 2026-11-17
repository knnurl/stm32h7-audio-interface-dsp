#include "dsp/dsp_fx_mod.h"

#include "dsp/dsp_fastmath.h"
#include "dsp/dsp_svf.h"

static float clamp01(float v) { return v >= 0.0f ? (v > 1.0f ? 1.0f : v) : 0.0f; }

static float clamp_fb(float v) { return v >= -0.9f ? (v > 0.9f ? 0.9f : v) : -0.9f; }

static int32_t ramp_samples(float sample_rate_hz) {
    return (int32_t)(DSP_FX_RAMP_MS * 0.001f * sample_rate_hz);
}

static int32_t stereo_lines(DspDelaylineF32 line[2], float *mem, int32_t mem_len, int32_t need) {
    if (mem == NULL || mem_len < need) {
        return -1;
    }
    const int32_t half = need / 2;
    if (dsp_delayline_f32_init(&line[0], mem, half) != 0 ||
        dsp_delayline_f32_init(&line[1], mem + half, half) != 0) {
        return -1;
    }
    return 0;
}

static void reset_lines(DspDelaylineF32 line[2], int32_t clear_memory) {
    for (int ch = 0; ch < 2; ++ch) {
        if (clear_memory) {
            dsp_delayline_f32_reset(&line[ch]);
        } else {
            line[ch].write = 0;
        }
    }
}

/* ---- Chorus ----------------------------------------------------------------------------------- */

int32_t dsp_fx_chorus_f32_mem_needed(float sample_rate_hz) {
    return 2 * ((int32_t)(0.028f * sample_rate_hz) + 4);
}

int32_t dsp_fx_chorus_f32_init(DspFxChorusF32 *fx, float sample_rate_hz, float *mem,
                               int32_t mem_len) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 1.0f;
    dsp_lfo_f32_init(&fx->lfo, sample_rate_hz, kDspLfoSine);
    dsp_lfo_f32_set_rate(&fx->lfo, 0.8f);
    dsp_fx_chorus_f32_set_spread(fx, 1.0f);
    dsp_ramp_jump(&fx->amount, 0.5f);
    if (stereo_lines(fx->line, mem, mem_len, dsp_fx_chorus_f32_mem_needed(sample_rate_hz)) != 0) {
        return -1;
    }
    dsp_fx_chorus_f32_reset(fx, 1);
    return 0;
}

void dsp_fx_chorus_f32_reset(DspFxChorusF32 *fx, int32_t clear_memory) {
    reset_lines(fx->line, clear_memory);
    dsp_lfo_f32_set_phase(&fx->lfo, 0.0);
}

void dsp_fx_chorus_f32_set_amount(DspFxChorusF32 *fx, float amount) {
    dsp_ramp_set(&fx->amount, clamp01(amount), ramp_samples(fx->sample_rate_hz));
}

void dsp_fx_chorus_f32_set_spread(DspFxChorusF32 *fx, float spread) {
    fx->right_offset = (uint32_t)(clamp01(spread) * 0.25f * 4294967296.0f);
}

void dsp_fx_chorus_f32_process(DspFxChorusF32 *fx, const float *in_l, const float *in_r,
                               float *wet_l, float *wet_r, size_t n_frames) {
    const float centre = 0.020f * fx->sample_rate_hz - 1.0f; /* Read before write: d - 1. */
    const float depth_max = 0.007f * fx->sample_rate_hz;
    const uint32_t half_cycle = 0x80000000u;
    for (size_t i = 0; i < n_frames; ++i) {
        const float a = dsp_ramp_next(&fx->amount);
        const float depth = a * depth_max;
        const uint32_t p = fx->lfo.phase;
        const float m0 = dsp_lfo_f32_value_at(&fx->lfo, p);
        const float m1 = dsp_lfo_f32_value_at(&fx->lfo, p + half_cycle);
        const float m2 = dsp_lfo_f32_value_at(&fx->lfo, p + fx->right_offset);
        const float m3 = dsp_lfo_f32_value_at(&fx->lfo, p + fx->right_offset + half_cycle);
        fx->lfo.phase += fx->lfo.inc;
        const float l = 0.5f * (dsp_delayline_f32_read_lagrange(&fx->line[0], centre + depth * m0) +
                                dsp_delayline_f32_read_lagrange(&fx->line[0], centre + depth * m1));
        const float r = 0.5f * (dsp_delayline_f32_read_lagrange(&fx->line[1], centre + depth * m2) +
                                dsp_delayline_f32_read_lagrange(&fx->line[1], centre + depth * m3));
        dsp_delayline_f32_push(&fx->line[0], in_l[i]);
        dsp_delayline_f32_push(&fx->line[1], in_r[i]);
        wet_l[i] = 0.7f * a * l;
        wet_r[i] = 0.7f * a * r;
    }
}

/* ---- Flanger ---------------------------------------------------------------------------------- */

int32_t dsp_fx_flanger_f32_mem_needed(float sample_rate_hz) {
    return 2 * ((int32_t)(0.0105f * sample_rate_hz) + 4);
}

int32_t dsp_fx_flanger_f32_init(DspFxFlangerF32 *fx, float sample_rate_hz, float *mem,
                                int32_t mem_len) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 0.7f;
    dsp_lfo_f32_init(&fx->lfo, sample_rate_hz, kDspLfoTriangle);
    dsp_lfo_f32_set_rate(&fx->lfo, 0.25f);
    fx->feedback = 0.5f;
    dsp_ramp_jump(&fx->amount, 0.5f);
    if (stereo_lines(fx->line, mem, mem_len, dsp_fx_flanger_f32_mem_needed(sample_rate_hz)) !=
        0) {
        return -1;
    }
    dsp_fx_flanger_f32_reset(fx, 1);
    return 0;
}

void dsp_fx_flanger_f32_reset(DspFxFlangerF32 *fx, int32_t clear_memory) {
    reset_lines(fx->line, clear_memory);
    dsp_lfo_f32_set_phase(&fx->lfo, 0.0);
}

void dsp_fx_flanger_f32_set_amount(DspFxFlangerF32 *fx, float amount) {
    dsp_ramp_set(&fx->amount, clamp01(amount), ramp_samples(fx->sample_rate_hz));
}

void dsp_fx_flanger_f32_set_feedback(DspFxFlangerF32 *fx, float feedback) {
    fx->feedback = clamp_fb(feedback);
}

void dsp_fx_flanger_f32_process(DspFxFlangerF32 *fx, const float *in_l, const float *in_r,
                                float *wet_l, float *wet_r, size_t n_frames) {
    const float d_min = 0.0005f * fx->sample_rate_hz;
    const float span_max = 0.0095f * fx->sample_rate_hz;
    const float fb = fx->feedback;
    for (size_t i = 0; i < n_frames; ++i) {
        const float a = dsp_ramp_next(&fx->amount);
        const uint32_t p = fx->lfo.phase;
        const float ul = 0.5f + 0.5f * dsp_lfo_f32_value_at(&fx->lfo, p);
        const float ur = 0.5f + 0.5f * dsp_lfo_f32_value_at(&fx->lfo, p + 0x40000000u);
        fx->lfo.phase += fx->lfo.inc;
        const float rl =
            dsp_delayline_f32_read_lagrange(&fx->line[0], d_min - 1.0f + a * span_max * ul);
        const float rr =
            dsp_delayline_f32_read_lagrange(&fx->line[1], d_min - 1.0f + a * span_max * ur);
        dsp_delayline_f32_push(&fx->line[0], in_l[i] + fb * rl);
        dsp_delayline_f32_push(&fx->line[1], in_r[i] + fb * rr);
        wet_l[i] = 0.7f * rl;
        wet_r[i] = 0.7f * rr;
    }
}

/* ---- Phaser ----------------------------------------------------------------------------------- */

float dsp_fx_phaser_coef(float sample_rate_hz, float fc_hz) {
    const float t = dsp_svf_fast_g(sample_rate_hz, fc_hz);
    return (t - 1.0f) / (t + 1.0f);
}

void dsp_fx_phaser_f32_init(DspFxPhaserF32 *fx, float sample_rate_hz) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 0.5f;
    dsp_lfo_f32_init(&fx->lfo, sample_rate_hz, kDspLfoSine);
    dsp_lfo_f32_set_rate(&fx->lfo, 0.3f);
    fx->stages = 4;
    fx->feedback = 0.3f;
    dsp_ramp_jump(&fx->amount, 0.5f);
    dsp_fx_phaser_f32_reset(fx);
}

void dsp_fx_phaser_f32_reset(DspFxPhaserF32 *fx) {
    for (int ch = 0; ch < 2; ++ch) {
        for (int k = 0; k < kDspPhaserMaxStages; ++k) {
            fx->state[ch][k] = 0.0f;
        }
        fx->last[ch] = 0.0f;
        fx->coef[ch] = dsp_fx_phaser_coef(fx->sample_rate_hz, 200.0f);
    }
    dsp_lfo_f32_set_phase(&fx->lfo, 0.0);
}

void dsp_fx_phaser_f32_set_amount(DspFxPhaserF32 *fx, float amount) {
    dsp_ramp_set(&fx->amount, clamp01(amount), ramp_samples(fx->sample_rate_hz));
}

void dsp_fx_phaser_f32_set_stages(DspFxPhaserF32 *fx, int32_t stages) {
    fx->stages = stages >= 8 ? 8 : 4;
}

void dsp_fx_phaser_f32_set_feedback(DspFxPhaserF32 *fx, float feedback) {
    fx->feedback = clamp_fb(feedback);
}

void dsp_fx_phaser_f32_process(DspFxPhaserF32 *fx, const float *in_l, const float *in_r,
                               float *wet_l, float *wet_r, size_t n_frames) {
    const float *in[2] = {in_l, in_r};
    float *wet[2] = {wet_l, wet_r};
    const float fb = fx->feedback;
    for (size_t start = 0; start < n_frames; start += kDspFxSubBlock) {
        const size_t n = n_frames - start < kDspFxSubBlock ? n_frames - start : kDspFxSubBlock;
        /* The sweep position at the start of the sub-block sets c for all of it. */
        float a = 0.0f;
        for (size_t i = 0; i < n; ++i) {
            a = dsp_ramp_next(&fx->amount);
        }
        const uint32_t p = fx->lfo.phase;
        fx->lfo.phase += fx->lfo.inc * (uint32_t)n;
        for (int ch = 0; ch < 2; ++ch) {
            const float u = 0.5f + 0.5f * dsp_lfo_f32_value_at(&fx->lfo, p + (ch ? 0x40000000u : 0u));
            const float fc = 200.0f * dsp_fast_exp2f(5.0f * a * u);
            const float c = dsp_fx_phaser_coef(fx->sample_rate_hz, fc);
            fx->coef[ch] = c;
            float *s = fx->state[ch];
            for (size_t i = 0; i < n; ++i) {
                float v = in[ch][start + i] + fb * fx->last[ch];
                for (int32_t k = 0; k < fx->stages; ++k) {
                    const float y = c * v + s[k];
                    s[k] = v - c * y;
                    v = y;
                }
                fx->last[ch] = v;
                wet[ch][start + i] = 0.5f * v;
            }
        }
    }
}
