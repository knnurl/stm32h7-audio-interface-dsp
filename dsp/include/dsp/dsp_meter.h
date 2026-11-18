/* Meters for one or two channels: peak with hold and decay, RMS, true peak, and the loudness of
 * ITU-R BS.1770-4 (momentary over 400 ms, short-term over 3 s).
 *
 * Per sample, per channel:
 *   - peak: the held peak follows any new maximum of |x| at once, holds it for `hold_ms`, then
 *     falls at `decay_db_per_s` (a per-sample factor, so the fall is linear in dB); and the
 *     largest |x| since the last read, so a reader at 30 Hz misses no sample;
 *   - RMS: a one-pole on x^2 with time constant `rms_ms` (default 300 ms [Verify] against the
 *     reading the owner wants; no single standard fixes it);
 *   - true peak (kDspMeterTruePeak): the largest 4x-interpolated peak since the last read, from
 *     the detector the limiter uses (dsp_truepeak.h); it under-reads by up to cos(pi f / 4 fs);
 *   - loudness (kDspMeterLoudness): K-weighting (two biquads per channel), then the sum of the
 *     squares over all channels (weight 1 each: left and right in BS.1770) in 100 ms blocks,
 *     accumulated in double. Momentary = the mean power of the newest 4 blocks, short-term of the
 *     newest 30, both as -0.691 + 10 log10(power) LUFS. The block history starts as silence at
 *     reset, so the first 0.4 s and 3 s read low, as the windows would over silence before the
 *     start. 100 ms blocks give the 75 % overlap of BS.1770's gating blocks, so a PC that reads
 *     the momentary value once per new block (`loudness_blocks`) can compute the gated
 *     integrated loudness itself.
 * The K-weighting comes from dsp_kweight_design (the owner's exercise EX8c); while that is a
 * stub, the loudness is unweighted and `kweighted` is 0. dsp_meter_f32_set_kweight sets other
 * coefficients (the tests use the published 48 kHz ones).
 *
 * Reading: dsp_meter_f32_read converts to dB (log10f) and clears the since-last-read maxima. It
 * must run in the same context as process (the audio path reads at the meter rate and publishes
 * the reading to the control level); it is not safe against a concurrent process.
 * Values below DSP_METER_FLOOR_DB (and silence) read as DSP_METER_FLOOR_DB.
 *
 * Assumptions: 1 or 2 channels (in_r ignored for 1); any block size; a 100 ms block is rounded
 * to whole samples (exact at 44.1, 48, 88.2 and 96 kHz).
 * Latency: the true peak looks 8 samples back; the rest 0. Cycles: self-test cases meter_f32
 * (everything) and meter_peak_f32 (peak and RMS only).
 */
#ifndef DSP_METER_H
#define DSP_METER_H

#include "dsp/dsp_biquad.h"
#include "dsp/dsp_truepeak.h"

#include <stddef.h>
#include <stdint.h>

enum {
    kDspMeterTruePeak = 1,
    kDspMeterLoudness = 2,
    kDspMeterBlocks = 30, /* 100 ms each: the short-term window. */
    kDspMeterMomentaryBlocks = 4,
};
#define DSP_METER_FLOOR_DB (-120.0f)

typedef struct {
    float sample_rate_hz;
    int32_t channels;
    int32_t flags;
    /* Peak. */
    int32_t hold_samples;
    float decay_coef;
    float held[2];
    int32_t hold_left[2];
    float max_peak[2];
    /* RMS. */
    float rms_coef;
    float ms[2];
    /* True peak. */
    float tp_hist[2][2 * kDspTruePeakTaps]; /* Newest first, written twice. */
    int32_t tp_pos;
    float max_tp[2];
    /* Loudness. */
    int32_t kweighted;
    DspBiquadCoefsF32 kw[2];
    DspBiquadStateF32 kw_state[2][2];
    int32_t block_len;
    int32_t block_fill;
    double block_sum;
    double block_power[kDspMeterBlocks]; /* Mean power of each block, newest at block_pos - 1. */
    int32_t block_pos;
    uint32_t blocks_done;
} DspMeterF32;

typedef struct {
    float peak_db[2];         /* The held peak. */
    float max_peak_db[2];     /* The largest sample since the last read. */
    float rms_db[2];
    float true_peak_db[2];    /* Since the last read; the floor without kDspMeterTruePeak. */
    float momentary_lufs;     /* The floor without kDspMeterLoudness. */
    float short_term_lufs;
    uint32_t loudness_blocks; /* 100 ms blocks completed since reset. */
    int32_t kweighted;
} DspMeterReading;

/* Hold 1000 ms, decay 11.8 dB/s (20 dB in 1.7 s [Verify] against IEC 60268-18), RMS 300 ms.
 * Returns 0, or -1 for a channel count other than 1 or 2. */
int32_t dsp_meter_f32_init(DspMeterF32 *meter, float sample_rate_hz, int32_t channels,
                           int32_t flags);
void dsp_meter_f32_set_ballistics(DspMeterF32 *meter, float hold_ms, float decay_db_per_s,
                                  float rms_ms);
/* K-weighting coefficients other than dsp_kweight_design's; marks the meter K-weighted. */
void dsp_meter_f32_set_kweight(DspMeterF32 *meter, const DspBiquadCoefsF32 sections[2]);
/* Clears every reading, filter state and the loudness history. */
void dsp_meter_f32_reset(DspMeterF32 *meter);
void dsp_meter_f32_process(DspMeterF32 *meter, const float *in_l, const float *in_r,
                           size_t n_frames);
void dsp_meter_f32_read(DspMeterF32 *meter, DspMeterReading *reading);
/* The mean power of the newest `n_blocks` blocks (clamped to 1 to kDspMeterBlocks), linear. */
double dsp_meter_f32_power(const DspMeterF32 *meter, int32_t n_blocks);

#endif
