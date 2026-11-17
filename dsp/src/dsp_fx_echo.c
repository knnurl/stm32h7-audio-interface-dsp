#include "dsp/dsp_fx_echo.h"

#include <math.h>

static const float kGlideMs = 50.0f;

int32_t dsp_fx_echo_f32_init(DspFxEchoF32 *fx, float sample_rate_hz, float *mem, int32_t mem_len) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 1.0f;
    const int32_t half = mem_len / 2;
    if (mem == NULL || (float)half < 0.010f * sample_rate_hz + 4.0f ||
        dsp_delayline_f32_init(&fx->line[0], mem, half) != 0 ||
        dsp_delayline_f32_init(&fx->line[1], mem + half, half) != 0) {
        fx->max_delay = 0.0f;
        return -1;
    }
    fx->max_delay = (float)(half - 4);
    fx->delay = fx->delay_target = 0.25f * sample_rate_hz;
    if (fx->delay > fx->max_delay) {
        fx->delay = fx->delay_target = fx->max_delay;
    }
    fx->glide_left = 0;
    fx->glide_step = 0.0f;
    fx->ping_pong = 0;
    dsp_fx_echo_f32_set_feedback(fx, 0.4f);
    dsp_fx_echo_f32_set_tone(fx, 0.7f);
    fx->hp[0].a = fx->hp[1].a = dsp_onepole_coef(sample_rate_hz, 80.0f);
    dsp_ramp_jump(&fx->wet, 0.5f);
    dsp_fx_echo_f32_reset(fx, 1);
    return 0;
}

void dsp_fx_echo_f32_reset(DspFxEchoF32 *fx, int32_t clear_memory) {
    for (int ch = 0; ch < 2; ++ch) {
        if (clear_memory) {
            dsp_delayline_f32_reset(&fx->line[ch]);
        } else {
            fx->line[ch].write = 0;
        }
        fx->lp[ch].z = 0.0f;
        fx->hp[ch].z = 0.0f;
    }
    fx->delay = fx->delay_target;
    fx->glide_left = 0;
}

void dsp_fx_echo_f32_set_amount(DspFxEchoF32 *fx, float amount) {
    amount = amount >= 0.0f ? (amount > 1.0f ? 1.0f : amount) : 0.0f;
    dsp_ramp_set(&fx->wet, amount, (int32_t)(DSP_FX_RAMP_MS * 0.001f * fx->sample_rate_hz));
}

void dsp_fx_echo_f32_set_time_ms(DspFxEchoF32 *fx, float time_ms) {
    /* One sample is taken by the read-before-write order: a line read at d - 1 delays by d. */
    float d = time_ms * fx->sample_rate_hz / 1000.0f - 1.0f;
    if (!(d >= 2.0f)) {
        d = 2.0f;
    } else if (d > fx->max_delay) {
        d = fx->max_delay;
    }
    if (d == fx->delay_target) {
        return;
    }
    fx->delay_target = d;
    const int32_t n = (int32_t)(kGlideMs * 0.001f * fx->sample_rate_hz);
    fx->glide_left = n;
    fx->glide_step = (d - fx->delay) / (float)n;
}

void dsp_fx_echo_f32_set_feedback(DspFxEchoF32 *fx, float feedback) {
    fx->feedback = feedback >= 0.0f ? (feedback > 0.95f ? 0.95f : feedback) : 0.0f;
}

void dsp_fx_echo_f32_set_tone(DspFxEchoF32 *fx, float tone) {
    tone = tone >= 0.0f ? (tone > 1.0f ? 1.0f : tone) : 0.0f;
    const float fc = 1500.0f * powf(12.0f, tone);
    fx->lp[0].a = fx->lp[1].a = dsp_onepole_coef(fx->sample_rate_hz, fc);
}

void dsp_fx_echo_f32_set_ping_pong(DspFxEchoF32 *fx, int32_t on) { fx->ping_pong = on != 0; }

float dsp_fx_echo_f32_max_time_ms(const DspFxEchoF32 *fx) {
    return (fx->max_delay + 1.0f) * 1000.0f / fx->sample_rate_hz;
}

void dsp_fx_echo_f32_process(DspFxEchoF32 *fx, const float *in_l, const float *in_r,
                             float *wet_l, float *wet_r, size_t n_frames) {
    const float fb = fx->feedback;
    for (size_t i = 0; i < n_frames; ++i) {
        if (fx->glide_left > 0) {
            /* From the target back, not by accumulating the step: a float32 sum drifted 0.4
             * samples over a 50 ms glide and then jumped to the target. */
            --fx->glide_left;
            fx->delay = fx->delay_target - fx->glide_step * (float)fx->glide_left;
        }
        const float rl = dsp_delayline_f32_read_lagrange(&fx->line[0], fx->delay);
        const float rr = dsp_delayline_f32_read_lagrange(&fx->line[1], fx->delay);
        const float fl = dsp_onepole_hp(&fx->hp[0], dsp_onepole_lp(&fx->lp[0], rl));
        const float fr = dsp_onepole_hp(&fx->hp[1], dsp_onepole_lp(&fx->lp[1], rr));
        if (fx->ping_pong) {
            dsp_delayline_f32_push(&fx->line[0], 0.5f * (in_l[i] + in_r[i]) + fb * fr);
            dsp_delayline_f32_push(&fx->line[1], fb * fl);
        } else {
            dsp_delayline_f32_push(&fx->line[0], in_l[i] + fb * fl);
            dsp_delayline_f32_push(&fx->line[1], in_r[i] + fb * fr);
        }
        const float w = dsp_ramp_next(&fx->wet);
        wet_l[i] = w * rl;
        wet_r[i] = w * rr;
    }
}
