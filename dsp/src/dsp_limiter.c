#include "dsp/dsp_limiter.h"

#include "dsp/dsp_env.h"

#include <math.h>
#include <string.h>

void dsp_limiter_f32_init(DspLimiterF32 *lim, float sample_rate_hz, float ceiling_db,
                          float lookahead_ms, float release_ms) {
    memset(lim, 0, sizeof(*lim));
    lim->sample_rate_hz = sample_rate_hz;
    lim->ceiling = powf(10.0f, ceiling_db / 20.0f);
    lim->release_coef = dsp_env_coef(sample_rate_hz, release_ms);
    int32_t l = (int32_t)(lookahead_ms * 0.001f * sample_rate_hz + 0.5f);
    if (l < kDspLimiterMinLookahead) {
        l = kDspLimiterMinLookahead;
    } else if (l > kDspLimiterMaxLookahead) {
        l = kDspLimiterMaxLookahead;
    }
    lim->lookahead = l;
    lim->delay_len = l + kDspLimiterDetectorDelay;
    dsp_oversample_f32_init(&lim->detector[0], 4);
    dsp_oversample_f32_init(&lim->detector[1], 4);
    dsp_limiter_f32_reset(lim);
}

void dsp_limiter_f32_reset(DspLimiterF32 *lim) {
    dsp_oversample_f32_reset(&lim->detector[0]);
    dsp_oversample_f32_reset(&lim->detector[1]);
    memset(lim->delay, 0, sizeof(lim->delay));
    lim->delay_pos = 0;
    lim->queue_head = 0;
    lim->queue_count = 0;
    lim->t = 0;
    lim->held = 1.0f;
    for (int32_t i = 0; i < lim->lookahead; ++i) {
        lim->box[i] = 1.0f;
    }
    lim->box_pos = 0;
    lim->box_sum = (double)lim->lookahead;
    lim->gain = 1.0f;
    lim->min_gain = 1.0f;
}

int32_t dsp_limiter_f32_latency(const DspLimiterF32 *lim) { return lim->delay_len; }

float dsp_limiter_f32_take_min_gain(DspLimiterF32 *lim) {
    const float g = lim->min_gain;
    lim->min_gain = lim->gain;
    return g;
}

/* Pushes r for sample index t and returns the minimum over the last W samples. */
static float window_min(DspLimiterF32 *lim, float r) {
    const int32_t cap = kDspLimiterWindow + 1;
    const uint32_t w = (uint32_t)lim->lookahead + 3u;
    /* Drop from the back everything not smaller than r: it can never be the minimum again. */
    while (lim->queue_count > 0) {
        const int32_t back = (lim->queue_head + lim->queue_count - 1) % cap;
        if (lim->queue_val[back] < r) {
            break;
        }
        --lim->queue_count;
    }
    const int32_t slot = (lim->queue_head + lim->queue_count) % cap;
    lim->queue_val[slot] = r;
    lim->queue_idx[slot] = lim->t;
    ++lim->queue_count;
    /* Drop from the front what has left the window. */
    while (lim->t - lim->queue_idx[lim->queue_head] >= w) {
        lim->queue_head = (lim->queue_head + 1) % cap;
        --lim->queue_count;
    }
    return lim->queue_val[lim->queue_head];
}

void dsp_limiter_f32_process(DspLimiterF32 *lim, const float *in_l, const float *in_r,
                             float *out_l, float *out_r, size_t n_frames) {
    const int32_t l = lim->lookahead;
    const double inv_l = 1.0 / (double)l;
    for (size_t start = 0; start < n_frames; start += kDspOversampleMaxBlock) {
        size_t n = n_frames - start;
        if (n > kDspOversampleMaxBlock) {
            n = kDspOversampleMaxBlock;
        }
        /* Clean copies of the input: NaN and infinity become 0. */
        for (size_t i = 0; i < n; ++i) {
            const float l_in = in_l[start + i], r_in = in_r[start + i];
            lim->clean[0][i] = isfinite(l_in) ? l_in : 0.0f;
            lim->clean[1][i] = isfinite(r_in) ? r_in : 0.0f;
            lim->peak[i] = 0.0f;
        }
        for (int ch = 0; ch < 2; ++ch) {
            dsp_oversample_f32_up(&lim->detector[ch], lim->clean[ch], lim->tp_buf, n);
            for (size_t i = 0; i < n; ++i) {
                const float *p = &lim->tp_buf[4 * i];
                float m = lim->peak[i];
                for (int k = 0; k < 4; ++k) {
                    const float a = fabsf(p[k]);
                    m = a > m ? a : m;
                }
                lim->peak[i] = m;
            }
        }
        for (size_t i = 0; i < n; ++i) {
            const float pk = lim->peak[i];
            const float r = pk > lim->ceiling ? lim->ceiling / pk : 1.0f;
            const float m = window_min(lim, r);
            ++lim->t;
            if (m < lim->held) {
                lim->held = m;
            } else {
                const float next = m + lim->release_coef * (lim->held - m);
                /* A float32 one-pole stalls short of its target (it stopped at 0.99997 here).
                 * Finish the move when it stalls or is within 1e-6, so a released limiter is
                 * exactly transparent again. */
                lim->held = (next == lim->held || m - next < 1e-6f) ? m : next;
            }
            lim->box_sum += (double)lim->held - (double)lim->box[lim->box_pos];
            lim->box[lim->box_pos] = lim->held;
            lim->box_pos = lim->box_pos + 1 == l ? 0 : lim->box_pos + 1;
            /* All ones in the box give exactly 1.0, so a quiet signal passes bit for bit. */
            const float gain = (float)(lim->box_sum * inv_l);
            lim->gain = gain;
            lim->min_gain = gain < lim->min_gain ? gain : lim->min_gain;

            const int32_t pos = lim->delay_pos;
            const float dl = lim->delay[0][pos];
            const float dr = lim->delay[1][pos];
            lim->delay[0][pos] = lim->clean[0][i];
            lim->delay[1][pos] = lim->clean[1][i];
            lim->delay_pos = pos + 1 == lim->delay_len ? 0 : pos + 1;
            out_l[start + i] = gain == 1.0f ? dl : dl * gain;
            out_r[start + i] = gain == 1.0f ? dr : dr * gain;
        }
    }
}
