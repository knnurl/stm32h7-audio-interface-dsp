/* Parametric EQ: a high-pass (second-order Butterworth, or off) and four bands, each a peak, a
 * low shelf, a high shelf, or off. Float, mono; a stereo use holds two instances.
 *
 * Changing a setting does not switch coefficients at once: the new coefficients are reached by
 * linear interpolation, one step per call of `process` (one block), over `ramp_blocks` blocks.
 * Interpolating coefficients is safe for stability at every step: the stable region of (a1, a2)
 * is a triangle, which is convex, so any blend of two stable sections is stable. Very fast
 * repeated changes are a different matter (switching between stable systems is not guaranteed
 * stable); settings change at control rate, not audio rate.
 *
 * Arithmetic: float in and out, double-precision coefficients and state (dsp_biquad_f64_section).
 * Float32 state gives only 59 to 111 dB signal-to-noise on low-frequency sections; double gives
 * about 152 dB, the floor of the float32 output itself (docs/results/b3_filter_noise.md).
 * Provisional until the M7 cycle cost is measured (SPEC decision log).
 *
 * Off is the identity section, which passes the signal bit for bit.
 * Assumptions: `in` and `out` may be the same buffer. Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_PEQ_H
#define DSP_PEQ_H

#include "dsp/dsp_biquad.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspPeqBands = 4, kDspPeqSections = kDspPeqBands + 1 };

typedef enum {
    kDspPeqOff = 0,
    kDspPeqPeak = 1,
    kDspPeqLowShelf = 2,
    kDspPeqHighShelf = 3,
} DspPeqBandType;

typedef struct {
    int32_t type;  /* DspPeqBandType. */
    float freq_hz;
    float gain_db;
    float q; /* Q for a peak; the slope S for a shelf. */
} DspPeqBand;

typedef struct {
    float sample_rate_hz;
    int32_t ramp_blocks;
    int32_t remaining; /* Blocks left in the current ramp. */
    DspBiquadCoefsF64 current[kDspPeqSections]; /* Section 0 is the high-pass. */
    DspBiquadCoefsF64 target[kDspPeqSections];
    DspBiquadCoefsF64 step[kDspPeqSections];
    DspBiquadStateF64 state[kDspPeqSections];
} DspPeqF32;

/* All sections off, state cleared. ramp_blocks of 1 or less means changes apply at once. */
void dsp_peq_f32_init(DspPeqF32 *peq, float sample_rate_hz, int32_t ramp_blocks);
/* Clears the state and jumps to the target coefficients. */
void dsp_peq_f32_reset(DspPeqF32 *peq);
/* 0 Hz turns the high-pass off. */
void dsp_peq_f32_set_highpass(DspPeqF32 *peq, float cutoff_hz);
void dsp_peq_f32_set_band(DspPeqF32 *peq, int32_t index, const DspPeqBand *band);
void dsp_peq_f32_process(DspPeqF32 *peq, const float *in, float *out, size_t n_frames);

#endif
