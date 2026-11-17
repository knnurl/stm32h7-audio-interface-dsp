/* Echo: a stereo feedback delay (a feedback comb filter, #140's structure) with a tone filter in
 * the loop, optional ping-pong, and a delay time that glides.
 *
 *   per channel: r = line[d];  f = hp(lp(r));  line <- x + fb f;  wet = amount r
 *   ping-pong:   line_l <- (x_l + x_r) / 2 + fb f_r;  line_r <- fb f_l  (repeats alternate)
 * Loop gain is fb times the tone filters' gain (at most 1), so the loop is stable for fb < 1;
 * fb is clamped to [0, 0.95].
 * Tone: a one-pole low-pass from 1.5 kHz (tone 0) to 18 kHz (tone 1), exponential, and a fixed
 * one-pole high-pass at 80 Hz, so the repeats darken and thin out as they decay.
 * Time: set in ms (the control level converts a note value and the tempo to ms). A change glides
 * linearly over 50 ms, which bends the pitch of what is in the line, as a tape echo does
 * (8b.5's proposal; a cross-fade without the bend is the owner's alternative). Reads are
 * third-order Lagrange (docs/results/b8b_interp.md).
 * Memory: caller-provided, split in two equal lines; the longest time is about
 * (mem_len / 2 - 4) / fs. 0.75 s at 96 kHz needs 144016 floats (563 KB): see the memory table
 * in docs/results/b8b_memory.md.
 *
 * FX AMOUNT: the wet level, 0 to 1; the dry stays at 1 (`dry`).
 * Assumptions: stereo; any block size. Latency: 0 (the dry path). Cycles: not yet measured.
 */
#ifndef DSP_FX_ECHO_H
#define DSP_FX_ECHO_H

#include "dsp/dsp_delayline.h"
#include "dsp/dsp_fx_common.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    float sample_rate_hz;
    float dry;
    DspDelaylineF32 line[2];
    float max_delay;     /* Samples. */
    float delay;         /* Current, in samples. */
    float delay_target;
    float glide_step;
    int32_t glide_left;
    float feedback;
    int32_t ping_pong;
    DspOnePoleF32 lp[2];
    DspOnePoleF32 hp[2];
    DspRampF32 wet;
} DspFxEchoF32;

/* Returns 0, or -1 if the memory is too small for 10 ms. */
int32_t dsp_fx_echo_f32_init(DspFxEchoF32 *fx, float sample_rate_hz, float *mem, int32_t mem_len);
/* Clears the filters; with clear_memory, zeroes the lines too (time proportional to mem_len). */
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
