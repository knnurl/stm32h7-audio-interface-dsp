/* THE OWNER'S EXERCISE: replace this pass-through stub with the tremolo that
 * dsp/include/dsp/dsp_fx_tremolo.h specifies (docs/exercises/EX8b_tremolo.md).
 * Until then the effect slot's tremolo passes audio through unchanged, and
 * tests/exercises/test_ex8b_tremolo.py fails. */
#include "dsp/dsp_fx_tremolo.h"

void dsp_fx_tremolo_f32_init(DspFxTremoloF32 *fx, float sample_rate_hz) {
    fx->sample_rate_hz = sample_rate_hz;
    fx->dry = 0.0f;
    dsp_lfo_f32_init(&fx->lfo, sample_rate_hz, kDspLfoSine);
    fx->right_offset = 0u;
    dsp_ramp_jump(&fx->depth, 0.5f);
}

void dsp_fx_tremolo_f32_reset(DspFxTremoloF32 *fx) { (void)fx; }

void dsp_fx_tremolo_f32_set_amount(DspFxTremoloF32 *fx, float depth) {
    (void)fx;
    (void)depth;
}

void dsp_fx_tremolo_f32_set_rate(DspFxTremoloF32 *fx, float rate_hz) {
    (void)fx;
    (void)rate_hz;
}

void dsp_fx_tremolo_f32_set_shape(DspFxTremoloF32 *fx, int32_t shape, float edge_cycles) {
    (void)fx;
    (void)shape;
    (void)edge_cycles;
}

void dsp_fx_tremolo_f32_set_stereo_phase(DspFxTremoloF32 *fx, float cycles) {
    (void)fx;
    (void)cycles;
}

void dsp_fx_tremolo_f32_sync(DspFxTremoloF32 *fx, double beats, float beats_per_cycle,
                             float bpm) {
    (void)fx;
    (void)beats;
    (void)beats_per_cycle;
    (void)bpm;
}

void dsp_fx_tremolo_f32_process(DspFxTremoloF32 *fx, const float *in_l, const float *in_r,
                                float *wet_l, float *wet_r, size_t n_frames) {
    (void)fx;
    for (size_t i = 0; i < n_frames; ++i) {
        wet_l[i] = in_l[i];
        wet_r[i] = in_r[i];
    }
}
