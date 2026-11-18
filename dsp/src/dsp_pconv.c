#include "dsp/dsp_pconv.h"

static int valid_block(int32_t block) {
    return block >= 8 && block <= kDspFftMaxN / 2 && (block & (block - 1)) == 0;
}

int32_t dsp_pconv_f32_mem_needed(int32_t block, int32_t taps) {
    if (!valid_block(block) || taps < 1) {
        return 0;
    }
    const int32_t parts = (taps + block - 1) / block;
    const int32_t n = 2 * block;
    return 2 * parts * n + 2 * n + block;
}

static void clear(float *p, int32_t n) {
    for (int32_t i = 0; i < n; ++i) {
        p[i] = 0.0f;
    }
}

int32_t dsp_pconv_f32_init(DspPconvF32 *conv, int32_t block, int32_t taps, float *mem,
                           int32_t mem_len) {
    const int32_t need = dsp_pconv_f32_mem_needed(block, taps);
    if (need == 0 || mem == NULL || mem_len < need) {
        return -1;
    }
    const int32_t n = 2 * block;
    (void)dsp_rfft_f32_init(&conv->fft, n);
    conv->block = block;
    conv->parts = (taps + block - 1) / block;
    conv->h = mem;
    conv->fdl = conv->h + conv->parts * n;
    conv->in = conv->fdl + conv->parts * n;
    conv->work = conv->in + n;
    conv->out = conv->work + n;
    clear(conv->h, conv->parts * n);
    dsp_pconv_f32_reset(conv);
    return 0;
}

int32_t dsp_pconv_f32_set_filter(DspPconvF32 *conv, const float *h, int32_t taps) {
    const int32_t b = conv->block;
    const int32_t n = 2 * b;
    if (taps < 0 || taps > conv->parts * b) {
        return -1;
    }
    const float scale = 1.0f / (float)n; /* The inverse FFT returns n times the signal. */
    for (int32_t k = 0; k < conv->parts; ++k) {
        float *spec = conv->h + k * n;
        for (int32_t i = 0; i < n; ++i) {
            const int32_t tap = k * b + i;
            spec[i] = (i < b && tap < taps) ? h[tap] : 0.0f;
        }
        dsp_rfft_f32_forward(&conv->fft, spec, spec);
        for (int32_t i = 0; i < n; ++i) {
            spec[i] *= scale;
        }
    }
    return 0;
}

void dsp_pconv_f32_reset(DspPconvF32 *conv) {
    const int32_t n = 2 * conv->block;
    clear(conv->fdl, conv->parts * n);
    clear(conv->in, n);
    clear(conv->work, n);
    clear(conv->out, conv->block);
    conv->head = 0;
    conv->fill = 0;
}

/* One partition step: B new samples sit in in[B .. 2B). */
static void step(DspPconvF32 *conv) {
    const int32_t b = conv->block;
    const int32_t n = 2 * b;
    const int32_t parts = conv->parts;
    conv->head = conv->head + 1 == parts ? 0 : conv->head + 1;
    dsp_rfft_f32_forward(&conv->fft, conv->in, conv->fdl + conv->head * n);

    float *acc = conv->work;
    clear(acc, n);
    int32_t slot = conv->head;
    for (int32_t k = 0; k < parts; ++k) {
        const float *x = conv->fdl + slot * n;
        const float *hk = conv->h + k * n;
        acc[0] += x[0] * hk[0]; /* DC and Nyquist are real. */
        acc[1] += x[1] * hk[1];
        for (int32_t i = 2; i < n; i += 2) {
            const float xr = x[i], xi = x[i + 1];
            const float hr = hk[i], hi = hk[i + 1];
            acc[i] += xr * hr - xi * hi;
            acc[i + 1] += xr * hi + xi * hr;
        }
        slot = slot == 0 ? parts - 1 : slot - 1;
    }
    dsp_rfft_f32_inverse(&conv->fft, acc, acc);
    for (int32_t i = 0; i < b; ++i) {
        conv->out[i] = acc[b + i];
        conv->in[i] = conv->in[b + i];
    }
}

void dsp_pconv_f32_process(DspPconvF32 *conv, const float *in, float *out, size_t n) {
    const int32_t b = conv->block;
    size_t done = 0;
    while (done < n) {
        size_t take = (size_t)(b - conv->fill);
        if (take > n - done) {
            take = n - done;
        }
        float *gather = conv->in + b + conv->fill;
        const float *ready = conv->out + conv->fill;
        for (size_t i = 0; i < take; ++i) {
            gather[i] = in[done + i];
            out[done + i] = ready[i];
        }
        done += take;
        conv->fill += (int32_t)take;
        if (conv->fill == b) {
            conv->fill = 0;
            step(conv);
        }
    }
}
