#include "dsp/dsp_pconv.h"

#include "arm_math.h"

/* A cache preload hint for the multiply-add loop, whose spectra (64 KB per channel at 4096 taps)
 * stream from AXI SRAM through a 16 KB data cache. It changes no result. */
#if defined(__GNUC__)
#define PRELOAD(p) __builtin_prefetch(p)
#else
#define PRELOAD(p) ((void)(p))
#endif

_Static_assert(sizeof(arm_rfft_fast_instance_f32) <= sizeof(((DspPconvF32 *)0)->fft_state),
               "fft_state is too small for CMSIS's instance");

static arm_rfft_fast_instance_f32 *fft_of(DspPconvF32 *conv) {
    return (arm_rfft_fast_instance_f32 *)(void *)conv->fft_state;
}

/* The size-specific initialisers, so the linker keeps only the tables of the sizes in use. */
static int init_fft(arm_rfft_fast_instance_f32 *s, int32_t n) {
    switch (n) {
    case 32:
        return arm_rfft_fast_init_32_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    case 64:
        return arm_rfft_fast_init_64_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    case 128:
        return arm_rfft_fast_init_128_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    case 256:
        return arm_rfft_fast_init_256_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    case 512:
        return arm_rfft_fast_init_512_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    case 1024:
        return arm_rfft_fast_init_1024_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    case 2048:
        return arm_rfft_fast_init_2048_f32(s) == ARM_MATH_SUCCESS ? 0 : -1;
    default:
        return -1;
    }
}

static int valid_block(int32_t block) {
    return block >= 16 && block <= kDspFftMaxN / 2 && (block & (block - 1)) == 0;
}

int32_t dsp_pconv_f32_mem_needed(int32_t block, int32_t taps) {
    if (!valid_block(block) || taps < 1) {
        return 0;
    }
    const int32_t parts = (taps + block - 1) / block;
    const int32_t n = 2 * block;
    return 2 * parts * n + 3 * n + block;
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
    if (init_fft(fft_of(conv), n) != 0) {
        return -1;
    }
    conv->block = block;
    conv->parts = (taps + block - 1) / block;
    conv->h = mem;
    conv->fdl = conv->h + conv->parts * n;
    conv->in = conv->fdl + conv->parts * n;
    conv->work = conv->in + n;
    conv->tmp = conv->work + n;
    conv->out = conv->tmp + n;
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
    for (int32_t k = 0; k < conv->parts; ++k) {
        for (int32_t i = 0; i < n; ++i) {
            const int32_t tap = k * b + i;
            conv->tmp[i] = (i < b && tap < taps) ? h[tap] : 0.0f;
        }
        arm_rfft_fast_f32(fft_of(conv), conv->tmp, conv->h + k * n, 0u);
    }
    return 0;
}

void dsp_pconv_f32_reset(DspPconvF32 *conv) {
    const int32_t n = 2 * conv->block;
    clear(conv->fdl, conv->parts * n);
    clear(conv->in, n);
    clear(conv->work, n);
    clear(conv->tmp, n);
    clear(conv->out, conv->block);
    conv->head = 0;
    conv->fill = 0;
}

static void cmac(float *restrict acc, const float *restrict x, const float *restrict h) {
    acc[0] += x[0] * h[0] - x[1] * h[1];
    acc[1] += x[0] * h[1] + x[1] * h[0];
}

/* acc += x h over two packed spectra of n floats. The three never overlap; saying so (restrict)
 * lets the compiler overlap one bin's loads with the previous bin's arithmetic instead of waiting
 * for each store. Two bins per pass; the order of operations per bin is unchanged, so the result
 * is too. */
static void mac(float *restrict acc, const float *restrict x, const float *restrict h,
                int32_t n) {
    acc[0] += x[0] * h[0]; /* DC and Nyquist are real. */
    acc[1] += x[1] * h[1];
    cmac(acc + 2, x + 2, h + 2); /* Bin 1; then pairs of bins 2 to n/2 - 1. */
    for (int32_t i = 4; i < n; i += 4) {
        PRELOAD(x + i + 64);
        PRELOAD(h + i + 64);
        const float xr0 = x[i], xi0 = x[i + 1], xr1 = x[i + 2], xi1 = x[i + 3];
        const float hr0 = h[i], hi0 = h[i + 1], hr1 = h[i + 2], hi1 = h[i + 3];
        acc[i] += xr0 * hr0 - xi0 * hi0;
        acc[i + 1] += xr0 * hi0 + xi0 * hr0;
        acc[i + 2] += xr1 * hr1 - xi1 * hi1;
        acc[i + 3] += xr1 * hi1 + xi1 * hr1;
    }
}

/* One partition step: B new samples sit in in[B .. 2B). */
static void step(DspPconvF32 *conv) {
    const int32_t b = conv->block;
    const int32_t n = 2 * b;
    const int32_t parts = conv->parts;
    conv->head = conv->head + 1 == parts ? 0 : conv->head + 1;
    for (int32_t i = 0; i < n; ++i) {
        conv->tmp[i] = conv->in[i]; /* CMSIS overwrites its input. */
    }
    arm_rfft_fast_f32(fft_of(conv), conv->tmp, conv->fdl + conv->head * n, 0u);

    float *acc = conv->work;
    clear(acc, n);
    int32_t slot = conv->head;
    for (int32_t k = 0; k < parts; ++k) {
        mac(acc, conv->fdl + slot * n, conv->h + k * n, n);
        slot = slot == 0 ? parts - 1 : slot - 1;
    }
    arm_rfft_fast_f32(fft_of(conv), acc, conv->tmp, 1u); /* Scales by 1 / N. */
    for (int32_t i = 0; i < b; ++i) {
        conv->out[i] = conv->tmp[b + i];
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
