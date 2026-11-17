#include "dsp/dsp_oversample.h"

#include <string.h>

/* From tools/design/b6_coefficients.py. */
static const float kHalfband1[83] = {
    6.021812855e-06f, 0.000000000e+00f, -2.001940640e-05f, 0.000000000e+00f,
    5.148910757e-05f, 0.000000000e+00f, -1.129440235e-04f, 0.000000000e+00f,
    2.227123343e-04f, 0.000000000e+00f, -4.059865797e-04f, 0.000000000e+00f,
    6.959492774e-04f, 0.000000000e+00f, -1.134923901e-03f, 0.000000000e+00f,
    1.775518910e-03f, 0.000000000e+00f, -2.682202257e-03f, 0.000000000e+00f,
    3.933778302e-03f, 0.000000000e+00f, -5.628103932e-03f, 0.000000000e+00f,
    7.891208697e-03f, 0.000000000e+00f, -1.089568029e-02f, 0.000000000e+00f,
    1.489836354e-02f, 0.000000000e+00f, -2.032238123e-02f, 0.000000000e+00f,
    2.795170574e-02f, 0.000000000e+00f, -3.946268815e-02f, 0.000000000e+00f,
    5.923341267e-02f, 0.000000000e+00f, -1.033901662e-01f, 0.000000000e+00f,
    3.173959958e-01f, 5.000000000e-01f, 3.173959958e-01f, 0.000000000e+00f,
    -1.033901662e-01f, 0.000000000e+00f, 5.923341267e-02f, 0.000000000e+00f,
    -3.946268815e-02f, 0.000000000e+00f, 2.795170574e-02f, 0.000000000e+00f,
    -2.032238123e-02f, 0.000000000e+00f, 1.489836354e-02f, 0.000000000e+00f,
    -1.089568029e-02f, 0.000000000e+00f, 7.891208697e-03f, 0.000000000e+00f,
    -5.628103932e-03f, 0.000000000e+00f, 3.933778302e-03f, 0.000000000e+00f,
    -2.682202257e-03f, 0.000000000e+00f, 1.775518910e-03f, 0.000000000e+00f,
    -1.134923901e-03f, 0.000000000e+00f, 6.959492774e-04f, 0.000000000e+00f,
    -4.059865797e-04f, 0.000000000e+00f, 2.227123343e-04f, 0.000000000e+00f,
    -1.129440235e-04f, 0.000000000e+00f, 5.148910757e-05f, 0.000000000e+00f,
    -2.001940640e-05f, 0.000000000e+00f, 6.021812855e-06f,
};
static const float kHalfband2[23] = {
    -1.999703852e-04f, 0.000000000e+00f, 1.775496952e-03f, 0.000000000e+00f,
    -8.299824663e-03f, 0.000000000e+00f, 2.763235143e-02f, 0.000000000e+00f,
    -7.911580159e-02f, 0.000000000e+00f, 3.082074892e-01f, 5.000000000e-01f,
    3.082074892e-01f, 0.000000000e+00f, -7.911580159e-02f, 0.000000000e+00f,
    2.763235143e-02f, 0.000000000e+00f, -8.299824663e-03f, 0.000000000e+00f,
    1.775496952e-03f, 0.000000000e+00f, -1.999703852e-04f,
};

const float *dsp_halfband_stage1(int32_t *length) {
    *length = 83;
    return kHalfband1;
}

const float *dsp_halfband_stage2(int32_t *length) {
    *length = 23;
    return kHalfband2;
}

static int32_t even_taps(const float *h, int32_t length, float *taps) {
    if (length < 3 || (length - 3) % 4 != 0) {
        return -1;
    }
    const int32_t n = (length + 1) / 2;
    if (n > kDspHalfbandMaxTaps) {
        return -1;
    }
    for (int32_t j = 0; j < n; ++j) {
        taps[j] = h[2 * j];
    }
    return n;
}

static int32_t is_symmetric(const float *taps, int32_t n) {
    for (int32_t j = 0; j < n / 2; ++j) {
        if (taps[j] != taps[n - 1 - j]) {
            return 0;
        }
    }
    return 1;
}

/* sum taps[j] x[j], j < n. The folded form pairs x[j] with x[n - 1 - j] and keeps four partial
 * sums; the summation order is fixed, so the PC and the target still agree bit for bit. */
static float fir(const float *taps, const float *x, int32_t n, int32_t symmetric) {
    float a0 = 0.0f, a1 = 0.0f, a2 = 0.0f, a3 = 0.0f;
    int32_t j = 0;
    if (symmetric) {
        const int32_t half = n / 2;
        const float *xr = x + n - 1;
        for (; j + 3 < half; j += 4) {
            a0 += taps[j] * (x[j] + xr[-j]);
            a1 += taps[j + 1] * (x[j + 1] + xr[-j - 1]);
            a2 += taps[j + 2] * (x[j + 2] + xr[-j - 2]);
            a3 += taps[j + 3] * (x[j + 3] + xr[-j - 3]);
        }
        for (; j < half; ++j) {
            a0 += taps[j] * (x[j] + xr[-j]);
        }
        if ((n & 1) != 0) {
            a1 += taps[half] * x[half];
        }
    } else {
        for (; j + 3 < n; j += 4) {
            a0 += taps[j] * x[j];
            a1 += taps[j + 1] * x[j + 1];
            a2 += taps[j + 2] * x[j + 2];
            a3 += taps[j + 3] * x[j + 3];
        }
        for (; j < n; ++j) {
            a0 += taps[j] * x[j];
        }
    }
    return (a0 + a1) + (a2 + a3);
}

/* Writes one sample at the head of a double-written ring: hist[pos .. pos + n - 1] is then the
 * newest n samples, newest first. */
static int32_t push(float *hist, int32_t n, int32_t pos, float x) {
    pos = pos == 0 ? n - 1 : pos - 1;
    hist[pos] = x;
    hist[pos + n] = x;
    return pos;
}

int32_t dsp_halfband_up_init(DspHalfbandUpF32 *up, const float *h, int32_t length) {
    memset(up, 0, sizeof(*up));
    const int32_t n = even_taps(h, length, up->taps);
    if (n < 0) {
        return -1;
    }
    up->n_taps = n;
    up->delay = (length - 1) / 4; /* (centre - 1) / 2 */
    up->symmetric = is_symmetric(up->taps, n);
    return 0;
}

void dsp_halfband_up_reset(DspHalfbandUpF32 *up) {
    memset(up->hist, 0, sizeof(up->hist));
    up->pos = 0;
}

void dsp_halfband_up_process(DspHalfbandUpF32 *up, const float *in, float *out, size_t n_in) {
    const int32_t n = up->n_taps;
    for (size_t i = 0; i < n_in; ++i) {
        up->pos = push(up->hist, n, up->pos, in[i]);
        const float *x = &up->hist[up->pos];
        const float acc = fir(up->taps, x, n, up->symmetric);
        out[2 * i] = 2.0f * acc;      /* The even taps, times the interpolation gain of 2. */
        out[2 * i + 1] = x[up->delay]; /* The centre tap: 2 x 0.5 x the delayed input. */
    }
}

int32_t dsp_halfband_down_init(DspHalfbandDownF32 *down, const float *h, int32_t length) {
    memset(down, 0, sizeof(*down));
    const int32_t n = even_taps(h, length, down->taps);
    if (n < 0) {
        return -1;
    }
    down->n_taps = n;
    down->delay = (length + 1) / 4; /* (centre + 1) / 2 */
    down->symmetric = is_symmetric(down->taps, n);
    return 0;
}

void dsp_halfband_down_reset(DspHalfbandDownF32 *down) {
    memset(down->even, 0, sizeof(down->even));
    memset(down->odd, 0, sizeof(down->odd));
    down->even_pos = 0;
    down->odd_pos = 0;
}

void dsp_halfband_down_process(DspHalfbandDownF32 *down, const float *in, float *out,
                               size_t n_out) {
    const int32_t n = down->n_taps;
    for (size_t i = 0; i < n_out; ++i) {
        /* Output k is the full-rate filter at m = 2k: the even taps meet the even samples
         * v[2k - 2j], and the centre tap (index c, odd) meets v[2k - c], which is the odd sample
         * of pair k - (c + 1) / 2. */
        down->odd_pos = push(down->odd, n, down->odd_pos, in[2 * i + 1]);
        down->even_pos = push(down->even, n, down->even_pos, in[2 * i]);
        const float *e = &down->even[down->even_pos];
        const float acc = fir(down->taps, e, n, down->symmetric);
        out[i] = acc + 0.5f * down->odd[down->odd_pos + down->delay];
    }
}

void dsp_oversample_f32_init(DspOversampleF32 *os, int32_t factor) {
    memset(os, 0, sizeof(*os));
    os->factor = factor == 4 ? 4 : 2;
    dsp_halfband_up_init(&os->up1, kHalfband1, 83);
    dsp_halfband_down_init(&os->down1, kHalfband1, 83);
    dsp_halfband_up_init(&os->up2, kHalfband2, 23);
    dsp_halfband_down_init(&os->down2, kHalfband2, 23);
}

void dsp_oversample_f32_reset(DspOversampleF32 *os) {
    dsp_halfband_up_reset(&os->up1);
    dsp_halfband_up_reset(&os->up2);
    dsp_halfband_down_reset(&os->down1);
    dsp_halfband_down_reset(&os->down2);
}

void dsp_oversample_f32_up(DspOversampleF32 *os, const float *in, float *out, size_t n) {
    if (os->factor == 2) {
        dsp_halfband_up_process(&os->up1, in, out, n);
        return;
    }
    /* The scratch holds 2 x kDspOversampleMaxBlock: work through longer blocks in pieces. */
    for (size_t start = 0; start < n; start += kDspOversampleMaxBlock) {
        const size_t m = n - start < kDspOversampleMaxBlock ? n - start : kDspOversampleMaxBlock;
        dsp_halfband_up_process(&os->up1, in + start, os->scratch, m);
        dsp_halfband_up_process(&os->up2, os->scratch, out + 4 * start, 2 * m);
    }
}

void dsp_oversample_f32_down(DspOversampleF32 *os, const float *in, float *out, size_t n) {
    if (os->factor == 2) {
        dsp_halfband_down_process(&os->down1, in, out, n);
        return;
    }
    for (size_t start = 0; start < n; start += kDspOversampleMaxBlock) {
        const size_t m = n - start < kDspOversampleMaxBlock ? n - start : kDspOversampleMaxBlock;
        dsp_halfband_down_process(&os->down2, in + 4 * start, os->scratch, 2 * m);
        dsp_halfband_down_process(&os->down1, os->scratch, out + start, m);
    }
}

float dsp_oversample_f32_latency(const DspOversampleF32 *os) {
    /* Each stage: (N - 1) / 2 samples at its high rate, twice (up and down). */
    const float stage1 = (83.0f - 1.0f) / 2.0f / 2.0f * 2.0f; /* 41 base-rate samples */
    const float stage2 = (23.0f - 1.0f) / 2.0f / 4.0f * 2.0f; /* 5.5 base-rate samples */
    return os->factor == 2 ? stage1 : stage1 + stage2;
}
