#include "dsp/dsp_fft.h"

#include <stddef.h>

int32_t dsp_rfft_f32_init(DspRfftF32 *fft, int32_t n) {
    if (n < 16 || n > kDspFftMaxN || (n & (n - 1)) != 0) {
        return -1;
    }
    fft->n = n;
    fft->log2_m = 0;
    while ((1 << fft->log2_m) < n / 2) {
        ++fft->log2_m;
    }
    return 0;
}

static void copy(const float *in, float *out, int32_t n) {
    if (in != out) {
        for (int32_t i = 0; i < n; ++i) {
            out[i] = in[i];
        }
    }
}

static void bit_reverse(float *d, int32_t m) {
    int32_t j = 0;
    for (int32_t i = 0; i < m - 1; ++i) {
        if (i < j) {
            const float re = d[2 * i];
            const float im = d[2 * i + 1];
            d[2 * i] = d[2 * j];
            d[2 * i + 1] = d[2 * j + 1];
            d[2 * j] = re;
            d[2 * j + 1] = im;
        }
        int32_t bit = m >> 1;
        while ((j & bit) != 0) {
            j ^= bit;
            bit >>= 1;
        }
        j |= bit;
    }
}

/* In-place radix-2 decimation-in-time FFT of m complex points (interleaved re, im). Unscaled.
 * inverse = 1 uses e^(+i...) twiddles. */
static void complex_fft(float *d, int32_t m, int inverse) {
    bit_reverse(d, m);
    for (int32_t i = 0; i < 2 * m; i += 4) { /* Length 2: the twiddle is 1. */
        const float ar = d[i], ai = d[i + 1], br = d[i + 2], bi = d[i + 3];
        d[i] = ar + br;
        d[i + 1] = ai + bi;
        d[i + 2] = ar - br;
        d[i + 3] = ai - bi;
    }
    for (int32_t len = 4; len <= m; len <<= 1) {
        const int32_t half = len / 2;
        const int32_t stride = kDspFftMaxN / len;
        for (int32_t j = 0; j < half; ++j) {
            const float wr = kDspFftCos[j * stride];
            const float wi = inverse ? kDspFftSin[j * stride] : -kDspFftSin[j * stride];
            for (int32_t b = j; b < m; b += len) {
                float *p = d + 2 * b;
                float *q = d + 2 * (b + half);
                const float tr = wr * q[0] - wi * q[1];
                const float ti = wr * q[1] + wi * q[0];
                q[0] = p[0] - tr;
                q[1] = p[1] - ti;
                p[0] = p[0] + tr;
                p[1] = p[1] + ti;
            }
        }
    }
}

void dsp_rfft_f32_forward(const DspRfftF32 *fft, const float *in, float *out) {
    const int32_t n = fft->n;
    const int32_t m = n / 2;
    const int32_t stride = kDspFftMaxN / n;
    copy(in, out, n);
    complex_fft(out, m, 0);
    const float z0r = out[0], z0i = out[1];
    out[0] = z0r + z0i; /* X[0] */
    out[1] = z0r - z0i; /* X[n/2] */
    for (int32_t k = 1; k <= m / 2; ++k) {
        const int32_t r = m - k;
        const float ar = out[2 * k], ai = out[2 * k + 1];
        const float br = out[2 * r], bi = out[2 * r + 1];
        /* Even part Fe = (A + conj B) / 2; odd part Fo = -i (A - conj B) / 2. */
        const float fer = 0.5f * (ar + br);
        const float fei = 0.5f * (ai - bi);
        const float for_ = 0.5f * (ai + bi);
        const float foi = 0.5f * (br - ar);
        /* t = W^k Fo, W = e^(-2 pi i / n). X[k] = Fe + t; X[m - k] = conj(Fe - t). */
        const float wr = kDspFftCos[k * stride];
        const float wi = -kDspFftSin[k * stride];
        const float tr = wr * for_ - wi * foi;
        const float ti = wr * foi + wi * for_;
        out[2 * k] = fer + tr;
        out[2 * k + 1] = fei + ti;
        if (r != k) {
            out[2 * r] = fer - tr;
            out[2 * r + 1] = ti - fei;
        }
    }
}

void dsp_rfft_f32_inverse(const DspRfftF32 *fft, const float *in, float *out) {
    const int32_t n = fft->n;
    const int32_t m = n / 2;
    const int32_t stride = kDspFftMaxN / n;
    copy(in, out, n);
    const float x0 = out[0], xm = out[1];
    out[0] = x0 + xm; /* Z[0] = (X[0] + X[n/2]) + i (X[0] - X[n/2]), times 2. */
    out[1] = x0 - xm;
    for (int32_t k = 1; k <= m / 2; ++k) {
        const int32_t r = m - k;
        const float ar = out[2 * k], ai = out[2 * k + 1];
        const float br = out[2 * r], bi = out[2 * r + 1];
        /* Twice the even part, X[k] + conj X[m-k]; twice the odd part, D conj(W^k), with
         * D = X[k] - conj X[m-k]. Z[k] = Fe + i Fo; Z[m-k] = conj(Fe) + i conj(Fo). */
        const float fer = ar + br;
        const float fei = ai - bi;
        const float dr = ar - br;
        const float di = ai + bi;
        const float wr = kDspFftCos[k * stride];
        const float wi = kDspFftSin[k * stride];
        const float for_ = dr * wr - di * wi;
        const float foi = dr * wi + di * wr;
        out[2 * k] = fer - foi;
        out[2 * k + 1] = fei + for_;
        if (r != k) {
            out[2 * r] = fer + foi;
            out[2 * r + 1] = for_ - fei;
        }
    }
    complex_fft(out, m, 1);
}
