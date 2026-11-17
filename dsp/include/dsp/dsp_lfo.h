/* Low-frequency oscillator for the modulation effects.
 *
 * Phase: a 32-bit accumulator (one cycle = 2^32), so the rate resolution is fs / 2^32 (1.1e-5 Hz
 * at 48 kHz) and the output is bit-identical on every platform. Rounding the increment drifts
 * the phase by at most 0.5 / 2^32 cycles per sample (0.04 cycles in an hour at 96 kHz), so a
 * tempo-synced LFO is re-phased from the tempo's beat position (dsp_lfo_f32_sync) once per
 * block or bar rather than left free-running.
 *
 * Shapes, all in [-1, 1], rising through 0 at phase 0:
 *   sine      odd polynomial of degree 7 on a quarter cycle, max error 8e-7 (measured,
 *             tests/unit/test_lfo_svf.py); peaks exactly 1;
 *   triangle  peaks at phase 0.25 and 0.75;
 *   square    rounded: each edge is half a sine cycle lasting `edge` cycles (0.001 to 0.5;
 *             0.5 gives the sine, small values approach a hard square);
 *   ramp      rising from -1 at phase 0.5 to 1 just before the next 0.5; one hard edge.
 *
 * Assumptions: one value per sample; no math.h in the per-sample path.
 * Latency: 0. Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_LFO_H
#define DSP_LFO_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    kDspLfoSine = 0,
    kDspLfoTriangle = 1,
    kDspLfoSquare = 2,
    kDspLfoRamp = 3,
} DspLfoShape;

typedef struct {
    float sample_rate_hz;
    int32_t shape;
    float edge;      /* Rounded square: edge length in cycles. */
    float edge_gain; /* 0.5 / edge. */
    uint32_t phase;
    uint32_t inc;
} DspLfoF32;

void dsp_lfo_f32_init(DspLfoF32 *lfo, float sample_rate_hz, int32_t shape);
void dsp_lfo_f32_set_shape(DspLfoF32 *lfo, int32_t shape);
void dsp_lfo_f32_set_edge(DspLfoF32 *lfo, float edge_cycles);
void dsp_lfo_f32_set_rate(DspLfoF32 *lfo, float rate_hz);
/* Rate from a tempo: one cycle every `beats_per_cycle` beats (1 = a quarter note at 4/4). */
void dsp_lfo_f32_set_tempo(DspLfoF32 *lfo, float bpm, float beats_per_cycle);
/* Phase in cycles, [0, 1). */
void dsp_lfo_f32_set_phase(DspLfoF32 *lfo, double cycles);
double dsp_lfo_f32_phase(const DspLfoF32 *lfo);
/* Tempo sync: phase = frac(beats / beats_per_cycle + offset_cycles). `beats` is the tempo's
 * beat position at the sample about to be processed. */
void dsp_lfo_f32_sync(DspLfoF32 *lfo, double beats, float beats_per_cycle, float offset_cycles);
/* The shape at a given phase (2^32 per cycle), without advancing. */
float dsp_lfo_f32_value_at(const DspLfoF32 *lfo, uint32_t phase);
/* One value per sample, advancing the phase. */
void dsp_lfo_f32_process(DspLfoF32 *lfo, float *out, size_t n_frames);

static inline float dsp_lfo_f32_next(DspLfoF32 *lfo) {
    const float v = dsp_lfo_f32_value_at(lfo, lfo->phase);
    lfo->phase += lfo->inc;
    return v;
}

#endif
