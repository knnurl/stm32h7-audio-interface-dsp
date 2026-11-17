/* Soft saturation: y = tanh(d x) / tanh(d), d = 10^(drive_db / 20).
 * The normalisation maps full scale to full scale, so turning the drive up adds harmonics
 * without changing the peak level. Small signals get a gain of d / tanh(d).
 *
 * Aliasing is the problem with any waveshaper: it makes harmonics above Nyquist, which fold back
 * as inharmonic tones. Four ways to run it, compared in docs/results/b6_aliasing.md:
 *   kDspSatPlain  at the sample rate: no protection;
 *   kDspSatOs2    at 2x inside dsp_oversample: harmonics up to 1.5 fs are filtered before the
 *                 way down;
 *   kDspSatOs4    at 4x;
 *   kDspSatAdaa   first-order antiderivative anti-aliasing at the sample rate:
 *                   y[n] = (F(x[n]) - F(x[n-1])) / (x[n] - x[n-1]),  F' = f,
 *                 with F(x) = log cosh(d x) / (d tanh d) evaluated in double, and the midpoint
 *                 f((x[n] + x[n-1]) / 2) when the two samples are within 1e-6.
 * Latency (base-rate samples): plain 0, ADAA 0.5, 2x 41, 4x 46.5. The fractional ones cannot be
 * matched by an integer delay on a dry path, so a parallel dry/wet blend would comb-filter.
 * ADAA's small-signal response is the average of two samples, |cos(w/2)|: -3 dB at fs/4, -11.7
 * dB at 20 kHz at a 48 kHz rate. Changing the drive is not smoothed here; the caller ramps it.
 *
 * Assumptions: mono; `in` and `out` may be the same buffer. The shaper is dsp_fast_tanhf
 * (absolute error at most 3e-7 against tanh): the C library's tanhf was measured on the M7 as the
 * larger part of the 4x saturator's cost (docs/results/budget_target.md). ADAA's antiderivative
 * stays in double with the C library.
 * Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_SATURATE_H
#define DSP_SATURATE_H

#include "dsp/dsp_oversample.h"

#include <stddef.h>
#include <stdint.h>

typedef enum {
    kDspSatPlain = 0,
    kDspSatOs2 = 1,
    kDspSatOs4 = 2,
    kDspSatAdaa = 3,
} DspSatMode;

typedef struct {
    int32_t mode;
    float drive;     /* d */
    float norm;      /* 1 / tanh(d) */
    double adaa_x;   /* Previous input. */
    double adaa_f;   /* F of the previous input. */
    DspOversampleF32 os;
    float buf[4 * kDspOversampleMaxBlock];
} DspSaturatorF32;

void dsp_saturator_f32_init(DspSaturatorF32 *sat, int32_t mode, float drive_db);
void dsp_saturator_f32_set_drive(DspSaturatorF32 *sat, float drive_db);
void dsp_saturator_f32_reset(DspSaturatorF32 *sat);
float dsp_saturator_f32_shape(const DspSaturatorF32 *sat, float x); /* The static curve. */
void dsp_saturator_f32_process(DspSaturatorF32 *sat, const float *in, float *out,
                               size_t n_frames);
float dsp_saturator_f32_latency(const DspSaturatorF32 *sat);

#endif
