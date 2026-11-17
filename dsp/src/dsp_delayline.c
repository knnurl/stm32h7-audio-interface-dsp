#include "dsp/dsp_delayline.h"

#include <string.h>

int32_t dsp_delayline_f32_init(DspDelaylineF32 *dl, float *mem, int32_t len) {
    if (mem == NULL || len < 4) {
        dl->buf = NULL;
        dl->len = 0;
        dl->write = 0;
        return -1;
    }
    dl->buf = mem;
    dl->len = len;
    dsp_delayline_f32_reset(dl);
    return 0;
}

void dsp_delayline_f32_reset(DspDelaylineF32 *dl) {
    for (int32_t i = 0; i < dl->len; ++i) {
        dl->buf[i] = 0.0f;
    }
    dl->write = 0;
}

/* NaN goes to `lo`: the integer cast below would be undefined for it. */
static float clampf(float v, float lo, float hi) {
    if (!(v >= lo)) {
        return lo;
    }
    return v > hi ? hi : v;
}

float dsp_delayline_f32_read_linear(const DspDelaylineF32 *dl, float d) {
    d = clampf(d, 0.0f, (float)(dl->len - 2));
    const int32_t i = (int32_t)d;
    const float f = d - (float)i;
    const float a = dsp_delayline_f32_tap(dl, i);
    const float b = dsp_delayline_f32_tap(dl, i + 1);
    return a + f * (b - a);
}

float dsp_delayline_f32_read_lagrange(const DspDelaylineF32 *dl, float d) {
    d = clampf(d, 1.0f, (float)(dl->len - 3));
    const int32_t i = (int32_t)d;
    const float f = d - (float)i;
    const float xm1 = dsp_delayline_f32_tap(dl, i - 1);
    const float x0 = dsp_delayline_f32_tap(dl, i);
    const float x1 = dsp_delayline_f32_tap(dl, i + 1);
    const float x2 = dsp_delayline_f32_tap(dl, i + 2);
    /* Nodes at -1, 0, 1, 2; evaluated at f in [0, 1). */
    const float fm1 = f - 1.0f, fm2 = f - 2.0f, fp1 = f + 1.0f;
    const float lm1 = -f * fm1 * fm2 * (1.0f / 6.0f);
    const float l0 = fp1 * fm1 * fm2 * 0.5f;
    const float l1 = -fp1 * f * fm2 * 0.5f;
    const float l2 = fp1 * f * fm1 * (1.0f / 6.0f);
    return lm1 * xm1 + l0 * x0 + l1 * x1 + l2 * x2;
}

float dsp_delayline_f32_read_allpass(const DspDelaylineF32 *dl, DspDelaylineApF32 *ap, float d) {
    d = clampf(d, 0.5f, (float)(dl->len - 3));
    int32_t i = (int32_t)d;
    float f = d - (float)i;
    /* Keep the fractional part in [0.5, 1.5): eta stays in (-0.2, 0.33], away from the pole
     * at -1 that a fraction near 0 would give. */
    if (f < 0.5f && i > 0) {
        i -= 1;
        f += 1.0f;
    }
    const float eta = (1.0f - f) / (1.0f + f);
    const float s0 = dsp_delayline_f32_tap(dl, i);
    const float s1 = dsp_delayline_f32_tap(dl, i + 1);
    const float y = eta * (s0 - ap->y1) + s1;
    ap->y1 = y;
    return y;
}

void dsp_delayline_f32_process(DspDelaylineF32 *dl, DspDelaylineApF32 *ap, int32_t interp,
                               const float *in, const float *delay, float *out, size_t n_frames) {
    for (size_t i = 0; i < n_frames; ++i) {
        dsp_delayline_f32_push(dl, in[i]);
        switch (interp) {
        case kDspInterpLinear:
            out[i] = dsp_delayline_f32_read_linear(dl, delay[i]);
            break;
        case kDspInterpLagrange:
            out[i] = dsp_delayline_f32_read_lagrange(dl, delay[i]);
            break;
        default:
            out[i] = dsp_delayline_f32_read_allpass(dl, ap, delay[i]);
            break;
        }
    }
}

/* ---- 16-bit storage ----------------------------------------------------------------------- */

static int16_t to_s16(float x) {
    float v = x * DSP_DELAYLINE_S16_SCALE;
    if (!(v >= -32768.0f)) {
        v = v != v ? 0.0f : -32768.0f; /* NaN stores 0. */
    } else if (v > 32767.0f) {
        v = 32767.0f;
    }
    /* Nearest (halves away from zero) at and above the snap level, toward zero below it: see the
     * header for why. */
    const float limit = DSP_DELAYLINE_S16_SNAP_LSB;
    if (v >= limit || v <= -limit) {
        return (int16_t)(int32_t)(v + (v >= 0.0f ? 0.5f : -0.5f));
    }
    return (int16_t)(int32_t)v;
}

float dsp_delayline_s16_quantise(float x) { return (float)to_s16(x) / DSP_DELAYLINE_S16_SCALE; }

int32_t dsp_delayline_s16_init(DspDelaylineS16 *dl, float *mem, int32_t len) {
    if (mem == NULL || len < 4) {
        dl->buf = NULL;
        dl->len = 0;
        dl->write = 0;
        return -1;
    }
    dl->buf = (unsigned char *)mem;
    dl->len = len;
    dsp_delayline_s16_reset(dl);
    return 0;
}

void dsp_delayline_s16_reset(DspDelaylineS16 *dl) {
    memset(dl->buf, 0, (size_t)dl->len * sizeof(int16_t));
    dl->write = 0;
}

void dsp_delayline_s16_push(DspDelaylineS16 *dl, float x) {
    const int16_t q = to_s16(x);
    memcpy(dl->buf + (size_t)dl->write * sizeof(int16_t), &q, sizeof(q));
    dl->write = dl->write + 1 == dl->len ? 0 : dl->write + 1;
}

float dsp_delayline_s16_tap(const DspDelaylineS16 *dl, int32_t d) {
    int32_t i = dl->write - 1 - d;
    if (i < 0) {
        i += dl->len;
    }
    int16_t q;
    memcpy(&q, dl->buf + (size_t)i * sizeof(int16_t), sizeof(q));
    return (float)q * (1.0f / DSP_DELAYLINE_S16_SCALE);
}

float dsp_delayline_s16_read_lagrange(const DspDelaylineS16 *dl, float d) {
    d = clampf(d, 1.0f, (float)(dl->len - 3));
    const int32_t i = (int32_t)d;
    const float f = d - (float)i;
    const float xm1 = dsp_delayline_s16_tap(dl, i - 1);
    const float x0 = dsp_delayline_s16_tap(dl, i);
    const float x1 = dsp_delayline_s16_tap(dl, i + 1);
    const float x2 = dsp_delayline_s16_tap(dl, i + 2);
    const float fm1 = f - 1.0f, fm2 = f - 2.0f, fp1 = f + 1.0f;
    const float lm1 = -f * fm1 * fm2 * (1.0f / 6.0f);
    const float l0 = fp1 * fm1 * fm2 * 0.5f;
    const float l1 = -fp1 * f * fm2 * 0.5f;
    const float l2 = fp1 * f * fm1 * (1.0f / 6.0f);
    return lm1 * xm1 + l0 * x0 + l1 * x1 + l2 * x2;
}
