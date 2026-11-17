#include "dsp/dsp_fx_echo.h"

#include <math.h>

static const float kGlideMs = 50.0f;

static int32_t is_half_rate(float sample_rate_hz) { return sample_rate_hz > 50000.0f; }

int32_t dsp_fx_echo_f32_mem_needed(float sample_rate_hz, float seconds) {
    const float rate = is_half_rate(sample_rate_hz) ? 0.5f * sample_rate_hz : sample_rate_hz;
    const int32_t per_line = (int32_t)(seconds * rate) + 4; /* int16 samples */
    const int32_t floats_per_line = (per_line + 1) / 2;
    return 2 * floats_per_line;
}

int32_t dsp_fx_echo_f32_init(DspFxEchoF32 *fx, float sample_rate_hz, float *mem, int32_t mem_len) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->half_rate = is_half_rate(sample_rate_hz);
    fx->rate_hz = fx->half_rate ? 0.5f * sample_rate_hz : sample_rate_hz;
    fx->dry = 1.0f;
    int32_t length;
    const float *taps = dsp_halfband_stage1(&length);
    for (int ch = 0; ch < 2; ++ch) {
        dsp_halfband_down_init(&fx->down[ch], taps, length);
        dsp_halfband_up_init(&fx->up[ch], taps, length);
    }
    const int32_t half = mem_len / 2; /* Floats per line. */
    const int32_t samples = 2 * half; /* int16 samples per line. */
    if (mem == NULL || (float)samples < 0.010f * fx->rate_hz + 4.0f ||
        dsp_delayline_s16_init(&fx->line[0], mem, samples) != 0 ||
        dsp_delayline_s16_init(&fx->line[1], mem + half, samples) != 0) {
        fx->max_delay = 0.0f;
        return -1;
    }
    fx->max_delay = (float)(samples - 4);
    fx->ping_pong = 0;
    fx->glide_left = 0;
    fx->glide_step = 0.0f;
    fx->delay = fx->delay_target = 2.0f;
    dsp_fx_echo_f32_set_time_ms(fx, 250.0f);
    dsp_fx_echo_f32_set_feedback(fx, 0.4f);
    dsp_fx_echo_f32_set_tone(fx, 0.7f);
    fx->hp[0].a = fx->hp[1].a = dsp_onepole_coef(fx->rate_hz, 80.0f);
    dsp_ramp_jump(&fx->wet, 0.5f);
    dsp_fx_echo_f32_reset(fx, 1);
    return 0;
}

void dsp_fx_echo_f32_reset(DspFxEchoF32 *fx, int32_t clear_memory) {
    for (int ch = 0; ch < 2; ++ch) {
        if (clear_memory) {
            dsp_delayline_s16_reset(&fx->line[ch]);
        } else {
            fx->line[ch].write = 0;
        }
        fx->lp[ch].z = 0.0f;
        fx->hp[ch].z = 0.0f;
        dsp_halfband_down_reset(&fx->down[ch]);
        dsp_halfband_up_reset(&fx->up[ch]);
        fx->in_hold[ch] = 0.0f;
        fx->out_hold[ch] = 0.0f;
    }
    fx->in_has = 0;
    fx->out_has = 1; /* The one-sample output hold starts primed (see the header). */
    fx->delay = fx->delay_target;
    fx->glide_left = 0;
}

void dsp_fx_echo_f32_set_amount(DspFxEchoF32 *fx, float amount) {
    amount = amount >= 0.0f ? (amount > 1.0f ? 1.0f : amount) : 0.0f;
    dsp_ramp_set(&fx->wet, amount, (int32_t)(DSP_FX_RAMP_MS * 0.001f * fx->sample_rate_hz));
}

void dsp_fx_echo_f32_set_time_ms(DspFxEchoF32 *fx, float time_ms) {
    /* Read before write costs one internal sample; at half rate the resamplers' delay comes off
     * as well, so the repeat lands at the set time at the output. */
    float d;
    if (fx->half_rate) {
        d = 0.5f * (time_ms * fx->sample_rate_hz / 1000.0f - DSP_ECHO_RESAMPLE_LATENCY) - 1.0f;
    } else {
        d = time_ms * fx->sample_rate_hz / 1000.0f - 1.0f;
    }
    if (!(d >= 2.0f)) {
        d = 2.0f;
    } else if (d > fx->max_delay) {
        d = fx->max_delay;
    }
    /* At rest the read is a whole number of internal samples: a fractional Lagrange read is a
     * low-pass (at a fraction of 0.5, -5.3 dB at 18 kHz at 48 kHz), and the repeats would come
     * back dull. The time is then within half an internal sample of the setting (one sample at
     * 96 kHz). Glides still pass through fractional positions. */
    d = floorf(d + 0.5f);
    if (d == fx->delay_target) {
        return;
    }
    fx->delay_target = d;
    const int32_t n = (int32_t)(kGlideMs * 0.001f * fx->rate_hz);
    fx->glide_left = n;
    fx->glide_step = (d - fx->delay) / (float)n;
}

void dsp_fx_echo_f32_set_feedback(DspFxEchoF32 *fx, float feedback) {
    fx->feedback = feedback >= 0.0f ? (feedback > 0.95f ? 0.95f : feedback) : 0.0f;
}

void dsp_fx_echo_f32_set_tone(DspFxEchoF32 *fx, float tone) {
    tone = tone >= 0.0f ? (tone > 1.0f ? 1.0f : tone) : 0.0f;
    const float fc = 1500.0f * powf(12.0f, tone);
    fx->lp[0].a = fx->lp[1].a = dsp_onepole_coef(fx->rate_hz, fc);
}

void dsp_fx_echo_f32_set_ping_pong(DspFxEchoF32 *fx, int32_t on) { fx->ping_pong = on != 0; }

float dsp_fx_echo_f32_max_time_ms(const DspFxEchoF32 *fx) {
    if (fx->half_rate) {
        return (2.0f * (fx->max_delay + 1.0f) + DSP_ECHO_RESAMPLE_LATENCY) * 1000.0f /
               fx->sample_rate_hz;
    }
    return (fx->max_delay + 1.0f) * 1000.0f / fx->sample_rate_hz;
}

/* One sample of the core at its own rate: the line outputs, before the wet gain. */
static void core(DspFxEchoF32 *fx, float xl, float xr, float *rl_out, float *rr_out) {
    if (fx->glide_left > 0) {
        /* From the target back, not by accumulating the step: a float32 sum drifted 0.4
         * samples over a 50 ms glide and then jumped to the target. */
        --fx->glide_left;
        fx->delay = fx->delay_target - fx->glide_step * (float)fx->glide_left;
    }
    const float fb = fx->feedback;
    const float rl = dsp_delayline_s16_read_lagrange(&fx->line[0], fx->delay);
    const float rr = dsp_delayline_s16_read_lagrange(&fx->line[1], fx->delay);
    const float fl = dsp_onepole_hp(&fx->hp[0], dsp_onepole_lp(&fx->lp[0], rl));
    const float fr = dsp_onepole_hp(&fx->hp[1], dsp_onepole_lp(&fx->lp[1], rr));
    if (fx->ping_pong) {
        dsp_delayline_s16_push(&fx->line[0], 0.5f * (xl + xr) + fb * fr);
        dsp_delayline_s16_push(&fx->line[1], fb * fl);
    } else {
        dsp_delayline_s16_push(&fx->line[0], xl + fb * fl);
        dsp_delayline_s16_push(&fx->line[1], xr + fb * fr);
    }
    *rl_out = rl;
    *rr_out = rr;
}

void dsp_fx_echo_f32_process(DspFxEchoF32 *fx, const float *in_l, const float *in_r,
                             float *wet_l, float *wet_r, size_t n_frames) {
    if (!fx->half_rate) {
        for (size_t i = 0; i < n_frames; ++i) {
            float rl, rr;
            core(fx, in_l[i], in_r[i], &rl, &rr);
            const float w = dsp_ramp_next(&fx->wet);
            wet_l[i] = w * rl;
            wet_r[i] = w * rr;
        }
        return;
    }
    /* Half rate. Inputs are paired (one may wait in in_hold); each pair gives one core sample
     * and, after the up filter, two outputs. One output always waits in out_hold or is due:
     * outputs on hand = n + 1 - in_has at the end of every call, so any block size works. */
    const float *in[2] = {in_l, in_r};
    float *wet[2] = {wet_l, wet_r};
    size_t used = 0;
    size_t emitted = 0;
    if (fx->out_has && n_frames > 0) {
        const float w = dsp_ramp_next(&fx->wet);
        wet_l[0] = w * fx->out_hold[0];
        wet_r[0] = w * fx->out_hold[1];
        fx->out_has = 0;
        emitted = 1;
    }
    for (;;) {
        const size_t available = (size_t)fx->in_has + (n_frames - used);
        size_t pairs = available / 2;
        if (pairs > kDspEchoChunk) {
            pairs = kDspEchoChunk;
        }
        if (pairs == 0) {
            if (available == 1 && !fx->in_has) {
                fx->in_hold[0] = in_l[used];
                fx->in_hold[1] = in_r[used];
                fx->in_has = 1;
                ++used;
            }
            break;
        }
        const size_t take = 2 * pairs - (size_t)fx->in_has;
        for (int ch = 0; ch < 2; ++ch) {
            size_t k = 0;
            if (fx->in_has) {
                fx->hi[ch][k++] = fx->in_hold[ch];
            }
            for (size_t i = 0; i < take; ++i) {
                fx->hi[ch][k++] = in[ch][used + i];
            }
            dsp_halfband_down_process(&fx->down[ch], fx->hi[ch], fx->lo_in[ch], pairs);
        }
        used += take;
        fx->in_has = 0;
        for (size_t j = 0; j < pairs; ++j) {
            core(fx, fx->lo_in[0][j], fx->lo_in[1][j], &fx->lo_out[0][j], &fx->lo_out[1][j]);
        }
        for (int ch = 0; ch < 2; ++ch) {
            dsp_halfband_up_process(&fx->up[ch], fx->lo_out[ch], fx->hi[ch], pairs);
        }
        for (size_t k = 0; k < 2 * pairs; ++k) {
            if (emitted < n_frames) {
                const float w = dsp_ramp_next(&fx->wet);
                wet[0][emitted] = w * fx->hi[0][k];
                wet[1][emitted] = w * fx->hi[1][k];
                ++emitted;
            } else {
                fx->out_hold[0] = fx->hi[0][k];
                fx->out_hold[1] = fx->hi[1][k];
                fx->out_has = 1;
            }
        }
    }
}
