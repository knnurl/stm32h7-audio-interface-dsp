#include "dsp/dsp_limiter.h"

#include "dsp/dsp_env.h"

#include <math.h>
#include <string.h>

/* tools/design/tp_detector.py, 16 taps per phase, Kaiser 4.1. Phase 3/4 is phase 1/4 reversed;
 * phase 1/2 is symmetric. Index i meets the sample i steps back from the newest. */
static const float kTpQuarter[kDspLimiterTpTaps] = {
    -2.356659854e-03f, 6.230897736e-03f, -1.268179156e-02f, 2.283323370e-02f,
    -3.870575503e-02f, 6.502874196e-02f, -1.173553094e-01f, 2.951403856e-01f,
    8.986518979e-01f, -1.718815416e-01f, 8.588046581e-02f, -5.004023388e-02f,
    2.986130491e-02f, -1.720060594e-02f, 9.075933136e-03f, -4.025056027e-03f,
};
static const float kTpHalf[kDspLimiterTpTaps / 2] = {
    -4.425711464e-03f, 1.070061512e-02f, -2.095292322e-02f, 3.698274866e-02f,
    -6.223199144e-02f, 1.053786874e-01f, -1.984295547e-01f, 6.319220662e-01f,
};

/* The true peak around the sample 8 steps back: the sample itself and the three phases after
 * it, from a history `x` holding the newest 16 samples newest first. */
static float true_peak(const float *x) {
    float q1a = 0.0f, q1b = 0.0f, q3a = 0.0f, q3b = 0.0f, h0 = 0.0f, h1 = 0.0f;
    for (int32_t i = 0; i < kDspLimiterTpTaps / 2; ++i) {
        const float a = x[i], b = x[kDspLimiterTpTaps - 1 - i];
        q1a += kTpQuarter[i] * a;
        q1b += kTpQuarter[kDspLimiterTpTaps - 1 - i] * b;
        q3a += kTpQuarter[kDspLimiterTpTaps - 1 - i] * a;
        q3b += kTpQuarter[i] * b;
        if ((i & 1) == 0) {
            h0 += kTpHalf[i] * (a + b);
        } else {
            h1 += kTpHalf[i] * (a + b);
        }
    }
    const float p0 = fabsf(x[kDspLimiterTpTaps / 2]);
    const float p1 = fabsf(q1a + q1b), p2 = fabsf(h0 + h1), p3 = fabsf(q3a + q3b);
    const float m01 = p0 > p1 ? p0 : p1, m23 = p2 > p3 ? p2 : p3;
    return m01 > m23 ? m01 : m23;
}

void dsp_limiter_f32_init(DspLimiterF32 *lim, float sample_rate_hz, float ceiling_db,
                          float lookahead_ms, float release_ms) {
    dsp_limiter_f32_init_mode(lim, sample_rate_hz, ceiling_db, lookahead_ms, release_ms,
                              kDspLimiterTruePeak);
}

void dsp_limiter_f32_init_mode(DspLimiterF32 *lim, float sample_rate_hz, float ceiling_db,
                               float lookahead_ms, float release_ms, int32_t mode) {
    memset(lim, 0, sizeof(*lim));
    lim->mode = mode == kDspLimiterSamplePeak ? kDspLimiterSamplePeak : kDspLimiterTruePeak;
    const int sample = lim->mode == kDspLimiterSamplePeak;
    lim->sample_rate_hz = sample_rate_hz;
    lim->ceiling =
        powf(10.0f, (ceiling_db - (sample ? 0.0f : DSP_LIMITER_TRUE_PEAK_MARGIN_DB)) / 20.0f);
    lim->release_coef = dsp_env_coef(sample_rate_hz, release_ms);
    int32_t l = (int32_t)(lookahead_ms * 0.001f * sample_rate_hz + 0.5f);
    if (l < kDspLimiterMinLookahead) {
        l = kDspLimiterMinLookahead;
    } else if (l > kDspLimiterMaxLookahead) {
        l = kDspLimiterMaxLookahead;
    }
    lim->lookahead = l;
    lim->delay_len = l + (sample ? 1 : kDspLimiterDetectorDelay);
    dsp_limiter_f32_reset(lim);
}

void dsp_limiter_f32_reset(DspLimiterF32 *lim) {
    memset(lim->tp_hist, 0, sizeof(lim->tp_hist));
    lim->tp_pos = 0;
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
        if (lim->mode == kDspLimiterSamplePeak) {
            for (size_t i = 0; i < n; ++i) {
                const float a = fabsf(lim->clean[0][i]), b = fabsf(lim->clean[1][i]);
                lim->peak[i] = a > b ? a : b;
            }
        }
        if (lim->mode == kDspLimiterTruePeak) {
            const int32_t n_taps = kDspLimiterTpTaps;
            for (size_t i = 0; i < n; ++i) {
                int32_t pos = lim->tp_pos == 0 ? n_taps - 1 : lim->tp_pos - 1;
                lim->tp_pos = pos;
                float m = 0.0f;
                for (int ch = 0; ch < 2; ++ch) {
                    float *hist = lim->tp_hist[ch];
                    hist[pos] = lim->clean[ch][i];
                    hist[pos + n_taps] = lim->clean[ch][i];
                    const float p = true_peak(&hist[pos]);
                    m = p > m ? p : m;
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
