#include "dsp/dsp_reverb.h"

#include <math.h>

static const float kBaseMs[kDspReverbLines] = {19.3f, 23.9f, 27.1f, 31.7f,
                                               35.3f, 39.7f, 43.9f, 47.9f};
static const int32_t kModLine[2] = {2, 6};
static const float kModHz[2] = {0.31f, 0.43f};
static const float kModMs = 0.3f;
static const float kMaxPredelayMs = 100.0f;
/* Output sign patterns: orthogonal rows, so left and right are decorrelated. */
static const float kOutL[kDspReverbLines] = {1, 1, -1, -1, 1, 1, -1, -1};
static const float kOutR[kDspReverbLines] = {1, -1, 1, -1, -1, 1, -1, 1};
static const float kOutGain = 0.35f;

static int32_t is_prime(int32_t n) {
    if (n < 2) {
        return 0;
    }
    for (int32_t d = 2; d * d <= n; ++d) {
        if (n % d == 0) {
            return 0;
        }
    }
    return 1;
}

static int32_t line_len(float sample_rate_hz, int32_t i) {
    int32_t n = (int32_t)(kBaseMs[i] * 0.001f * sample_rate_hz + 0.5f);
    while (!is_prime(n)) {
        ++n;
    }
    return n;
}

static int32_t mod_samples(float sample_rate_hz) {
    return (int32_t)(kModMs * 0.001f * sample_rate_hz) + 1;
}

static int32_t pre_len(float sample_rate_hz) {
    return (int32_t)(kMaxPredelayMs * 0.001f * sample_rate_hz) + 4;
}

/* Allocated length of line i: its delay, the modulation's swing, and the reads' margin. */
static int32_t alloc_len(float sample_rate_hz, int32_t i) {
    return line_len(sample_rate_hz, i) + mod_samples(sample_rate_hz) + 4;
}

int32_t dsp_reverb_f32_mem_needed(float sample_rate_hz) {
    int32_t total = 2 * pre_len(sample_rate_hz);
    for (int32_t i = 0; i < kDspReverbLines; ++i) {
        total += alloc_len(sample_rate_hz, i);
    }
    return total;
}

int32_t dsp_reverb_f32_init(DspReverbF32 *rev, float sample_rate_hz, float *mem, int32_t mem_len) {
    rev->sample_rate_hz = sample_rate_hz;
    if (mem == NULL || mem_len < dsp_reverb_f32_mem_needed(sample_rate_hz)) {
        return -1;
    }
    float *p = mem;
    for (int32_t i = 0; i < kDspReverbLines; ++i) {
        rev->len[i] = line_len(sample_rate_hz, i);
        const int32_t n = alloc_len(sample_rate_hz, i);
        dsp_delayline_f32_init(&rev->line[i], p, n);
        p += n;
    }
    rev->max_predelay = pre_len(sample_rate_hz) - 4;
    dsp_delayline_f32_init(&rev->pre[0], p, pre_len(sample_rate_hz));
    p += pre_len(sample_rate_hz);
    dsp_delayline_f32_init(&rev->pre[1], p, pre_len(sample_rate_hz));
    rev->mod_depth = kModMs * 0.001f * sample_rate_hz;
    for (int k = 0; k < 2; ++k) {
        dsp_lfo_f32_init(&rev->mod[k], sample_rate_hz, kDspLfoSine);
        dsp_lfo_f32_set_rate(&rev->mod[k], kModHz[k]);
    }
    dsp_reverb_f32_set_decay(rev, 2.0f, 1.0f);
    dsp_reverb_f32_set_predelay_ms(rev, 10.0f);
    dsp_reverb_f32_reset(rev, 1);
    return 0;
}

void dsp_reverb_f32_reset(DspReverbF32 *rev, int32_t clear_memory) {
    for (int32_t i = 0; i < kDspReverbLines; ++i) {
        if (clear_memory) {
            dsp_delayline_f32_reset(&rev->line[i]);
        } else {
            rev->line[i].write = 0;
        }
        rev->z[i] = 0.0f;
    }
    for (int k = 0; k < 2; ++k) {
        if (clear_memory) {
            dsp_delayline_f32_reset(&rev->pre[k]);
        } else {
            rev->pre[k].write = 0;
        }
        dsp_lfo_f32_set_phase(&rev->mod[k], 0.25 * (double)k);
    }
}

void dsp_reverb_f32_set_decay(DspReverbF32 *rev, float rt60_low_s, float rt60_high_s) {
    if (!(rt60_low_s >= 0.1f)) {
        rt60_low_s = 0.1f;
    } else if (rt60_low_s > 20.0f) {
        rt60_low_s = 20.0f;
    }
    if (!(rt60_high_s >= 0.05f)) {
        rt60_high_s = 0.05f;
    } else if (rt60_high_s > rt60_low_s) {
        rt60_high_s = rt60_low_s;
    }
    rev->rt60_low_s = rt60_low_s;
    rev->rt60_high_s = rt60_high_s;
    for (int32_t i = 0; i < kDspReverbLines; ++i) {
        const double l = (double)rev->len[i] / (double)rev->sample_rate_hz;
        const double g_lo = pow(10.0, -3.0 * l / (double)rt60_low_s);
        const double g_hi = pow(10.0, -3.0 * l / (double)rt60_high_s);
        const double a1 = (g_lo - g_hi) / (g_lo + g_hi);
        rev->a1[i] = (float)a1;
        rev->b0[i] = (float)(g_lo * (1.0 - a1));
    }
}

void dsp_reverb_f32_set_predelay_ms(DspReverbF32 *rev, float ms) {
    int32_t d = (int32_t)(ms * 0.001f * rev->sample_rate_hz + 0.5f);
    if (!(ms > 0.0f) || d < 0) {
        d = 0;
    } else if (d > rev->max_predelay) {
        d = rev->max_predelay;
    }
    rev->predelay = d;
}

/* In-place fast Walsh-Hadamard transform of order 8, scaled by 1 / sqrt(8). */
static void hadamard8(float *v) {
    for (int32_t h = 1; h < kDspReverbLines; h *= 2) {
        for (int32_t i = 0; i < kDspReverbLines; i += 2 * h) {
            for (int32_t j = i; j < i + h; ++j) {
                const float a = v[j], b = v[j + h];
                v[j] = a + b;
                v[j + h] = a - b;
            }
        }
    }
    for (int32_t i = 0; i < kDspReverbLines; ++i) {
        v[i] *= 0.35355339f;
    }
}

void dsp_reverb_f32_process(DspReverbF32 *rev, const float *in_l, const float *in_r,
                            float *out_l, float *out_r, size_t n_frames) {
    float s[kDspReverbLines];
    float v[kDspReverbLines];
    for (size_t n = 0; n < n_frames; ++n) {
        dsp_delayline_f32_push(&rev->pre[0], in_l[n]);
        dsp_delayline_f32_push(&rev->pre[1], in_r[n]);
        const float ul = dsp_delayline_f32_tap(&rev->pre[0], rev->predelay);
        const float ur = dsp_delayline_f32_tap(&rev->pre[1], rev->predelay);
        for (int32_t i = 0; i < kDspReverbLines; ++i) {
            s[i] = dsp_delayline_f32_tap(&rev->line[i], rev->len[i] - 1);
        }
        for (int k = 0; k < 2; ++k) {
            const int32_t i = kModLine[k];
            const float m = rev->mod_depth * dsp_lfo_f32_next(&rev->mod[k]);
            s[i] = dsp_delayline_f32_read_lagrange(&rev->line[i], (float)(rev->len[i] - 1) + m);
        }
        float yl = 0.0f, yr = 0.0f;
        for (int32_t i = 0; i < kDspReverbLines; ++i) {
            yl += kOutL[i] * s[i];
            yr += kOutR[i] * s[i];
            rev->z[i] = rev->b0[i] * s[i] + rev->a1[i] * rev->z[i];
            v[i] = rev->z[i];
        }
        hadamard8(v);
        /* Left into the even lines, right into the odd ones, alternating signs. */
        v[0] += ul;
        v[2] -= ul;
        v[4] += ul;
        v[6] -= ul;
        v[1] += ur;
        v[3] -= ur;
        v[5] += ur;
        v[7] -= ur;
        for (int32_t i = 0; i < kDspReverbLines; ++i) {
            dsp_delayline_f32_push(&rev->line[i], v[i]);
        }
        out_l[n] = kOutGain * yl;
        out_r[n] = kOutGain * yr;
    }
}
