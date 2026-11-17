/* 2x and 4x oversampling with polyphase half-band FIR filters.
 *
 * A half-band low-pass of length N = 4K + 3 has every other tap zero except the centre (0.5).
 * Upsampling by 2 with it splits into two phases: one is a (N + 1) / 2 = 2K + 2 tap FIR on the
 * even-indexed taps, the other is a pure delay (the centre tap). Downsampling uses the same
 * split. So a 2x stage costs 2K + 2 multiply-adds per base-rate sample each way (42 for the
 * 83-tap filter). Folding the symmetric taps would halve that; not done yet.
 * The stopband starts at 28 kHz, not at the new Nyquist (24 kHz at 48 kHz): content between 24
 * and 28 kHz at the high rate folds into 20 to 24 kHz on the way down. That band is above
 * hearing, which is the half-band trade: half the taps for it.
 *
 * Built-in filters (tools/design/b6_coefficients.py, equiripple):
 *   stage 1 (base to 2x): 83 taps, passband to 0.2083 fs_out (20 kHz at a 48 kHz base rate),
 *                         stopband from 0.2917 fs_out (28 kHz), 113 dB down, ripple 4e-5 dB.
 *   stage 2 (2x to 4x):   23 taps, passband to 0.1042 fs_out, stopband from 0.3958 fs_out,
 *                         125 dB down.
 * 4x is stage 1 then stage 2 on the way up, and the reverse on the way down.
 *
 * Latency, up and down together, in base-rate samples: 41 for 2x, 46.5 for 4x (each stage is a
 * linear-phase filter with a delay of (N - 1) / 2 samples at its output rate, met twice).
 *
 * dsp_halfband_*: one stage, for callers that bring their own filter (exercise 6). The filter
 * must have length 4K + 3 with (N + 1) / 2 <= kDspHalfbandMaxTaps (N <= 95); only its
 * even-indexed taps are used.
 * Assumptions: mono; any block size (the wrappers work through it 64 frames at a time).
 * Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_OVERSAMPLE_H
#define DSP_OVERSAMPLE_H

#include <stddef.h>
#include <stdint.h>

enum { kDspHalfbandMaxTaps = 48, kDspOversampleMaxBlock = 64 };

typedef struct {
    int32_t n_taps;           /* Even-indexed taps, K + 1. */
    int32_t delay;            /* Of the centre phase, in input samples. */
    float taps[kDspHalfbandMaxTaps];
    float hist[2 * kDspHalfbandMaxTaps]; /* Newest first, written twice for contiguous reads. */
    int32_t pos;
} DspHalfbandUpF32;

typedef struct {
    int32_t n_taps;
    int32_t delay; /* Of the odd-sample path, in output samples. */
    float taps[kDspHalfbandMaxTaps];
    float even[2 * kDspHalfbandMaxTaps];
    int32_t even_pos;
    float odd[2 * kDspHalfbandMaxTaps];
    int32_t odd_pos;
} DspHalfbandDownF32;

/* `h` is the full filter, `length` = 4K + 3. Returns 0, or -1 if the filter does not fit. */
int32_t dsp_halfband_up_init(DspHalfbandUpF32 *up, const float *h, int32_t length);
int32_t dsp_halfband_down_init(DspHalfbandDownF32 *down, const float *h, int32_t length);
void dsp_halfband_up_reset(DspHalfbandUpF32 *up);
void dsp_halfband_down_reset(DspHalfbandDownF32 *down);
/* n_in frames in, 2 n_in out. */
void dsp_halfband_up_process(DspHalfbandUpF32 *up, const float *in, float *out, size_t n_in);
/* 2 n_out frames in, n_out out. */
void dsp_halfband_down_process(DspHalfbandDownF32 *down, const float *in, float *out,
                               size_t n_out);

/* The built-in filters, for tests and studies. */
const float *dsp_halfband_stage1(int32_t *length);
const float *dsp_halfband_stage2(int32_t *length);

typedef struct {
    int32_t factor; /* 2 or 4. */
    DspHalfbandUpF32 up1, up2;
    DspHalfbandDownF32 down1, down2;
    float scratch[2 * kDspOversampleMaxBlock];
} DspOversampleF32;

void dsp_oversample_f32_init(DspOversampleF32 *os, int32_t factor);
void dsp_oversample_f32_reset(DspOversampleF32 *os);
/* n frames in, factor x n out. */
void dsp_oversample_f32_up(DspOversampleF32 *os, const float *in, float *out, size_t n);
/* factor x n frames in, n out. */
void dsp_oversample_f32_down(DspOversampleF32 *os, const float *in, float *out, size_t n);
/* Up and down together, in base-rate samples (41 or 46.5). */
float dsp_oversample_f32_latency(const DspOversampleF32 *os);

#endif
