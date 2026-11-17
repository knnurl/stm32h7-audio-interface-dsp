/* Echo: a stereo feedback delay (a feedback comb filter, #140's structure) with a tone filter in
 * the loop, optional ping-pong, and a delay time that glides.
 *
 *   per channel: r = line[d];  f = hp(lp(r));  line <- x + fb f;  wet = amount r
 *   ping-pong:   line_l <- (x_l + x_r) / 2 + fb f_r;  line_r <- fb f_l  (repeats alternate)
 * Loop gain is fb times the tone filters' gain (at most 1), so the loop is stable for fb < 1;
 * fb is clamped to [0, 0.95].
 * Tone: a one-pole low-pass from 1.5 kHz (tone 0) to 18 kHz (tone 1), exponential, and a fixed
 * one-pole high-pass at 80 Hz, so the repeats darken and thin out as they decay.
 *
 * Storage and rate (owner's decision 2026-11-17, docs/results/b8b_memory.md):
 *   - the lines are 16-bit (DspDelaylineS16: 2^13 per 1.0, +/-4.0, rounded, no dither), so each
 *     repeat is requantised; noise measured in tests/unit/test_fx_echo16.py;
 *   - the core runs at fs for fs <= 48 kHz and at fs / 2 for 88.2 and 96 kHz, between the
 *     batch 6 83-tap half-band filters (down on the way in, up on the way out). Their delay,
 *     DSP_ECHO_RESAMPLE_LATENCY samples at fs, is taken off the line's delay, so the first
 *     repeat lands at the set time. Content between 20 and 24 kHz at a 96 kHz input does not
 *     reach the repeats (the half-band's passband ends at 20 kHz).
 * Time: set in ms (the control level converts a note value and the tempo to ms). A change glides
 * linearly over 50 ms at the internal rate, bending the pitch of what is in the line, as a tape
 * echo does. Reads are third-order Lagrange (docs/results/b8b_interp.md); at rest the delay is
 * rounded to whole internal samples, so the read is exact and the repeats keep their top end
 * (a half-sample read is -5.3 dB at 18 kHz); the time is then within one sample at 96 kHz.
 * Memory: caller-provided floats, used as int16 storage, two lines of mem_len int16 samples
 * between them; dsp_fx_echo_f32_mem_needed gives the floats for a time. 0.75 s at 48 or 96 kHz
 * is 36004 floats (141 KB).
 *
 * FX AMOUNT: the wet level, 0 to 1; the dry stays at 1 (`dry`).
 * Assumptions: stereo; any block size (at half rate, odd blocks are carried over by one-sample
 * holds, which the latency above includes).
 * Latency: 0 on the dry path. Cycles: not yet measured.
 */
#ifndef DSP_FX_ECHO_H
#define DSP_FX_ECHO_H

#include "dsp/dsp_delayline.h"
#include "dsp/dsp_fx_common.h"
#include "dsp/dsp_oversample.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspEchoChunk = 32 }; /* Internal samples per pass at half rate. */
/* Down and up half-band filters, 41 samples each at fs, plus the one-sample output hold. */
#define DSP_ECHO_RESAMPLE_LATENCY 83.0f

typedef struct {
    float sample_rate_hz; /* Outside. */
    float rate_hz;        /* Of the core: fs or fs / 2. */
    int32_t half_rate;
    float dry;
    DspDelaylineS16 line[2];
    float max_delay;      /* Internal samples. */
    float delay;
    float delay_target;
    float glide_step;
    int32_t glide_left;
    float feedback;
    int32_t ping_pong;
    DspOnePoleF32 lp[2];
    DspOnePoleF32 hp[2];
    DspRampF32 wet;
    DspHalfbandDownF32 down[2];
    DspHalfbandUpF32 up[2];
    float in_hold[2];
    int32_t in_has;
    float out_hold[2];
    int32_t out_has;
    float hi[2][2 * kDspEchoChunk];
    float lo_in[2][kDspEchoChunk];
    float lo_out[2][kDspEchoChunk];
} DspFxEchoF32;

/* Floats of memory for `seconds` of echo at a sample rate. */
int32_t dsp_fx_echo_f32_mem_needed(float sample_rate_hz, float seconds);
/* Returns 0, or -1 if the memory is too small for 10 ms. */
int32_t dsp_fx_echo_f32_init(DspFxEchoF32 *fx, float sample_rate_hz, float *mem, int32_t mem_len);
/* Clears the filters and resamplers; with clear_memory, zeroes the lines too. */
void dsp_fx_echo_f32_reset(DspFxEchoF32 *fx, int32_t clear_memory);
void dsp_fx_echo_f32_set_amount(DspFxEchoF32 *fx, float amount);
void dsp_fx_echo_f32_set_time_ms(DspFxEchoF32 *fx, float time_ms);
void dsp_fx_echo_f32_set_feedback(DspFxEchoF32 *fx, float feedback);
void dsp_fx_echo_f32_set_tone(DspFxEchoF32 *fx, float tone);
void dsp_fx_echo_f32_set_ping_pong(DspFxEchoF32 *fx, int32_t on);
float dsp_fx_echo_f32_max_time_ms(const DspFxEchoF32 *fx);
void dsp_fx_echo_f32_process(DspFxEchoF32 *fx, const float *in_l, const float *in_r,
                             float *wet_l, float *wet_r, size_t n_frames);

#endif
