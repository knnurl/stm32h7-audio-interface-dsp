/* Small helpers shared by the effects: a linear parameter ramp and one-pole filters.
 *
 * Every effect writes a wet signal; the slot (dsp_fxslot) adds `dry` times the input. An effect's
 * `dry` is the dry gain its sound needs (1 for an echo, 0 for a filter or a distortion).
 * Parameters arrive once per block from the control level; the ones that would click if they
 * jumped (levels, depths, positions) are ramped linearly over kDspFxRampMs.
 * Effects that update coefficients from a modulated value do it every kDspFxSubBlock samples.
 */
#ifndef DSP_FX_COMMON_H
#define DSP_FX_COMMON_H

#include <stdint.h>

enum { kDspFxSubBlock = 16 };
#define DSP_FX_RAMP_MS 10.0f

typedef struct {
    float cur;
    float target;
    float step;
    int32_t left;
} DspRampF32;

static inline void dsp_ramp_jump(DspRampF32 *r, float v) {
    r->cur = v;
    r->target = v;
    r->step = 0.0f;
    r->left = 0;
}

/* Moves to `target` over `n` samples (at once when n <= 0). A repeated target does not restart. */
static inline void dsp_ramp_set(DspRampF32 *r, float target, int32_t n) {
    if (target == r->target) {
        return;
    }
    r->target = target;
    if (n <= 0) {
        dsp_ramp_jump(r, target);
        return;
    }
    r->step = (target - r->cur) / (float)n;
    r->left = n;
}

static inline float dsp_ramp_next(DspRampF32 *r) {
    if (r->left > 0) {
        r->cur = --r->left == 0 ? r->target : r->cur + r->step;
    }
    return r->cur;
}

static inline int32_t dsp_ramp_moving(const DspRampF32 *r) { return r->left > 0; }

/* One-pole low-pass: y = x + a (y1 - x), a = exp(-2 pi fc / fs). High-pass: x - low-pass. */
typedef struct {
    float a;
    float z;
} DspOnePoleF32;

float dsp_onepole_coef(float sample_rate_hz, float fc_hz);

static inline float dsp_onepole_lp(DspOnePoleF32 *p, float x) {
    p->z = x + p->a * (p->z - x);
    return p->z;
}

static inline float dsp_onepole_hp(DspOnePoleF32 *p, float x) { return x - dsp_onepole_lp(p, x); }

#endif
