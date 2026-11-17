#include "dsp/dsp_biquad.h"

#include <string.h>

void dsp_biquad_f32_section(const DspBiquadCoefsF32 *coefs, DspBiquadStateF32 *state,
                            const float *in, float *out, size_t n_frames) {
    const float b0 = coefs->b0, b1 = coefs->b1, b2 = coefs->b2;
    const float a1 = coefs->a1, a2 = coefs->a2;
    float z1 = state->z1, z2 = state->z2;
    for (size_t i = 0; i < n_frames; ++i) {
        const float x = in[i];
        const float y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        out[i] = y;
    }
    state->z1 = z1;
    state->z2 = z2;
}

void dsp_biquad_f64_section(const DspBiquadCoefsF64 *coefs, DspBiquadStateF64 *state,
                            const float *in, float *out, size_t n_frames) {
    const double b0 = coefs->b0, b1 = coefs->b1, b2 = coefs->b2;
    const double a1 = coefs->a1, a2 = coefs->a2;
    double z1 = state->z1, z2 = state->z2;
    for (size_t i = 0; i < n_frames; ++i) {
        const double x = in[i];
        const double y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        out[i] = (float)y;
    }
    state->z1 = z1;
    state->z2 = z2;
}

void dsp_biquad_f32_init(DspBiquadF32 *filter, const DspBiquadCoefsF32 *coefs, size_t n_sections) {
    if (n_sections > kDspBiquadMaxSections) {
        n_sections = kDspBiquadMaxSections;
    }
    filter->n_sections = n_sections;
    for (size_t s = 0; s < n_sections; ++s) {
        filter->coefs[s] = coefs[s];
    }
    dsp_biquad_f32_reset(filter);
}

void dsp_biquad_f32_reset(DspBiquadF32 *filter) {
    memset(filter->state, 0, sizeof(filter->state));
}

void dsp_biquad_f32_process(DspBiquadF32 *filter, const float *in, float *out, size_t n_frames) {
    const float *src = in;
    for (size_t s = 0; s < filter->n_sections; ++s) {
        dsp_biquad_f32_section(&filter->coefs[s], &filter->state[s], src, out, n_frames);
        src = out;
    }
    if (filter->n_sections == 0 && in != out) {
        memcpy(out, in, n_frames * sizeof(float));
    }
}

static int32_t saturate32(int64_t value) {
    if (value > INT32_MAX) {
        return INT32_MAX;
    }
    if (value < INT32_MIN) {
        return INT32_MIN;
    }
    return (int32_t)value;
}

static void q31_section(const DspBiquadCoefsQ31 *c, DspBiquadStateQ31 *st, int32_t error_feedback,
                        const int32_t *in, int32_t *out, size_t n_frames) {
    const int k = 30 - (int)c->shift;
    const int64_t half = (int64_t)1 << (k - 1);
    const int64_t unit = (int64_t)1 << k;
    int32_t x1 = st->x1, x2 = st->x2, y1 = st->y1, y2 = st->y2;
    int64_t err = st->err;
    for (size_t i = 0; i < n_frames; ++i) {
        const int32_t x = in[i];
        int64_t acc = (int64_t)c->b0 * x + (int64_t)c->b1 * x1 + (int64_t)c->b2 * x2 -
                      (int64_t)c->a1 * y1 - (int64_t)c->a2 * y2;
        int64_t y;
        if (error_feedback) {
            acc += err;
            y = acc >> k;
            err = acc - y * unit;
            if (y > INT32_MAX || y < INT32_MIN) {
                err = 0; /* Saturated: the remainder means nothing. */
            }
        } else {
            y = (acc + half) >> k;
        }
        const int32_t ys = saturate32(y);
        x2 = x1;
        x1 = x;
        y2 = y1;
        y1 = ys;
        out[i] = ys;
    }
    st->x1 = x1;
    st->x2 = x2;
    st->y1 = y1;
    st->y2 = y2;
    st->err = (int32_t)err;
}

void dsp_biquad_q31_init(DspBiquadQ31 *filter, const DspBiquadCoefsQ31 *coefs, size_t n_sections,
                         int32_t error_feedback) {
    if (n_sections > kDspBiquadMaxSections) {
        n_sections = kDspBiquadMaxSections;
    }
    filter->n_sections = n_sections;
    filter->error_feedback = error_feedback ? 1 : 0;
    for (size_t s = 0; s < n_sections; ++s) {
        filter->coefs[s] = coefs[s];
    }
    dsp_biquad_q31_reset(filter);
}

void dsp_biquad_q31_reset(DspBiquadQ31 *filter) {
    memset(filter->state, 0, sizeof(filter->state));
}

void dsp_biquad_q31_process(DspBiquadQ31 *filter, const int32_t *in, int32_t *out,
                            size_t n_frames) {
    const int32_t *src = in;
    for (size_t s = 0; s < filter->n_sections; ++s) {
        q31_section(&filter->coefs[s], &filter->state[s], filter->error_feedback, src, out,
                    n_frames);
        src = out;
    }
    if (filter->n_sections == 0 && in != out) {
        memcpy(out, in, n_frames * sizeof(int32_t));
    }
}
