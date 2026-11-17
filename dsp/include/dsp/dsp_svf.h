/* State-variable filter in the topology-preserving (trapezoidal) form of Zavalishin, as written
 * by Simper ("Linear trapezoidal integrated SVF", Cytomic, 2013) [Verify against the paper]:
 *   g = tan(pi fc / fs), k = 1 / Q
 *   a1 = 1 / (1 + g (g + k)), a2 = g a1, a3 = g a2
 *   v3 = v0 - ic2;  v1 = a1 ic1 + a2 v3;  v2 = ic2 + a2 ic1 + a3 v3
 *   ic1 = 2 v1 - ic1;  ic2 = 2 v2 - ic2
 *   low = v2, band = v1, high = v0 - k v1 - v2, notch = low + high
 * Why this form for anything that moves: its states are the integrators' own states, so a change
 * of g or k between samples changes how the state is used, not what it means. A direct-form
 * biquad's states are mixtures of past inputs and outputs that are only valid for the
 * coefficients that made them; under fast modulation they produce transients. Measured in
 * tests/unit/test_lfo_svf.py (test_svf_against_biquad_under_modulation).
 *
 * dsp_svf_f32_set uses tanf (coefficient code). dsp_svf_f32_set_fast replaces it with the Pade
 * approximant tan(x) ~ x (15 - x^2) / (15 - 6 x^2), for per-block modulation: g error 2.1e-4
 * below 0.25 fs and 3.2 % at the 0.45 fs clamp, a cutoff error of 0.37 % there (measured,
 * test_fast_g_error). Both clamp fc to
 * [1 Hz, 0.45 fs] and Q to [0.1, 50].
 *
 * Assumptions: mono; `in` and `out` may be the same buffer.
 * Latency: 0. Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_SVF_H
#define DSP_SVF_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    kDspSvfLow = 0,
    kDspSvfBand = 1,
    kDspSvfHigh = 2,
    kDspSvfNotch = 3,
} DspSvfMode;

typedef struct {
    float g, k, a1, a2, a3;
    float ic1, ic2;
} DspSvfF32;

void dsp_svf_f32_init(DspSvfF32 *svf, float sample_rate_hz, float fc_hz, float q);
void dsp_svf_f32_reset(DspSvfF32 *svf);
void dsp_svf_f32_set(DspSvfF32 *svf, float sample_rate_hz, float fc_hz, float q);
void dsp_svf_f32_set_fast(DspSvfF32 *svf, float sample_rate_hz, float fc_hz, float q);
/* tan(pi fc / fs) by the Pade approximant, fc clamped as above. */
float dsp_svf_fast_g(float sample_rate_hz, float fc_hz);
void dsp_svf_f32_process(DspSvfF32 *svf, int32_t mode, const float *in, float *out,
                         size_t n_frames);

static inline float dsp_svf_f32_tick(DspSvfF32 *svf, int32_t mode, float v0) {
    const float v3 = v0 - svf->ic2;
    const float v1 = svf->a1 * svf->ic1 + svf->a2 * v3;
    const float v2 = svf->ic2 + svf->a2 * svf->ic1 + svf->a3 * v3;
    svf->ic1 = 2.0f * v1 - svf->ic1;
    svf->ic2 = 2.0f * v2 - svf->ic2;
    switch (mode) {
    case kDspSvfBand:
        return v1;
    case kDspSvfHigh:
        return v0 - svf->k * v1 - v2;
    case kDspSvfNotch:
        return v0 - svf->k * v1;
    default:
        return v2;
    }
}

#endif
