/* Headphone crossfeed: each ear also hears the other channel, low-passed and a little late, as
 * it would from a pair of speakers. The idea is Bauer's (1961); the structure below, a low-pass
 * into the far ear and a matching lift of the near ear's highs, is the one bs2b uses [Verify].
 *
 *   lp = LP(x)                          one-pole low-pass, corner fc (default 700 Hz)
 *   y  = ((1 + g) x - g lp + g lp_opposite[n - D]) / (1 + g)
 * which is the near ear's own signal with its highs lifted, x + g (x - lp), plus the other
 * channel's low-passed signal g lp_opposite, D samples late, all scaled by 1 / (1 + g).
 * Computed as the same thing rearranged, with h = g / (1 + g):
 *   y  = x + h (lp_opposite[n - D] - lp)
 * one multiply-add per ear, and only h ramps when the amount changes, so a centred source stays
 * exact during a ramp too (ramping g and 1 / (1 + g) separately bumped it by 0.47 dB half-way).
 * The delayed low-pass is the low-pass of the delayed signal (both are linear and time-invariant),
 * so one low-pass per channel serves both paths and the delay line holds lp.
 *
 * The delay: D = 0 by default. The low-pass itself delays the far ear's low frequencies by its
 * group delay, a / (1 - a) samples at DC: 0.22 ms at 700 Hz, about the time difference between
 * the ears for a speaker 30 degrees off centre [Verify]. With D = 0 a centred (mono) source passes
 * unchanged, because lp_opposite - lp is then exactly 0. An explicit delay
 * (dsp_crossfeed_f32_set_delay_us) breaks that cancellation: measured at 48 kHz and full amount, a
 * centred source then dips by 1.4 dB at 1.7 kHz for 100 us and by 3.5 dB at 890 Hz for 300 us
 * (tests/unit/test_crossfeed.py). That colours every centred vocal, so it is not the default.
 *
 * g = amount x kDspCrossfeedMaxGain (0.596, -4.5 dB: bs2b's default level difference between the
 * ears at low frequencies [Verify]). What it does, at full amount:
 *   - a centred (mono) source: unchanged with D = 0 (to float rounding); see above for D > 0;
 *   - a hard-panned source: the near ear's lows drop by 1 / (1 + g) (-4.1 dB), its highs stay at
 *     unity; the far ear gets the lows at g / (1 + g) (-8.5 dB), D samples later.
 * amount 0 (or off) passes the input through bit for bit once the ramp has finished; the filters
 * and the delay line keep running, so turning it on starts from a filled state.
 * h moves linearly over the ramp time when the amount changes.
 *
 * Assumptions: stereo; any block size; in and out may be the same buffers.
 * Latency: 0 samples (the near ear is not delayed). Cycles: self-test case crossfeed_f32.
 */
#ifndef DSP_CROSSFEED_H
#define DSP_CROSSFEED_H

#include "dsp/dsp_fx_common.h"

#include <stddef.h>
#include <stdint.h>

#define DSP_CROSSFEED_MAX_GAIN 0.596f
enum { kDspCrossfeedRing = 256 }; /* A power of two: up to 255 samples, 2.6 ms at 96 kHz. */

typedef struct {
    float sample_rate_hz;
    int32_t ramp_samples;
    int32_t delay;           /* D, samples. */
    DspOnePoleF32 lp[2];
    float ring[2][kDspCrossfeedRing];
    int32_t pos;
    DspRampF32 h;            /* g / (1 + g) */
} DspCrossfeedF32;

/* Amount 0, fc 700 Hz, no explicit delay. */
void dsp_crossfeed_f32_init(DspCrossfeedF32 *xf, float sample_rate_hz, float ramp_ms);
/* Clears the filters and the delay line; the amount jumps to its target. */
void dsp_crossfeed_f32_reset(DspCrossfeedF32 *xf);
/* 0 to 1 (clamped); 0 is off. */
void dsp_crossfeed_f32_set_amount(DspCrossfeedF32 *xf, float amount);
void dsp_crossfeed_f32_set_cutoff(DspCrossfeedF32 *xf, float fc_hz);
/* Rounded to whole samples, clamped to 0 to kDspCrossfeedRing - 1. */
void dsp_crossfeed_f32_set_delay_us(DspCrossfeedF32 *xf, float delay_us);
void dsp_crossfeed_f32_process(DspCrossfeedF32 *xf, const float *in_l, const float *in_r,
                               float *out_l, float *out_r, size_t n_frames);

#endif
