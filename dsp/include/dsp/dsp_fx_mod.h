/* The modulated-delay and all-pass effects: chorus, flanger, phaser. All stereo, all driven by
 * one dsp_lfo each (the right channel reads it at a phase offset), so tempo sync is
 * dsp_lfo_f32_sync on `lfo` and the rate is dsp_lfo_f32_set_rate or _set_tempo.
 *
 * Chorus: two voices per channel at 20 ms +/- depth, depth = 7 ms x amount, the voices half a
 * cycle apart; the right channel's voices are offset by spread / 4 cycles. Wet = 0.7 x amount x
 * the mean of the voices; dry 1. Reads: third-order Lagrange. Memory: 2 x (28 ms + 4) samples.
 * FX AMOUNT: depth and mix together.
 *
 * Flanger: one delay per channel swept linearly by a triangle LFO between 0.5 ms and
 * 0.5 + 9.5 x amount ms, with feedback fb in [-0.9, 0.9]: line <- x + fb r. Wet 0.7 r,
 * dry 0.7, so the deepest notch is full cancellation. Right channel a quarter cycle on. Memory:
 * 2 x (10.5 ms + 4) samples. FX AMOUNT: depth.
 *
 * Phaser: 4 or 8 first-order all-pass sections, y = c x + s, s = x - c y,
 * c = (t - 1) / (t + 1), t = tan(pi fc / fs) (#162's coefficient), with fc swept exponentially
 * from 200 Hz up by 5 x amount octaves; feedback fb in [-0.9, 0.9] from the last section into
 * the first. Wet 0.5 x the chain, dry 0.5: notches where the chain is 180 degrees out. c is
 * updated every kDspFxSubBlock samples with the Pade tan of dsp_svf and dsp_fast_exp2f (no
 * math.h per sample). No memory. FX AMOUNT: depth (the sweep's span).
 *
 * Assumptions: stereo; any block size. Latency: 0 on the dry path; the wet path is the effect.
 * Cycles: not yet measured.
 */
#ifndef DSP_FX_MOD_H
#define DSP_FX_MOD_H

#include "dsp/dsp_delayline.h"
#include "dsp/dsp_fx_common.h"
#include "dsp/dsp_lfo.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspPhaserMaxStages = 8 };

typedef struct {
    float sample_rate_hz;
    float dry;
    DspDelaylineF32 line[2];
    DspLfoF32 lfo;
    uint32_t right_offset; /* Phase offset of the right channel's voices. */
    DspRampF32 amount;
} DspFxChorusF32;

typedef struct {
    float sample_rate_hz;
    float dry;
    DspDelaylineF32 line[2];
    DspLfoF32 lfo;
    float feedback;
    DspRampF32 amount;
} DspFxFlangerF32;

typedef struct {
    float sample_rate_hz;
    float dry;
    DspLfoF32 lfo;
    int32_t stages;
    float feedback;
    DspRampF32 amount;
    float coef[2];
    float state[2][kDspPhaserMaxStages];
    float last[2]; /* The chain's previous output, for the feedback. */
} DspFxPhaserF32;

/* Memory each needs at a sample rate, in floats. */
int32_t dsp_fx_chorus_f32_mem_needed(float sample_rate_hz);
int32_t dsp_fx_flanger_f32_mem_needed(float sample_rate_hz);

/* init returns 0, or -1 if the memory is too small (see mem_needed). */
int32_t dsp_fx_chorus_f32_init(DspFxChorusF32 *fx, float sample_rate_hz, float *mem,
                               int32_t mem_len);
void dsp_fx_chorus_f32_reset(DspFxChorusF32 *fx, int32_t clear_memory);
void dsp_fx_chorus_f32_set_amount(DspFxChorusF32 *fx, float amount);
void dsp_fx_chorus_f32_set_spread(DspFxChorusF32 *fx, float spread);
void dsp_fx_chorus_f32_process(DspFxChorusF32 *fx, const float *in_l, const float *in_r,
                               float *wet_l, float *wet_r, size_t n_frames);

int32_t dsp_fx_flanger_f32_init(DspFxFlangerF32 *fx, float sample_rate_hz, float *mem,
                                int32_t mem_len);
void dsp_fx_flanger_f32_reset(DspFxFlangerF32 *fx, int32_t clear_memory);
void dsp_fx_flanger_f32_set_amount(DspFxFlangerF32 *fx, float amount);
void dsp_fx_flanger_f32_set_feedback(DspFxFlangerF32 *fx, float feedback);
void dsp_fx_flanger_f32_process(DspFxFlangerF32 *fx, const float *in_l, const float *in_r,
                                float *wet_l, float *wet_r, size_t n_frames);

void dsp_fx_phaser_f32_init(DspFxPhaserF32 *fx, float sample_rate_hz);
void dsp_fx_phaser_f32_reset(DspFxPhaserF32 *fx);
void dsp_fx_phaser_f32_set_amount(DspFxPhaserF32 *fx, float amount);
void dsp_fx_phaser_f32_set_stages(DspFxPhaserF32 *fx, int32_t stages); /* 4 or 8. */
void dsp_fx_phaser_f32_set_feedback(DspFxPhaserF32 *fx, float feedback);
/* The all-pass coefficient for a corner frequency, as the phaser computes it. */
float dsp_fx_phaser_coef(float sample_rate_hz, float fc_hz);
void dsp_fx_phaser_f32_process(DspFxPhaserF32 *fx, const float *in_l, const float *in_r,
                               float *wet_l, float *wet_r, size_t n_frames);

#endif
