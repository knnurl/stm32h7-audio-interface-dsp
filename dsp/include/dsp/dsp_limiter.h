/* Stereo-linked look-ahead limiter with true-peak detection.
 *
 * Detection: each channel is upsampled 4x (dsp_oversample's filters) and the largest |value|
 * of the 4 phases is that sample's true peak; the larger of the two channels counts. This
 * catches the peaks between samples that a DAC's reconstruction filter will produce (the idea
 * of ITU-R BS.1770's true-peak meter, with a sharper interpolator than the standard's).
 * Required gain: r[t] = min(1, ceiling / peak[t]).
 *
 * Gain, so the ceiling is never crossed:
 *   1. a sliding minimum of r over W = L + 3 samples (L = look-ahead; the 3 cover the
 *      detector's fractional alignment);
 *   2. a release: when that minimum rises, the gain follows it through a one-pole (`release_ms`);
 *      when it falls, at once;
 *   3. a moving average over L samples, which turns each drop into a straight ramp of L samples
 *      that is complete before the loud sample leaves the delay line.
 * The audio is delayed by L + 24 samples (the detector's own delay is 23.25 samples, rounded up).
 * Every gain value in the average is at most the required gain of the sample it is applied to,
 * so the average is too.
 *
 * What is guaranteed: no output *sample* exceeds the ceiling. The output's true peak can exceed
 * it slightly, because the gain's own movement adds sidebands: about +0.12 dB with a look-ahead
 * of 1 to 4 samples, +0.01 dB from 20 samples (from the batch 6 review; measured in
 * tests/unit/test_limiter.py). The look-ahead is therefore at least 32 samples.
 * Non-finite input (NaN, infinity) is replaced by 0 before it reaches the detector or the delay
 * line: this is the last block before the converters and the speakers.
 *
 * Latency: L + 24 samples (dsp_limiter_f32_latency). Below the ceiling the output is the delayed
 * input, bit for bit.
 * Assumptions: stereo; blocks of any size. Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_LIMITER_H
#define DSP_LIMITER_H

#include "dsp/dsp_oversample.h"

#include <stddef.h>
#include <stdint.h>

enum {
    kDspLimiterMinLookahead = 32,
    kDspLimiterMaxLookahead = 480, /* 5 ms at 96 kHz */
    kDspLimiterDetectorDelay = 24,
    kDspLimiterWindow = kDspLimiterMaxLookahead + 3,
    kDspLimiterMaxDelay = kDspLimiterMaxLookahead + kDspLimiterDetectorDelay,
};

typedef struct {
    float sample_rate_hz;
    float ceiling;      /* Linear. */
    float release_coef;
    int32_t lookahead;  /* L */
    int32_t delay_len;  /* L + 24 */
    DspOversampleF32 detector[2];
    float tp_buf[4 * kDspOversampleMaxBlock];
    float peak[kDspOversampleMaxBlock];
    float clean[2][kDspOversampleMaxBlock];
    float delay[2][kDspLimiterMaxDelay];
    int32_t delay_pos;
    /* Sliding minimum: a monotonic queue of (sample index, value). */
    float queue_val[kDspLimiterWindow + 1];
    uint32_t queue_idx[kDspLimiterWindow + 1];
    int32_t queue_head;
    int32_t queue_count;
    uint32_t t;
    float held;
    /* Moving average. */
    float box[kDspLimiterMaxLookahead];
    int32_t box_pos;
    double box_sum;
    float gain;     /* The last gain applied, for metering. */
    float min_gain; /* The smallest since the last read (dsp_limiter_f32_take_min_gain). */
} DspLimiterF32;

void dsp_limiter_f32_init(DspLimiterF32 *lim, float sample_rate_hz, float ceiling_db,
                          float lookahead_ms, float release_ms);
void dsp_limiter_f32_reset(DspLimiterF32 *lim);
int32_t dsp_limiter_f32_latency(const DspLimiterF32 *lim);
float dsp_limiter_f32_take_min_gain(DspLimiterF32 *lim);
void dsp_limiter_f32_process(DspLimiterF32 *lim, const float *in_l, const float *in_r,
                             float *out_l, float *out_r, size_t n_frames);

#endif
