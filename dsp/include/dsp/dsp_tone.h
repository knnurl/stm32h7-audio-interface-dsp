/* Tone control behind the BASS, MID and TREBLE knobs: a low shelf, a peak and a high shelf on
 * one stereo bus, -12 to +12 dB each. Monitors and headphones only; never recorded (SPEC 2).
 *
 * Default corner frequencies (a proposal the owner confirms in batch 3): low shelf 100 Hz,
 * peak 1 kHz with Q 0.7, high shelf 10 kHz; shelf slope 1.
 *
 * Each band's gain is smoothed in dB by a one-pole updated once per block (20 ms time
 * constant), and the band's coefficients are redesigned once per block from the smoothed gain.
 * The smoothed gain snaps to its target when within 0.001 dB, so it arrives exactly.
 *
 * Flat at centre, exactly: a band at 0 dB whose state has decayed below 1e-9 is skipped, so
 * with all three at 0 dB the bus passes the signal bit for bit. Leaving 0 dB starts the band
 * from cleared state, which is exact because a skipped band holds no signal. Arriving at 0 dB
 * keeps the band running (with its 0 dB design, the identity response) until its state has
 * decayed, so its last transient is not cut off.
 *
 * Arithmetic: float in and out, double coefficients and state (see dsp_peq.h for why).
 *
 * Assumptions: the two channels share coefficients; inputs and outputs may alias pairwise.
 * Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): not yet measured; the redesign costs a cos, a sin and a pow
 * per moving band per block.
 */
#ifndef DSP_TONE_H
#define DSP_TONE_H

#include "dsp/dsp_biquad.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspToneBands = 3 };
typedef enum { kDspToneBass = 0, kDspToneMid = 1, kDspToneTreble = 2 } DspToneBand;

typedef struct {
    float sample_rate_hz;
    float smoothing_ms;
    float freq_hz[kDspToneBands];
    float target_db[kDspToneBands];
    float smoothed_db[kDspToneBands];
    int32_t active[kDspToneBands];
    int32_t dirty[kDspToneBands]; /* Coefficients need a redesign. */
    DspBiquadCoefsF64 coefs[kDspToneBands];
    DspBiquadStateF64 state[2][kDspToneBands]; /* [channel][band] */
} DspToneF32;

void dsp_tone_f32_init(DspToneF32 *tone, float sample_rate_hz);
/* Corner frequencies; takes effect at the next block. */
void dsp_tone_f32_set_freqs(DspToneF32 *tone, float bass_hz, float mid_hz, float treble_hz);
/* Clamped to -12..+12 dB. */
void dsp_tone_f32_set_db(DspToneF32 *tone, int32_t band, float gain_db);
/* Jumps every band to its target and clears the state. */
void dsp_tone_f32_reset(DspToneF32 *tone);
void dsp_tone_f32_process(DspToneF32 *tone, const float *in_l, const float *in_r, float *out_l,
                          float *out_r, size_t n_frames);

#endif
