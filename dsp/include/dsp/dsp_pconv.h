/* Uniformly partitioned FFT convolution, float32, one channel: the room correction FIR (batch 9).
 *
 * The filter of up to `taps` coefficients is cut into P = ceil(taps / B) partitions of B taps.
 * Each is zero-padded to N = 2B and transformed once, when the filter is loaded. At run time
 * every B input samples make one partition step (overlap-save with a frequency-domain delay
 * line, as in Wefers, "Partitioned convolution algorithms for real-time auralization", 2015):
 *   1. the last 2B input samples are transformed (one N-point real FFT) into the newest slot of
 *      a ring of P input spectra;
 *   2. Y = sum over k of X(newest - k) H(k): P complex multiply-adds per bin, N/2 + 1 bins;
 *   3. one inverse FFT; its last B samples are the output (the first B are circular wrap).
 * So the cost per partition is two N-point real FFTs plus P (N/2 + 1) complex multiply-adds,
 * whatever the filter's length; the multiply-adds dominate once P is more than a few.
 *
 * Output: y[t] = sum_j h[j] x[t - B - j]. Latency: B samples (the partition being gathered).
 * On the target the step runs at the deferred level, where it can finish up to a partition
 * later than the audio level asks for it; that costs a further B unless the first partition is
 * computed in the time domain (batch 9 decides; docs/notes/partitioned_convolution.md).
 * The FFTs are CMSIS-DSP's arm_rfft_fast_f32 (owner's choice C, 2026-11-18: about 1.7 times
 * dsp_fft's speed, docs/results/bench_fft.md), on the PC as on the target, so the two stay
 * bit-identical. It overwrites its input, so each transform reads a copy in `tmp`; its inverse
 * scales by 1 / N, so the filter spectra are stored unscaled.
 * Memory: caller-provided, dsp_pconv_f32_mem_needed floats: 2 P N for the filter and input
 * spectra, 3 N for the input, work and copy buffers, B for the output. 71 KB per channel for
 * 4096 taps at B = 256.
 * Assumptions: B a power of two in [16, 1024] (CMSIS's real FFT starts at 32 points); the
 * filter is loaded outside the audio level (P forward FFTs). Cycles: docs/results/bench_fft.md.
 */
#ifndef DSP_PCONV_H
#define DSP_PCONV_H

#include "dsp/dsp_fft.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint64_t fft_state[8]; /* CMSIS-DSP's arm_rfft_fast_instance_f32, kept opaque here. */
    int32_t block; /* B */
    int32_t parts; /* P */
    int32_t head;  /* Ring slot of the newest input spectrum. */
    int32_t fill;  /* Samples gathered towards the next step. */
    float *h;      /* P spectra of N floats, packed (dsp_fft.h's layout, also CMSIS's). */
    float *fdl;    /* P input spectra of N floats. */
    float *in;     /* N: the previous and the current input partitions. */
    float *work;   /* N: the accumulated spectrum. */
    float *tmp;    /* N: the copy each transform destroys, then the inverse's output. */
    float *out;    /* B: the last step's output. */
} DspPconvF32;

/* Floats of memory for a filter of up to `taps` coefficients; 0 if block is not valid. */
int32_t dsp_pconv_f32_mem_needed(int32_t block, int32_t taps);
/* Returns 0, or -1 for an invalid block or taps, or memory smaller than mem_needed. The filter
 * starts as silence (all zero) and the history clear. */
int32_t dsp_pconv_f32_init(DspPconvF32 *conv, int32_t block, int32_t taps, float *mem,
                           int32_t mem_len);
/* Loads `taps` coefficients (at most the init's taps; the rest of the filter is zero). Keeps
 * the input history. Returns 0, or -1 if taps is out of range. */
int32_t dsp_pconv_f32_set_filter(DspPconvF32 *conv, const float *h, int32_t taps);
/* Clears the input history and the pending output; keeps the filter. */
void dsp_pconv_f32_reset(DspPconvF32 *conv);
/* Any n: steps run whenever B new samples have arrived. */
void dsp_pconv_f32_process(DspPconvF32 *conv, const float *in, float *out, size_t n);

#endif
