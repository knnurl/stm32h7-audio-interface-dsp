#include "dsp/dsp_saturate.h"

#include <math.h>
#include <string.h>

#define kLn2 0.69314718055994531

/* log cosh(z), without overflow: |z| + log1p(exp(-2|z|)) - ln 2. */
static double log_cosh(double z) {
    const double a = fabs(z);
    return a + log1p(exp(-2.0 * a)) - kLn2;
}

static double antiderivative(const DspSaturatorF32 *sat, double x) {
    const double d = sat->drive;
    return log_cosh(d * x) * (double)sat->norm / d;
}

void dsp_saturator_f32_set_drive(DspSaturatorF32 *sat, float drive_db) {
    sat->drive = powf(10.0f, drive_db / 20.0f);
    sat->norm = 1.0f / tanhf(sat->drive);
    /* ADAA divides a difference of antiderivatives: both must be of the same curve, or the next
     * output is (F_new(x) - F_old(x_prev)) / dx, which can be huge for a small dx. */
    sat->adaa_f = antiderivative(sat, sat->adaa_x);
}

void dsp_saturator_f32_init(DspSaturatorF32 *sat, int32_t mode, float drive_db) {
    memset(sat, 0, sizeof(*sat));
    sat->mode = mode;
    dsp_saturator_f32_set_drive(sat, drive_db);
    dsp_oversample_f32_init(&sat->os, mode == kDspSatOs4 ? 4 : 2);
    dsp_saturator_f32_reset(sat);
}

void dsp_saturator_f32_reset(DspSaturatorF32 *sat) {
    dsp_oversample_f32_reset(&sat->os);
    sat->adaa_x = 0.0;
    sat->adaa_f = antiderivative(sat, 0.0);
}

float dsp_saturator_f32_shape(const DspSaturatorF32 *sat, float x) {
    return tanhf(sat->drive * x) * sat->norm;
}

static void shape_block(const DspSaturatorF32 *sat, float *buf, size_t n) {
    const float d = sat->drive, norm = sat->norm;
    for (size_t i = 0; i < n; ++i) {
        buf[i] = tanhf(d * buf[i]) * norm;
    }
}

static void process_adaa(DspSaturatorF32 *sat, const float *in, float *out, size_t n) {
    double xp = sat->adaa_x, fp = sat->adaa_f;
    for (size_t i = 0; i < n; ++i) {
        const double x = in[i];
        const double fx = antiderivative(sat, x);
        const double dx = x - xp;
        double y;
        if (fabs(dx) > 1e-6) {
            y = (fx - fp) / dx;
        } else {
            y = dsp_saturator_f32_shape(sat, (float)(0.5 * (x + xp)));
        }
        out[i] = (float)y;
        xp = x;
        fp = fx;
    }
    sat->adaa_x = xp;
    sat->adaa_f = fp;
}

void dsp_saturator_f32_process(DspSaturatorF32 *sat, const float *in, float *out,
                               size_t n_frames) {
    switch (sat->mode) {
    case kDspSatAdaa:
        process_adaa(sat, in, out, n_frames);
        return;
    case kDspSatOs2:
    case kDspSatOs4: {
        const size_t factor = (size_t)sat->os.factor;
        for (size_t start = 0; start < n_frames; start += kDspOversampleMaxBlock) {
            size_t n = n_frames - start;
            if (n > kDspOversampleMaxBlock) {
                n = kDspOversampleMaxBlock;
            }
            dsp_oversample_f32_up(&sat->os, in + start, sat->buf, n);
            shape_block(sat, sat->buf, n * factor);
            dsp_oversample_f32_down(&sat->os, sat->buf, out + start, n);
        }
        return;
    }
    default:
        if (in != out) {
            memmove(out, in, n_frames * sizeof(float));
        }
        shape_block(sat, out, n_frames);
        return;
    }
}

float dsp_saturator_f32_latency(const DspSaturatorF32 *sat) {
    switch (sat->mode) {
    case kDspSatAdaa:
        return 0.5f;
    case kDspSatOs2:
    case kDspSatOs4:
        return dsp_oversample_f32_latency(&sat->os);
    default:
        return 0.0f;
    }
}
