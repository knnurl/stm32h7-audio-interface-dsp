/* Feed-forward compressor, after Giannoulis, Massberg and Reiss, "Digital dynamic range
 * compressor design: a tutorial and analysis" (JAES 60(6), 2012).
 *
 * Their recommended arrangement, "log domain, smooth branching peak detector":
 *   x_dB  = 20 log10 |x_sc|                         instantaneous level of the side chain
 *   x_G   = static curve (threshold T, ratio R, knee W):
 *             x_dB                                   below the knee
 *             x_dB + (1/R - 1)(x_dB - T + W/2)^2/(2W) inside it
 *             T + (x_dB - T)/R                       above it
 *   x_L   = x_dB - x_G                              wanted gain reduction, >= 0
 *   y_L   = branching one-pole on x_L: attack when rising, release when falling
 *   gain  = 10^((makeup - y_L) / 20)
 * Smoothing the gain reduction in dB, rather than the level, keeps attack and release times
 * independent of the ratio and threshold, and gives a smooth release. The side chain is the
 * input itself, optionally through a high-pass so bass does not pump the compressor.
 *
 * Times are time constants (63 % of a step). Tools that quote 10 to 90 % rise times (MATLAB, the
 * Phil's Lab compressor) use exp(-2.2 / (t fs)): their times are 2.2 times ours.
 * The detector is instantaneous, so on bass with a short release the gain moves within each
 * cycle and distorts: measured in tests/unit/test_dynamics.py and docs/notes/dynamics.md.
 * Makeup can take the gain above 1; the limiter downstream catches overs.
 * Per-sample log and exp use dsp_fastmath (1e-4 dB).
 * Assumptions: mono; `in` and `out` may be the same buffer. Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_COMP_H
#define DSP_COMP_H

#include "dsp/dsp_biquad.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    float threshold_db;
    float ratio;   /* 1 or more; 1 is no compression. */
    float knee_db; /* 0 for a hard knee. */
    float attack_ms;
    float release_ms;
    float makeup_db;
    float sidechain_hpf_hz; /* 0: off. */
} DspCompParams;

typedef struct {
    float sample_rate_hz;
    DspCompParams params;
    float slope; /* 1 / ratio - 1 */
    float attack_coef;
    float release_coef;
    float reduction_db; /* y_L: the smoothed gain reduction, for metering. */
    int32_t hpf_on;
    DspBiquadCoefsF32 hpf;
    DspBiquadStateF32 hpf_state;
} DspCompF32;

void dsp_comp_f32_init(DspCompF32 *comp, float sample_rate_hz, const DspCompParams *params);
/* Applies new parameters, keeping the state (no click). */
void dsp_comp_f32_set_params(DspCompF32 *comp, const DspCompParams *params);
void dsp_comp_f32_reset(DspCompF32 *comp);
/* The static curve: the output level in dB for a steady input level, makeup included. */
float dsp_comp_f32_static_db(const DspCompF32 *comp, float level_db);
void dsp_comp_f32_process(DspCompF32 *comp, const float *in, float *out, size_t n_frames);

#endif
