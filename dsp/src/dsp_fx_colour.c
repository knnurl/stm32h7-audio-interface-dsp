#include "dsp/dsp_fx_colour.h"

#include "dsp/dsp_fastmath.h"

#include <math.h>

static float clamp01(float v) { return v >= 0.0f ? (v > 1.0f ? 1.0f : v) : 0.0f; }

static int32_t ramp_samples(float sample_rate_hz) {
    return (int32_t)(DSP_FX_RAMP_MS * 0.001f * sample_rate_hz);
}

/* Advances a ramp by n samples; returns its value at the end. */
static float ramp_advance(DspRampF32 *r, size_t n) {
    float v = r->cur;
    for (size_t i = 0; i < n; ++i) {
        v = dsp_ramp_next(r);
    }
    return v;
}

/* ---- Sweep filter ----------------------------------------------------------------------------- */

void dsp_fx_sweep_map(float position, int32_t *mode, float *fc_hz, float *blend) {
    const float p = clamp01(position);
    const float off = p - 0.5f;
    const float dist = off < 0.0f ? -off : off;
    float b = (dist - 0.03f) / 0.07f;
    b = b < 0.0f ? 0.0f : (b > 1.0f ? 1.0f : b);
    *blend = b;
    if (dist <= 0.03f) {
        *mode = -1;
        *fc_hz = 0.0f;
    } else if (off < 0.0f) {
        *mode = kDspSvfLow;
        /* 20 kHz x (50 / 20000)^t = 20 kHz x 2^(t log2(0.0025)), t = (0.47 - p) / 0.47. */
        *fc_hz = 20000.0f * dsp_fast_exp2f(-8.643856f * (0.47f - p) / 0.47f);
    } else {
        *mode = kDspSvfHigh;
        *fc_hz = 20.0f * dsp_fast_exp2f(8.965784f * (p - 0.53f) / 0.47f);
    }
}

void dsp_fx_sweep_f32_init(DspFxSweepF32 *fx, float sample_rate_hz) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 0.0f;
    fx->q = 0.9f;
    dsp_ramp_jump(&fx->position, 0.5f);
    dsp_svf_f32_init(&fx->svf[0], sample_rate_hz, 1000.0f, fx->q);
    dsp_svf_f32_init(&fx->svf[1], sample_rate_hz, 1000.0f, fx->q);
}

void dsp_fx_sweep_f32_reset(DspFxSweepF32 *fx) {
    dsp_svf_f32_reset(&fx->svf[0]);
    dsp_svf_f32_reset(&fx->svf[1]);
}

void dsp_fx_sweep_f32_set_amount(DspFxSweepF32 *fx, float position) {
    dsp_ramp_set(&fx->position, clamp01(position), ramp_samples(fx->sample_rate_hz));
}

void dsp_fx_sweep_f32_set_resonance(DspFxSweepF32 *fx, float q) {
    fx->q = q >= 0.5f ? (q > 8.0f ? 8.0f : q) : 0.5f;
}

void dsp_fx_sweep_f32_process(DspFxSweepF32 *fx, const float *in_l, const float *in_r,
                              float *wet_l, float *wet_r, size_t n_frames) {
    const float *in[2] = {in_l, in_r};
    float *wet[2] = {wet_l, wet_r};
    for (size_t start = 0; start < n_frames; start += kDspFxSubBlock) {
        const size_t n = n_frames - start < kDspFxSubBlock ? n_frames - start : kDspFxSubBlock;
        int32_t mode;
        float fc, blend;
        dsp_fx_sweep_map(ramp_advance(&fx->position, n), &mode, &fc, &blend);
        for (int ch = 0; ch < 2; ++ch) {
            DspSvfF32 *svf = &fx->svf[ch];
            if (mode < 0) {
                /* Off: keep the filter's state quiet so a later entry starts clean. */
                dsp_svf_f32_reset(svf);
                for (size_t i = 0; i < n; ++i) {
                    wet[ch][start + i] = in[ch][start + i];
                }
                continue;
            }
            dsp_svf_f32_set_fast(svf, fx->sample_rate_hz, fc, fx->q);
            for (size_t i = 0; i < n; ++i) {
                const float x = in[ch][start + i];
                const float y = dsp_svf_f32_tick(svf, mode, x);
                wet[ch][start + i] = x + blend * (y - x);
            }
        }
    }
}

/* ---- Overdrive -------------------------------------------------------------------------------- */

static const float kBias = 0.3f;

void dsp_fx_overdrive_f32_init(DspFxOverdriveF32 *fx, float sample_rate_hz) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 0.0f;
    fx->asymmetric = 0;
    fx->level = 1.0f;
    /* Compensation: a -18 dBFS sine (peak 0.126) keeps its RMS at every whole dB of drive. */
    const float amp = 0.12589254f;
    for (int32_t k = 0; k < kDspOverdriveTable; ++k) {
        const float d = powf(10.0f, (float)k / 20.0f);
        const float norm = 1.0f / tanhf(d);
        double sum = 0.0;
        for (int32_t j = 0; j < 64; ++j) {
            const float y = tanhf(d * amp * sinf(6.2831853f * ((float)j + 0.5f) / 64.0f)) * norm;
            sum += (double)y * (double)y;
        }
        fx->comp[k] = (float)((double)amp * 0.70710678 / sqrt(sum / 64.0));
    }
    dsp_ramp_jump(&fx->amount, 0.5f);
    fx->drive_db = 18.0f;
    for (int ch = 0; ch < 2; ++ch) {
        dsp_saturator_f32_init(&fx->sat[ch], kDspSatOs4, fx->drive_db);
        fx->pre[ch].a = dsp_onepole_coef(sample_rate_hz, 100.0f);
        fx->dc[ch].a = dsp_onepole_coef(sample_rate_hz, 10.0f);
    }
    dsp_fx_overdrive_f32_set_tone(fx, 0.6f);
    dsp_fx_overdrive_f32_reset(fx);
}

void dsp_fx_overdrive_f32_reset(DspFxOverdriveF32 *fx) {
    for (int ch = 0; ch < 2; ++ch) {
        dsp_saturator_f32_reset(&fx->sat[ch]);
        fx->pre[ch].z = fx->dc[ch].z = fx->post[ch].z = 0.0f;
    }
}

void dsp_fx_overdrive_f32_set_amount(DspFxOverdriveF32 *fx, float amount) {
    dsp_ramp_set(&fx->amount, clamp01(amount), ramp_samples(fx->sample_rate_hz));
}

void dsp_fx_overdrive_f32_set_tone(DspFxOverdriveF32 *fx, float tone) {
    const float fc = 1000.0f * powf(12.0f, clamp01(tone));
    fx->post[0].a = fx->post[1].a = dsp_onepole_coef(fx->sample_rate_hz, fc);
}

void dsp_fx_overdrive_f32_set_asymmetric(DspFxOverdriveF32 *fx, int32_t on) {
    fx->asymmetric = on != 0;
}

void dsp_fx_overdrive_f32_set_level_db(DspFxOverdriveF32 *fx, float level_db) {
    if (!(level_db >= -40.0f)) {
        level_db = -40.0f;
    } else if (level_db > 12.0f) {
        level_db = 12.0f;
    }
    fx->level = powf(10.0f, level_db / 20.0f);
}

float dsp_fx_overdrive_f32_latency(const DspFxOverdriveF32 *fx) {
    return dsp_saturator_f32_latency(&fx->sat[0]);
}

void dsp_fx_overdrive_f32_process(DspFxOverdriveF32 *fx, const float *in_l, const float *in_r,
                                  float *wet_l, float *wet_r, size_t n_frames) {
    const float *in[2] = {in_l, in_r};
    float *wet[2] = {wet_l, wet_r};
    for (size_t start = 0; start < n_frames; start += kDspFxSubBlock) {
        const size_t n = n_frames - start < kDspFxSubBlock ? n_frames - start : kDspFxSubBlock;
        const float drive_db = 36.0f * ramp_advance(&fx->amount, n);
        if (drive_db != fx->drive_db) {
            /* Only while the knob moves: powf and tanhf once per sub-block per channel. */
            fx->drive_db = drive_db;
            dsp_saturator_f32_set_drive(&fx->sat[0], drive_db);
            dsp_saturator_f32_set_drive(&fx->sat[1], drive_db);
        }
        const int32_t k = (int32_t)drive_db;
        const float frac = drive_db - (float)k;
        const float comp = k >= kDspOverdriveTable - 1
                               ? fx->comp[kDspOverdriveTable - 1]
                               : fx->comp[k] + frac * (fx->comp[k + 1] - fx->comp[k]);
        const float gain = comp * fx->level;
        const float bias = fx->asymmetric ? kBias / fx->sat[0].drive : 0.0f;
        for (int ch = 0; ch < 2; ++ch) {
            for (size_t i = 0; i < n; ++i) {
                fx->buf[i] = dsp_onepole_hp(&fx->pre[ch], in[ch][start + i]) + bias;
            }
            dsp_saturator_f32_process(&fx->sat[ch], fx->buf, fx->buf, n);
            for (size_t i = 0; i < n; ++i) {
                const float y = dsp_onepole_hp(&fx->dc[ch], fx->buf[i]);
                wet[ch][start + i] = gain * dsp_onepole_lp(&fx->post[ch], y);
            }
        }
    }
}

/* ---- Bit crusher ------------------------------------------------------------------------------ */

void dsp_fx_crusher_f32_init(DspFxCrusherF32 *fx, float sample_rate_hz) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 0.0f;
    fx->bits = 6.0f;
    fx->rate_hz = 6000.0f;
    fx->dither = 0;
    dsp_ramp_jump(&fx->amount, 0.5f);
    dsp_fx_crusher_f32_reset(fx);
}

void dsp_fx_crusher_f32_reset(DspFxCrusherF32 *fx) {
    fx->phase = 1.0f; /* Take a sample at once. */
    fx->held[0] = fx->held[1] = 0.0f;
    dsp_noise_seed(&fx->noise, 8u);
}

void dsp_fx_crusher_f32_set_amount(DspFxCrusherF32 *fx, float amount) {
    dsp_ramp_set(&fx->amount, clamp01(amount), ramp_samples(fx->sample_rate_hz));
}

void dsp_fx_crusher_f32_set_bits(DspFxCrusherF32 *fx, float bits) {
    fx->bits = bits >= 1.0f ? (bits > 16.0f ? 16.0f : bits) : 1.0f;
}

void dsp_fx_crusher_f32_set_rate(DspFxCrusherF32 *fx, float rate_hz) {
    const float lo = 100.0f;
    fx->rate_hz = rate_hz >= lo ? (rate_hz > fx->sample_rate_hz ? fx->sample_rate_hz : rate_hz) : lo;
}

void dsp_fx_crusher_f32_set_dither(DspFxCrusherF32 *fx, int32_t on) { fx->dither = on != 0; }

static float quantise(float x, float steps, float dither) {
    float v = x * steps + dither;
    /* Clamp; NaN goes to -steps, because the integer cast below would be undefined for it. */
    if (!(v >= -steps)) {
        v = -steps;
    } else if (v > steps) {
        v = steps;
    }
    const float r = (float)(int32_t)(v + (v >= 0.0f ? 0.5f : -0.5f));
    return r / steps;
}

void dsp_fx_crusher_f32_process(DspFxCrusherF32 *fx, const float *in_l, const float *in_r,
                                float *wet_l, float *wet_r, size_t n_frames) {
    const float log2_ratio = dsp_fast_log2f(fx->rate_hz / fx->sample_rate_hz);
    for (size_t start = 0; start < n_frames; start += kDspFxSubBlock) {
        const size_t n = n_frames - start < kDspFxSubBlock ? n_frames - start : kDspFxSubBlock;
        const float a = ramp_advance(&fx->amount, n);
        const float bits = 16.0f + a * (fx->bits - 16.0f);
        const float steps = dsp_fast_exp2f(bits - 1.0f);
        const float inc = dsp_fast_exp2f(a * log2_ratio); /* rate / fs, at most 1. */
        if (fx->dither) {
            dsp_noise_f32(&fx->noise, fx->rnd, 4 * n, 0.5f);
        }
        for (size_t i = 0; i < n; ++i) {
            fx->phase += inc;
            if (fx->phase >= 1.0f) {
                fx->phase -= 1.0f;
                const float dl = fx->dither ? fx->rnd[4 * i] + fx->rnd[4 * i + 1] : 0.0f;
                const float dr = fx->dither ? fx->rnd[4 * i + 2] + fx->rnd[4 * i + 3] : 0.0f;
                fx->held[0] = quantise(in_l[start + i], steps, dl);
                fx->held[1] = quantise(in_r[start + i], steps, dr);
            }
            wet_l[start + i] = fx->held[0];
            wet_r[start + i] = fx->held[1];
        }
    }
}
