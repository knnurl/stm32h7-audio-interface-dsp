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
 * Arithmetic: float in and out, double-precision coefficients and ramps. The high-pass and bands
 * 1 and 2 run with double state (dsp_biquad_f64_section): float32 state gives only 59 to 111 dB
 * signal-to-noise on low-frequency sections, double about 152 dB, the floor of the float32
 * output itself (docs/results/b3_filter_noise.md). Bands 3 and 4 run in float32
 * (dsp_biquad_f32_section, coefficients rounded from the double ones each block) at sample rates
 * up to 48 kHz, where they sit at DSP_PEQ_F32_MIN_HZ (2.5 kHz) or above. There, with band 3 at
 * its worst (a peak, Q 10, +15 dB) and band 4 a high shelf at its worst, both at the corner, the
 * arithmetic noise stays 113.9 dB under the signal, and each rounded section's response within
 * 0.0001 dB of the double design (docs/results/peq_f32_noise.md). At 2 kHz the same pair gave
 * 110.4 dB on the kernel and 109.6 dB through the PEQ, too close to the 110 dB criterion; at
 * 96 kHz float32 would need 5 kHz, so above 48 kHz every section stays double. Two peaks stacked at the corner (not possible through the
 * registry, whose band 4 is always a high shelf) give 109.7 dB at 2.5 kHz. The float32 bands are
 * budget option D (SPEC decision log, 2026-11-18): about 17 cycles per sample per section on the
 * M7 against 56 in double.
 * A float32 band set below DSP_PEQ_F32_MIN_HZ is raised to it; the registry's range (2.5 kHz to
 * 20 kHz for bands 3 and 4) never asks for less.
 *
 * Off is the identity section, which passes the signal bit for bit.
 * Assumptions: `in` and `out` may be the same buffer. Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): self-test case peq_f32 (one channel, all five sections on).
 */
#ifndef DSP_PEQ_H
#define DSP_PEQ_H

#include "dsp/dsp_biquad.h"

#include <stddef.h>
#include <stdint.h>

enum {
    kDspPeqBands = 4,
    kDspPeqSections = kDspPeqBands + 1,
    kDspPeqF32FirstBand = 2, /* Bands 3 and 4 (indices 2 and 3) may run in float32. */
};
#define DSP_PEQ_F32_MIN_HZ 2500.0f   /* Lowest corner of a float32 band. */
#define DSP_PEQ_F32_MAX_FS_HZ 48000.0f /* Float32 bands only up to this sample rate. */

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
    DspBiquadStateF32 state_f32[kDspPeqSections]; /* Used by the float32 sections only. */
    int32_t first_f32; /* First section run in float32; kDspPeqSections when none. */
} DspPeqF32;

/* All sections off, state cleared. ramp_blocks of 1 or less means changes apply at once. Bands 3
 * and 4 run in float32 when sample_rate_hz is at most DSP_PEQ_F32_MAX_FS_HZ. */
void dsp_peq_f32_init(DspPeqF32 *peq, float sample_rate_hz, int32_t ramp_blocks);
/* Clears the state and jumps to the target coefficients. */
void dsp_peq_f32_reset(DspPeqF32 *peq);
/* 0 Hz turns the high-pass off. */
void dsp_peq_f32_set_highpass(DspPeqF32 *peq, float cutoff_hz);
void dsp_peq_f32_set_band(DspPeqF32 *peq, int32_t index, const DspPeqBand *band);
void dsp_peq_f32_process(DspPeqF32 *peq, const float *in, float *out, size_t n_frames);

#endif
