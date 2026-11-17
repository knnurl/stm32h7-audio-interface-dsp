/* Tremolo and auto-pan. THE OWNER'S EXERCISE (docs/exercises/EX8b_tremolo.md): this header and
 * the reference model in tests/ref/fx.py are the specification; dsp/src/dsp_fx_tremolo.c is a
 * pass-through stub until he writes it.
 *
 * Gain per channel: g = 1 - depth (1 - u), u = (1 + lfo(phase)) / 2, so g runs from 1 (lfo = +1)
 * down to 1 - depth (lfo = -1). The right channel reads the LFO at phase + stereo_phase cycles:
 * 0 is a mono tremolo, 0.5 an auto-pan. Output: wet = g x; dry 0.
 * Shapes: sine, triangle, rounded square (dsp_lfo; `edge` sets the square's edge length).
 * Tempo: dsp_fx_tremolo_f32_sync(beats, beats_per_cycle) places the loudest point (lfo = +1,
 * phase 0.25) on every multiple of beats_per_cycle beats, and sets the rate from the bpm.
 * Depth changes are ramped linearly over DSP_FX_RAMP_MS.
 *
 * FX AMOUNT: depth, 0 to 1.
 * Assumptions: stereo; any block size. Latency: 0. Cycles: not yet measured.
 */
#ifndef DSP_FX_TREMOLO_H
#define DSP_FX_TREMOLO_H

#include "dsp/dsp_fx_common.h"
#include "dsp/dsp_lfo.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    float sample_rate_hz;
    float dry;             /* 0. */
    DspLfoF32 lfo;
    uint32_t right_offset; /* stereo_phase x 2^32. */
    DspRampF32 depth;
} DspFxTremoloF32;

/* Defaults: depth 0.5, 4 Hz, sine, stereo phase 0. */
void dsp_fx_tremolo_f32_init(DspFxTremoloF32 *fx, float sample_rate_hz);
void dsp_fx_tremolo_f32_reset(DspFxTremoloF32 *fx);
void dsp_fx_tremolo_f32_set_amount(DspFxTremoloF32 *fx, float depth);
void dsp_fx_tremolo_f32_set_rate(DspFxTremoloF32 *fx, float rate_hz);
void dsp_fx_tremolo_f32_set_shape(DspFxTremoloF32 *fx, int32_t shape, float edge_cycles);
void dsp_fx_tremolo_f32_set_stereo_phase(DspFxTremoloF32 *fx, float cycles);
void dsp_fx_tremolo_f32_sync(DspFxTremoloF32 *fx, double beats, float beats_per_cycle, float bpm);
void dsp_fx_tremolo_f32_process(DspFxTremoloF32 *fx, const float *in_l, const float *in_r,
                                float *wet_l, float *wet_r, size_t n_frames);

#endif
