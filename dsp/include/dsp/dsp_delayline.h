/* Delay line: a circular buffer in caller-provided memory, with integer and fractional reads.
 *
 * Convention: after dsp_delayline_f32_push(x[n]), a read at delay d returns x[n - d]. Integer
 * reads take 0 <= d <= len - 1. Fractional reads clamp d to their valid range:
 *   linear              [0, len - 2]      2 taps, 1 multiply-add
 *   third-order Lagrange [1, len - 3]      4 taps, about 10 multiply-adds
 *   first-order all-pass [0.5, len - 3]    2 taps, 2 multiply-adds, one state word per reader
 * Linear is exact at integer d and a low-pass in between, worst at a fraction of 0.5, where it
 * is (1 + z^-1) / 2: -3 dB at fs / 4. Lagrange is flatter in magnitude. The all-pass is
 * flat in magnitude but has a state, so it must be read exactly once per sample per reader, and
 * a jump in d gives a short transient. The study measures all three on a swept read position.
 *
 * Length is any value >= 4, not only a power of two (the plan's 8b.1 said power of two): a mask
 * would round a 0.75 s line at 96 kHz (72000 samples) up to 131072, nearly doubling the largest
 * buffer in the device against a memory budget that is already over (8b.6). The wrap costs one
 * compare and add per read instead of an AND [Verify the cycle difference on the M7].
 *
 * Assumptions: mono; the caller owns the memory and keeps it alive; no allocation.
 * Latency: the delay itself. Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_DELAYLINE_H
#define DSP_DELAYLINE_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    float *buf;
    int32_t len;
    int32_t write; /* Where the next sample goes. */
} DspDelaylineF32;

/* The state of one all-pass interpolating reader. */
typedef struct {
    float y1;
} DspDelaylineApF32;

/* Returns 0, or -1 if `mem` is NULL or `len` < 4. Clears the memory. */
int32_t dsp_delayline_f32_init(DspDelaylineF32 *dl, float *mem, int32_t len);
void dsp_delayline_f32_reset(DspDelaylineF32 *dl);

static inline void dsp_delayline_f32_push(DspDelaylineF32 *dl, float x) {
    dl->buf[dl->write] = x;
    dl->write = dl->write + 1 == dl->len ? 0 : dl->write + 1;
}

static inline float dsp_delayline_f32_tap(const DspDelaylineF32 *dl, int32_t d) {
    int32_t i = dl->write - 1 - d;
    if (i < 0) {
        i += dl->len;
    }
    return dl->buf[i];
}

float dsp_delayline_f32_read_linear(const DspDelaylineF32 *dl, float d);
float dsp_delayline_f32_read_lagrange(const DspDelaylineF32 *dl, float d);
float dsp_delayline_f32_read_allpass(const DspDelaylineF32 *dl, DspDelaylineApF32 *ap, float d);

/* Block helpers for tests and studies: push each input sample, then read at delay d[i]. */
typedef enum {
    kDspInterpLinear = 0,
    kDspInterpLagrange = 1,
    kDspInterpAllpass = 2,
} DspInterp;
void dsp_delayline_f32_process(DspDelaylineF32 *dl, DspDelaylineApF32 *ap, int32_t interp,
                               const float *in, const float *delay, float *out, size_t n_frames);

/* 16-bit delay line (the echo's storage, owner's decision 2026-11-17).
 * Format: int16 with 2^13 per 1.0, so +/-4.0 (12 dB of headroom over full scale for feedback
 * build-up); saturates; NaN stores 0.
 * Rounding: to nearest (halves away from zero) at and above DSP_DELAYLINE_S16_SNAP_LSB (16 LSB,
 * -54 dBFS), toward zero below it. Pure round-to-nearest, the rule asked for, traps a decaying
 * echo in a limit cycle: with feedback g a stored value under 0.5 / (1 - g) LSB rounds back to
 * itself (10 LSB at g = 0.95), and the tail hung at -59 dBFS for ever (measured,
 * test_noise_at_feedback_095), so the slot's trails never ended. Rounding toward zero below
 * 16 LSB makes every small value shrink, and the tail reaches exact zero (2.15 s for 20 ms
 * repeats at 0.95). Cost, against a float line, over 2 s at g = 0.95: -74.2 dBFS of error
 * instead of -79.5 dBFS. Set the snap level to 0 for pure round-to-nearest.
 * Quantisation: no dither. The error is deterministic and only present while signal is stored:
 * a silent input leaves exactly zero, where dither would leave a hiss on every repeat. The
 * repeats pass through the echo's loop filters, which smear the error rather than leave it as
 * a fixed pattern. Step 1.22e-4 (-78 dBFS), error RMS about 3.5e-5 (-89 dBFS) per quantisation;
 * measured in tests/unit/test_fx_echo16.py.
 * Memory: `mem` is the caller's float pool, used as bytes: every access goes through memcpy
 * (character-type access), so the same pool can serve float delay lines at other times without
 * breaking C's effective-type (strict aliasing) rules under GCC -O2; GCC turns each 2-byte
 * memcpy into one load or store. `len` is in int16 samples (two per float of memory).
 */
typedef struct {
    unsigned char *buf;
    int32_t len;
    int32_t write;
} DspDelaylineS16;

#define DSP_DELAYLINE_S16_SCALE 8192.0f
#define DSP_DELAYLINE_S16_SNAP_LSB 16.0f

/* Returns 0, or -1 if `mem` is NULL or `len` < 4. Clears the memory. */
int32_t dsp_delayline_s16_init(DspDelaylineS16 *dl, float *mem, int32_t len);
void dsp_delayline_s16_reset(DspDelaylineS16 *dl);
void dsp_delayline_s16_push(DspDelaylineS16 *dl, float x);
float dsp_delayline_s16_tap(const DspDelaylineS16 *dl, int32_t d);
float dsp_delayline_s16_read_lagrange(const DspDelaylineS16 *dl, float d);
/* The stored value of x: what a push then a tap at 0 returns. */
float dsp_delayline_s16_quantise(float x);

#endif
