/* Gain with smoothing: the linear gain follows its target through a one-pole low-pass, so a
 * change never clicks.
 *
 *   g[n] = g[n-1] + coef * (target - g[n-1]),  coef = 1 - exp(-1 / (tau * fs))
 *   y[n] = x[n] * g[n]
 *
 * Assumptions: mono; `in` and `out` may be the same buffer; the smoothing time is the time
 * constant tau (63 % of a step), not the time to settle.
 * Numerical limit: in float32 the recursion stalls just short of its target (3.6e-6 away for
 * 5 ms at 48 kHz, -109 dBFS). At the end of a block in which it has stalled, the gain is set to
 * the target exactly. That step is the only way the output depends on the block size.
 * Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): not yet measured (docs/results/bench_b1.md).
 */
#ifndef DSP_GAIN_H
#define DSP_GAIN_H

#include <stddef.h>

typedef struct {
    float gain;   /* The gain in use now, linear. */
    float target; /* Where it is heading, linear. */
    float coef;   /* Share of the remaining distance covered per sample, 0 to 1. */
} DspGainF32;

/* Unity gain, settled. A smoothing time of 0 ms or less means no smoothing. */
void dsp_gain_f32_init(DspGainF32 *state, float sample_rate_hz, float smoothing_ms);
/* Jumps to the target without a ramp. */
void dsp_gain_f32_reset(DspGainF32 *state);
void dsp_gain_f32_set_linear(DspGainF32 *state, float gain_linear);
void dsp_gain_f32_set_db(DspGainF32 *state, float gain_db);
void dsp_gain_f32_process(DspGainF32 *state, const float *in, float *out, size_t n_frames);

#endif
