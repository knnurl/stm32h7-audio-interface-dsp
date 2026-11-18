/* Real FFT, float32, for 16 to 2048 points (powers of two). For the room correction's
 * partitioned convolution (dsp_pconv.h) and for analysis.
 *
 * Method: the n real samples are read as n/2 complex ones (even samples real, odd imaginary), an
 * n/2-point complex radix-2 FFT runs in place, and a split step separates the even and odd
 * halves' spectra into the real signal's spectrum (Oppenheim and Schafer's "two real FFTs in
 * one" applied to the halves of one signal). This costs about half of an n-point complex FFT.
 *
 * Spectrum layout (the CMSIS-DSP arm_rfft_fast_f32 layout, so the two can be compared): n floats;
 * out[0] = X[0] and out[1] = X[n/2], both real; then out[2k], out[2k+1] = Re, Im of X[k] for
 * 1 <= k < n/2. X[k] = sum_t x[t] e^(-2 pi i k t / n), unscaled.
 * The inverse is unscaled too: inverse(forward(x)) = n x. Callers fold 1/n into whatever they
 * multiply the spectrum by (dsp_pconv does it into its filter spectra).
 *
 * Twiddles: one generated table (dsp_fft_tables.c, tools/design/fft_twiddles.py), so every
 * platform uses the same values and the output is bit-identical between the PC and the target.
 * Assumptions: in and out may be the same buffer; otherwise they must not overlap.
 * Latency: none (a block transform). Cycles: docs/results/bench_fft.md.
 */
#ifndef DSP_FFT_H
#define DSP_FFT_H

#include <stdint.h>

enum { kDspFftMaxN = 2048, kDspFftTableLen = kDspFftMaxN / 2 };

extern const float kDspFftCos[kDspFftTableLen];
extern const float kDspFftSin[kDspFftTableLen];

typedef struct {
    int32_t n;      /* Real points. */
    int32_t log2_m; /* log2 of the complex size n / 2. */
} DspRfftF32;

/* Returns 0, or -1 unless n is a power of two in [16, 2048]. */
int32_t dsp_rfft_f32_init(DspRfftF32 *fft, int32_t n);
void dsp_rfft_f32_forward(const DspRfftF32 *fft, const float *in, float *out);
/* Packed spectrum in, n times the time signal out. */
void dsp_rfft_f32_inverse(const DspRfftF32 *fft, const float *in, float *out);

#endif
