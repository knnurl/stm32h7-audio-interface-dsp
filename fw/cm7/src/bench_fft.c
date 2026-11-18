#include "bench_fft.h"

#include "board.h"
#include "console.h"
#include "dsp/dsp_fft.h"
#include "dsp/dsp_pconv.h"
#include "dsp/dsp_testsig.h"

#include <stdio.h>

enum {
    kTaps = 4096,
    kMaxConvMem = 18944, /* dsp_pconv_f32_mem_needed at B = 512, the largest of the sweep. */
    kCall = 16,
    kStepsPerRep = 8,
    kReps = 5,
};

static float s_buf[kDspFftMaxN] __attribute__((section(".axi_bss")));
static float s_spec[kDspFftMaxN] __attribute__((section(".axi_bss")));
static float s_conv_mem[2][kMaxConvMem] __attribute__((section(".axi_bss")));
static float s_filter[kTaps] __attribute__((section(".axi_bss")));
static float s_x[2][4096] __attribute__((section(".axi_bss")));
static float s_y[2][kCall];

static void noise(float *out, size_t n, uint32_t seed, float amplitude) {
    DspNoise gen;
    dsp_noise_seed(&gen, seed);
    dsp_noise_f32(&gen, out, n, amplitude);
}

void bench_fft(void) {
    for (int32_t n = 64; n <= kDspFftMaxN; n *= 2) {
        DspRfftF32 fft;
        (void)dsp_rfft_f32_init(&fft, n);
        uint32_t fwd = 0xFFFFFFFFu, inv = 0xFFFFFFFFu;
        for (int run = 0; run < 9; ++run) {
            noise(s_buf, (size_t)n, 5u, 0.5f);
            uint32_t start = board_cycles();
            dsp_rfft_f32_forward(&fft, s_buf, s_spec);
            uint32_t c = board_cycles() - start;
            fwd = c < fwd ? c : fwd;
            start = board_cycles();
            dsp_rfft_f32_inverse(&fft, s_spec, s_buf);
            c = board_cycles() - start;
            inv = c < inv ? c : inv;
        }
        printf("fftbench n=%ld fwd=%lu inv=%lu\r\n", (long)n, (unsigned long)fwd,
               (unsigned long)inv);
        console_flush();
    }
    printf("fftbench done\r\n");
}

/* The selftest's room-like filter: noise under a decay with a time constant of taps / 6. */
static void room_filter(uint32_t seed) {
    noise(s_filter, kTaps, seed, 0.2f);
    float g = 1.0f;
    for (size_t i = 0; i < kTaps; ++i) {
        s_filter[i] *= g;
        g *= 0.998536f;
    }
}

void bench_conv(void) {
    static DspPconvF32 conv[2];
    noise(s_x[0], 4096, 21u, 0.5f);
    noise(s_x[1], 4096, 22u, 0.5f);
    for (int32_t block = 64; block <= 512; block *= 2) {
        const int32_t frames = kStepsPerRep * block;
        uint32_t best_total = 0xFFFFFFFFu, best_step = 0xFFFFFFFFu;
        for (int rep = 0; rep < kReps; ++rep) {
            for (int ch = 0; ch < 2; ++ch) {
                (void)dsp_pconv_f32_init(&conv[ch], block, kTaps, s_conv_mem[ch], kMaxConvMem);
                room_filter(11u + (uint32_t)ch);
                (void)dsp_pconv_f32_set_filter(&conv[ch], s_filter, kTaps);
            }
            uint32_t total = 0, step = 0;
            for (int32_t i = 0; i < frames; i += kCall) {
                const uint32_t start = board_cycles();
                dsp_pconv_f32_process(&conv[0], s_x[0] + i, s_y[0], kCall);
                dsp_pconv_f32_process(&conv[1], s_x[1] + i, s_y[1], kCall);
                const uint32_t c = board_cycles() - start;
                total += c;
                step = c > step ? c : step;
            }
            best_total = total < best_total ? total : best_total;
            best_step = step < best_step ? step : best_step;
        }
        const uint32_t per_frame_x10 = (uint32_t)((10ull * best_total) / (uint32_t)frames);
        const uint32_t latency_us = (uint32_t)(1000000ull * (uint32_t)block / 48000u);
        printf("convbench block=%ld parts=%ld taps=%d ch=2 per_frame=%lu.%lu step_call=%lu "
               "latency_ms48=%lu.%02lu\r\n",
               (long)block, (long)conv[0].parts, (int)kTaps, (unsigned long)(per_frame_x10 / 10u),
               (unsigned long)(per_frame_x10 % 10u), (unsigned long)best_step,
               (unsigned long)(latency_us / 1000u), (unsigned long)((latency_us % 1000u) / 10u));
        console_flush();
    }
    printf("convbench done\r\n");
}
