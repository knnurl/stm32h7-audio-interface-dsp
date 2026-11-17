#include "dsp/dsp_lfo.h"

#include <math.h>

static const float kTwoPow32 = 4294967296.0f;

/* sin(2 pi x) for x in [-0.25, 0.25]: odd minimax polynomial, constrained to 1 at 0.25
 * (fitted in double, max error 6.8e-7; 8e-7 evaluated in float32). */
static float sin_quarter(float x) {
    const float x2 = x * x;
    return x * (6.283161163330078f +
                x2 * (-41.336708068847656f + x2 * (81.32439422607422f + x2 * -70.82131958007812f)));
}

/* Folds a signed phase in cycles, [-0.5, 0.5), to [-0.25, 0.25] about the sine's peaks. */
static float fold(float x) {
    if (x > 0.25f) {
        return 0.5f - x;
    }
    if (x < -0.25f) {
        return -0.5f - x;
    }
    return x;
}

void dsp_lfo_f32_init(DspLfoF32 *lfo, float sample_rate_hz, int32_t shape) {
    lfo->sample_rate_hz = sample_rate_hz;
    lfo->phase = 0u;
    lfo->inc = 0u;
    dsp_lfo_f32_set_shape(lfo, shape);
    dsp_lfo_f32_set_edge(lfo, 0.05f);
}

void dsp_lfo_f32_set_shape(DspLfoF32 *lfo, int32_t shape) {
    lfo->shape = (shape >= kDspLfoSine && shape <= kDspLfoRamp) ? shape : kDspLfoSine;
}

void dsp_lfo_f32_set_edge(DspLfoF32 *lfo, float edge_cycles) {
    if (!(edge_cycles >= 0.001f)) {
        edge_cycles = 0.001f; /* Also catches NaN. */
    } else if (edge_cycles > 0.5f) {
        edge_cycles = 0.5f;
    }
    lfo->edge = edge_cycles;
    lfo->edge_gain = 0.5f / edge_cycles;
}

void dsp_lfo_f32_set_rate(DspLfoF32 *lfo, float rate_hz) {
    double r = (double)rate_hz / (double)lfo->sample_rate_hz;
    if (!(r > 0.0)) {
        r = 0.0;
    } else if (r > 0.5) {
        r = 0.5;
    }
    lfo->inc = (uint32_t)(r * 4294967296.0 + 0.5);
}

void dsp_lfo_f32_set_tempo(DspLfoF32 *lfo, float bpm, float beats_per_cycle) {
    if (!(beats_per_cycle > 0.0f) || !(bpm > 0.0f)) {
        dsp_lfo_f32_set_rate(lfo, 0.0f);
        return;
    }
    dsp_lfo_f32_set_rate(lfo, bpm / 60.0f / beats_per_cycle);
}

void dsp_lfo_f32_set_phase(DspLfoF32 *lfo, double cycles) {
    double f = cycles - floor(cycles);
    if (!(f >= 0.0 && f < 1.0)) {
        f = 0.0;
    }
    lfo->phase = (uint32_t)(f * 4294967296.0);
}

double dsp_lfo_f32_phase(const DspLfoF32 *lfo) { return (double)lfo->phase / 4294967296.0; }

void dsp_lfo_f32_sync(DspLfoF32 *lfo, double beats, float beats_per_cycle, float offset_cycles) {
    if (!(beats_per_cycle > 0.0f)) {
        return;
    }
    dsp_lfo_f32_set_phase(lfo, beats / (double)beats_per_cycle + (double)offset_cycles);
}

float dsp_lfo_f32_value_at(const DspLfoF32 *lfo, uint32_t phase) {
    /* Signed phase in cycles, [-0.5, 0.5): 0 is the rising zero crossing. */
    const float x = (float)(int32_t)phase / kTwoPow32;
    switch (lfo->shape) {
    case kDspLfoTriangle:
        return 4.0f * fold(x);
    case kDspLfoSquare: {
        float y = fold(x) * lfo->edge_gain;
        y = y > 0.25f ? 0.25f : (y < -0.25f ? -0.25f : y);
        return sin_quarter(y);
    }
    case kDspLfoRamp:
        return 2.0f * x;
    default:
        return sin_quarter(fold(x));
    }
}

void dsp_lfo_f32_process(DspLfoF32 *lfo, float *out, size_t n_frames) {
    for (size_t i = 0; i < n_frames; ++i) {
        out[i] = dsp_lfo_f32_next(lfo);
    }
}
