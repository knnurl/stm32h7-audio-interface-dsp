/* Stereo-linked look-ahead limiter with true-peak detection.
 *
 * Detection: each channel is interpolated 4x and the largest |value| of the 4 phases is that
 * sample's true peak; the larger of the two channels counts. This catches the peaks between
 * samples that a DAC's reconstruction filter will produce (the idea of ITU-R BS.1770's true-peak
 * meter). The interpolator (since the budget round of 2026-11-17; it was dsp_oversample's 4x
 * chain, 113 dB, about 780 of the limiter's 998 cycles per frame): a 63-tap Kaiser-windowed sinc
 * cut at the base Nyquist, so phase 0 is the sample itself and phases 1/4, 1/2 and 3/4 are 16
 * taps each, the 3/4 phase being the 1/4 phase reversed (tools/design/tp_detector.py). Passband
 * flat within +/-0.07 dB to 20 kHz at 48 kHz; images from 28 kHz at -41 dB or lower. Its
 * decisions are checked by the same true-peak tests as before.
 * Required gain: r[t] = min(1, threshold / peak[t]), the threshold being the set ceiling less
 * kDspLimiterTruePeakMarginDb (0.5 dB; owner's decision 2026-11-17).
 *
 * Gain, so the ceiling is never crossed:
 *   1. a sliding minimum of r over W = L + 3 samples (L = look-ahead; the 3 cover the
 *      detector's fractional alignment);
 *   2. a release: when that minimum rises, the gain follows it through a one-pole (`release_ms`);
 *      when it falls, at once;
 *   3. a moving average over L samples, which turns each drop into a straight ramp of L samples
 *      that is complete before the loud sample leaves the delay line.
 * The audio is delayed by L + 9 samples (the detector looks 8 samples back, its phases up to
 * three quarters of a sample nearer; 9 keeps the emerging sample inside every window).
 * Every gain value in the average is at most the required gain of the sample it is applied to,
 * so the average is too.
 *
 * What is guaranteed: no output *sample* exceeds the threshold. The output's true peak can
 * exceed the threshold, because 4x detection under-reads peaks between its samples by up to
 * cos(pi f / 4 fs): 0.198 dB measured on the hostile set at every look-ahead, 0.47 dB in theory
 * for 20 kHz content at 48 kHz. The 0.5 dB margin covers that, so the true peak stays under the
 * set ceiling (tests/unit/test_limiter.py). Interpolating between the four detector samples is
 * the measured improvement left for later. The look-ahead is at least 32 samples.
 * Non-finite input (NaN, infinity) is replaced by 0 before it reaches the detector or the delay
 * line: this is the last block before the converters and the speakers.
 *
 * Latency: L + 9 samples (dsp_limiter_f32_latency; L + 24 before the budget round). Below the ceiling the output is the delayed
 * input, bit for bit.
 *
 * Sample-peak mode (kDspLimiterSamplePeak, dsp_limiter_f32_init_mode; for the headphones since
 * the budget round of 2026-11-17): no oversampled detector. The peak is max(|l|, |r|) of the
 * sample itself, the threshold is the ceiling itself (no true-peak margin: there is no
 * inter-sample estimate to correct), and the audio delay is L + 1, which keeps the emerging sample
 * inside every window that sets its gain (the same argument as above with a detector delay of 0,
 * which allows L - 1 to L + 2). Guaranteed: no output sample above the ceiling. Not guaranteed:
 * the true peak, which can exceed it by up to about 3 dB on a quarter-rate sine at 45 degrees
 * (measured in tests/unit/test_limiter.py).
 * Assumptions: stereo; blocks of any size. Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_LIMITER_H
#define DSP_LIMITER_H

#include "dsp/dsp_oversample.h"

#include <stddef.h>
#include <stdint.h>

/* The true-peak margin below the set ceiling, in dB. */
#define DSP_LIMITER_TRUE_PEAK_MARGIN_DB 0.5f

enum {
    kDspLimiterTruePeak = 0,
    kDspLimiterSamplePeak = 1,
};

enum {
    kDspLimiterMinLookahead = 32,
    kDspLimiterMaxLookahead = 480, /* 5 ms at 96 kHz */
    kDspLimiterDetectorDelay = 9,
    kDspLimiterTpTaps = 16,
    kDspLimiterWindow = kDspLimiterMaxLookahead + 3,
    kDspLimiterMaxDelay = kDspLimiterMaxLookahead + kDspLimiterDetectorDelay,
};

typedef struct {
    float sample_rate_hz;
    float ceiling;      /* Linear: the threshold, the set ceiling less the margin. */
    float release_coef;
    int32_t lookahead;  /* L */
    int32_t delay_len;  /* L + 24 */
    float tp_hist[2][2 * kDspLimiterTpTaps]; /* Newest first, written twice. */
    int32_t tp_pos;
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
    int32_t mode;   /* kDspLimiterTruePeak or kDspLimiterSamplePeak. */
} DspLimiterF32;

void dsp_limiter_f32_init(DspLimiterF32 *lim, float sample_rate_hz, float ceiling_db,
                          float lookahead_ms, float release_ms);
/* As dsp_limiter_f32_init, with the detector chosen: kDspLimiterTruePeak (the default above) or
 * kDspLimiterSamplePeak. */
void dsp_limiter_f32_init_mode(DspLimiterF32 *lim, float sample_rate_hz, float ceiling_db,
                               float lookahead_ms, float release_ms, int32_t mode);
void dsp_limiter_f32_reset(DspLimiterF32 *lim);
int32_t dsp_limiter_f32_latency(const DspLimiterF32 *lim);
float dsp_limiter_f32_take_min_gain(DspLimiterF32 *lim);
void dsp_limiter_f32_process(DspLimiterF32 *lim, const float *in_l, const float *in_r,
                             float *out_l, float *out_r, size_t n_frames);

#endif
