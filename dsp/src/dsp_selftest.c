#include "dsp/dsp_selftest.h"

#include "dsp/dsp_biquad.h"
#include "dsp/dsp_comp.h"
#include "dsp/dsp_crossfeed.h"
#include "dsp/dsp_delayline.h"
#include "dsp/dsp_fastmath.h"
#include "dsp/dsp_fft.h"
#include "dsp/dsp_fxslot.h"
#include "dsp/dsp_gain.h"
#include "dsp/dsp_gate.h"
#include "dsp/dsp_oversample.h"
#include "dsp/dsp_pconv.h"
#include "dsp/dsp_limiter.h"
#include "dsp/dsp_meter.h"
#include "dsp/dsp_mixer.h"
#include "dsp/dsp_reverb.h"
#include "dsp/dsp_saturate.h"
#include "dsp/dsp_svf.h"
#include "dsp/dsp_testsig.h"
#include "dsp/dsp_tone.h"

#include <math.h>

typedef struct {
    const char *name;
    DspFmt fmt;
    int channels;
    void (*input)(void *in);
    void (*run)(const void *in, void *out);
} SelftestCase;

/* The bench's hook: processing starts now. The one mutable global here, set only by the bench
 * (the self-test is a test harness, not a DSP block). */
static DspSelftestMarkFn s_mark;

void dsp_selftest_set_mark(DspSelftestMarkFn fn) { s_mark = fn; }

static void mark(void) {
    if (s_mark != NULL) {
        s_mark();
    }
}

/* gain_f32: half-scale noise; from silence up to -6 dB, then on to 0.25, at 48 kHz with a 5 ms
 * time constant, so both ramps are still moving when their half of the buffer ends. */
static void gain_f32_input(void *in) {
    DspNoise noise;
    dsp_noise_seed(&noise, 1u);
    dsp_noise_f32(&noise, (float *)in, kDspSelftestFrames, 0.5f);
}

static void gain_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    DspGainF32 gain;
    dsp_gain_f32_init(&gain, 48000.0f, 5.0f);
    dsp_gain_f32_set_linear(&gain, 0.0f);
    dsp_gain_f32_reset(&gain);
    mark();
    dsp_gain_f32_set_db(&gain, -6.0f);
    dsp_gain_f32_process(&gain, x, y, half);
    dsp_gain_f32_set_linear(&gain, 0.25f);
    dsp_gain_f32_process(&gain, x + half, y + half, kDspSelftestFrames - half);
}

/* noise_q31: the generator itself, as the one fixed-point case until batch 3 adds real ones.
 * It proves the checksum route end to end. The input is ignored. */
static void noise_q31_input(void *in) {
    int32_t *x = (int32_t *)in;
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        x[i] = 0;
    }
}

static void noise_q31_run(const void *in, void *out) {
    (void)in;
    DspNoise noise;
    dsp_noise_seed(&noise, 2u);
    mark();
    dsp_noise_q31(&noise, (int32_t *)out, kDspSelftestFrames);
}

/* The biquad cases use fixed coefficients, so they test the filter code and not the C
 * library's sin, cos and pow (which may differ by an ulp between the PC and the target and would
 * break the fixed-point checksum). From tests/ref/coef.py at 48 kHz: a 30 Hz Butterworth
 * high-pass, a 1 kHz peak +6 dB Q 1, an 8 kHz high shelf -4 dB slope 1. */
static const DspBiquadCoefsF32 kCascadeF32[3] = {
    {0.997227073f, -1.99445415f, 0.997227073f, -1.9944464f, 0.994461775f},
    {1.04395306f, -1.89532077f, 0.867722273f, -1.89532077f, 0.911675394f},
    {0.739665747f, -0.367563397f, 0.159448624f, -0.737999022f, 0.269549966f},
};
static const DspBiquadCoefsQ31 kCascadeQ31[3] = {
    {535382196, -1070764392, 535382196, -1070760263, 533897608, 1},
    {560468046, -1017542566, 465854854, -1017542566, 489451988, 1},
    {794210024, -394668207, 171206661, -792420405, 289427058, 0},
};

static const DspBiquadCoefsF64 kCascadeF64[3] = {
    {0.9972270499044701, -1.9944540998089402, 0.9972270499044701, -1.9944464105419266,
     0.9944617890759537},
    {1.043953086990335, -1.8953207239365961, 0.8677222847598566, -1.8953207239365961,
     0.9116753717501915},
    {0.739665724472926, -0.36756341089391625, 0.15944862806897292, -0.7379990113316548,
     0.2695499529796374},
};

static void noise_half_f32_input(void *in) {
    DspNoise noise;
    dsp_noise_seed(&noise, 3u);
    dsp_noise_f32(&noise, (float *)in, kDspSelftestFrames, 0.5f);
}

/* Quarter-scale Q31 noise: headroom for the +6 dB peak. */
static void noise_quarter_q31_input(void *in) {
    int32_t *x = (int32_t *)in;
    DspNoise noise;
    dsp_noise_seed(&noise, 4u);
    dsp_noise_q31(&noise, x, kDspSelftestFrames);
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        x[i] /= 4;
    }
}

static void biquad_f32_run(const void *in, void *out) {
    DspBiquadF32 filter;
    dsp_biquad_f32_init(&filter, kCascadeF32, 3);
    mark();
    /* In blocks of 16, as the audio interrupt will call it. */
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_biquad_f32_process(&filter, (const float *)in + i, (float *)out + i, 16);
    }
}

/* The same cascade with double state: the kernel the PEQ and tone control use. */
static void biquad_f64_run(const void *in, void *out) {
    DspBiquadStateF64 state[3] = {{0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}};
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        const float *src = (const float *)in + i;
        float *dst = (float *)out + i;
        for (int s = 0; s < 3; ++s) {
            dsp_biquad_f64_section(&kCascadeF64[s], &state[s], src, dst, 16);
            src = dst;
        }
    }
}

static void biquad_q31_run(const void *in, void *out, int32_t error_feedback) {
    DspBiquadQ31 filter;
    dsp_biquad_q31_init(&filter, kCascadeQ31, 3, error_feedback);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_biquad_q31_process(&filter, (const int32_t *)in + i, (int32_t *)out + i, 16);
    }
}

static void biquad_q31_round_run(const void *in, void *out) { biquad_q31_run(in, out, 0); }
static void biquad_q31_ef_run(const void *in, void *out) { biquad_q31_run(in, out, 1); }

/* tone_f32: the first half of the buffer is the left channel, the second half the right.
 * Bass +6, mid -3, treble +9 from the start; after 256 frames bass moves to -12. */
static void tone_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    DspToneF32 tone;
    dsp_tone_f32_init(&tone, 48000.0f);
    dsp_tone_f32_set_db(&tone, kDspToneBass, 6.0f);
    dsp_tone_f32_set_db(&tone, kDspToneMid, -3.0f);
    dsp_tone_f32_set_db(&tone, kDspToneTreble, 9.0f);
    dsp_tone_f32_reset(&tone);
    mark();
    for (size_t i = 0; i < half; i += 16) {
        if (i == 256) {
            dsp_tone_f32_set_db(&tone, kDspToneBass, -12.0f);
        }
        dsp_tone_f32_process(&tone, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

/* Batch 6. Inputs: a 1 kHz-ish burst pattern made from the noise generator, so the dynamics
 * blocks see loud and quiet passages. Every case runs in blocks of 16 like the audio interrupt. */
static void bursts_f32_input(void *in) {
    float *x = (float *)in;
    DspNoise noise;
    dsp_noise_seed(&noise, 5u);
    dsp_noise_f32(&noise, x, kDspSelftestFrames, 1.0f);
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        x[i] *= (i / 128u) % 2u == 0u ? 0.9f : 0.01f;
    }
}

static void comp_f32_run(const void *in, void *out) {
    const DspCompParams params = {-20.0f, 4.0f, 6.0f, 1.0f, 10.0f, 3.0f, 80.0f};
    DspCompF32 comp;
    dsp_comp_f32_init(&comp, 48000.0f, &params);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_comp_f32_process(&comp, (const float *)in + i, (float *)out + i, 16);
    }
}

static void gate_f32_run(const void *in, void *out) {
    const DspGateParams params = {-30.0f, 6.0f, 1.0f, 0.2f, 2.0f, -60.0f, 1.0f};
    DspGateF32 gate;
    dsp_gate_f32_init(&gate, 48000.0f, &params);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_gate_f32_process(&gate, (const float *)in + i, (float *)out + i, 16);
    }
}

/* Left = first half, right = second half, as tone_f32. 4 ms of state lives in the struct, so it
 * is static here rather than on the stack (about 30 KB). */
static DspLimiterF32 s_limiter;

static void limiter_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    dsp_limiter_f32_init(&s_limiter, 48000.0f, -6.0f, 1.0f, 20.0f);
    mark();
    for (size_t i = 0; i < half; i += 16) {
        dsp_limiter_f32_process(&s_limiter, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

/* The headphones' limiter: the same, detecting sample peaks. */
static void limiter_sp_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    dsp_limiter_f32_init_mode(&s_limiter, 48000.0f, -6.0f, 1.0f, 20.0f, kDspLimiterSamplePeak);
    mark();
    for (size_t i = 0; i < half; i += 16) {
        dsp_limiter_f32_process(&s_limiter, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

static DspSaturatorF32 s_saturator;

static void saturate_run(const void *in, void *out, int32_t mode) {
    dsp_saturator_f32_init(&s_saturator, mode, 12.0f);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_saturator_f32_process(&s_saturator, (const float *)in + i, (float *)out + i, 16);
    }
}

static void sat_os4_f32_run(const void *in, void *out) { saturate_run(in, out, kDspSatOs4); }
static void sat_os2_f32_run(const void *in, void *out) { saturate_run(in, out, kDspSatOs2); }

/* Budget decomposition (2026-11-17): the two parts of the 4x saturator on their own. tanh of
 * 4 x the input, once with the C library (differs between the PC and the target in the last
 * bits) and once with dsp_fast_tanhf; and the 4x oversampler up and down with no shaping. */
static void tanh_libm_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        y[i] = tanhf(4.0f * x[i]);
    }
}

static void tanh_fast_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        y[i] = dsp_fast_tanhf(4.0f * x[i]);
    }
}

static DspOversampleF32 s_os;
static float s_os_buf[4 * 16];

static void os4_pass_f32_run(const void *in, void *out) {
    dsp_oversample_f32_init(&s_os, 4);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_oversample_f32_up(&s_os, (const float *)in + i, s_os_buf, 16);
        dsp_oversample_f32_down(&s_os, s_os_buf, (float *)out + i, 16);
    }
}
static void sat_adaa_f32_run(const void *in, void *out) { saturate_run(in, out, kDspSatAdaa); }

/* Batch 8b. The cases share one state union and one memory pool (they never run at the same
 * time): about 41 KB in all. Stereo cases: left = first half of the buffer, right = second
 * half. The input is the bursts pattern above, so delay and reverb tails show between the
 * bursts. The tremolo has no case until the owner writes it.
 * On the M7 the 30 KB pool sits where the real delay lines will (AXI SRAM, `.axi_bss`, SPEC 6.2),
 * so the cycle counts are the real ones and DTCM is not spent on a test; the section is not
 * zeroed at start, and every init clears the memory it is given. Elsewhere, ordinary .bss. */
#if defined(DSP_HAS_AXI_BSS) /* The M7 firmware; not the M4, whose RAM has no such section. */
#define SELFTEST_AXI __attribute__((section(".axi_bss")))
#else
#define SELFTEST_AXI
#endif
enum { kPool8b = 7680 };
static float s_pool8b[kPool8b] SELFTEST_AXI;
static union {
    DspDelaylineF32 delay;
    DspSvfF32 svf;
    DspFxEchoF32 echo;
    DspFxChorusF32 chorus;
    DspFxFlangerF32 flanger;
    DspFxPhaserF32 phaser;
    DspFxSweepF32 sweep;
    DspFxOverdriveF32 overdrive;
    DspFxCrusherF32 crusher;
    DspFxSlotF32 slot;
    DspReverbF32 reverb;
} s_8b;

/* A delay read swept from 10 to 600 samples and back, third-order Lagrange. */
static void delay_lagrange_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    dsp_delayline_f32_init(&s_8b.delay, s_pool8b, 1024);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        const float t = (float)i / (float)kDspSelftestFrames;
        const float d = 10.0f + 590.0f * (t < 0.5f ? 2.0f * t : 2.0f - 2.0f * t);
        dsp_delayline_f32_push(&s_8b.delay, x[i]);
        y[i] = dsp_delayline_f32_read_lagrange(&s_8b.delay, d);
    }
}

/* Low-pass, Q 4, cutoff stepped every 16 samples from 200 Hz up to 8 kHz (fast coefficients). */
static void svf_f32_run(const void *in, void *out) {
    dsp_svf_f32_init(&s_8b.svf, 48000.0f, 200.0f, 4.0f);
    mark();
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        const float fc = 200.0f + 7800.0f * (float)i / (float)kDspSelftestFrames;
        dsp_svf_f32_set_fast(&s_8b.svf, 48000.0f, fc, 4.0f);
        dsp_svf_f32_process(&s_8b.svf, kDspSvfLow, (const float *)in + i, (float *)out + i, 16);
    }
}

typedef void (*StereoFn)(void *state, const float *, const float *, float *, float *, size_t);

static void run_stereo16(StereoFn fn, void *state, const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    mark();
    for (size_t i = 0; i < half; i += 16) {
        fn(state, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

static void echo_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_echo_f32_process((DspFxEchoF32 *)s, a, b, c, d, n);
}
static void chorus_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_chorus_f32_process((DspFxChorusF32 *)s, a, b, c, d, n);
}
static void flanger_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_flanger_f32_process((DspFxFlangerF32 *)s, a, b, c, d, n);
}
static void phaser_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_phaser_f32_process((DspFxPhaserF32 *)s, a, b, c, d, n);
}
static void sweep_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_sweep_f32_process((DspFxSweepF32 *)s, a, b, c, d, n);
}
static void overdrive_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_overdrive_f32_process((DspFxOverdriveF32 *)s, a, b, c, d, n);
}
static void crusher_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_fx_crusher_f32_process((DspFxCrusherF32 *)s, a, b, c, d, n);
}
static void reverb_fn(void *s, const float *a, const float *b, float *c, float *d, size_t n) {
    dsp_reverb_f32_process((DspReverbF32 *)s, a, b, c, d, n);
}

/* Echo: 3 ms, feedback 0.6, ping-pong, wet 1 (the time is short so repeats fit the buffer). */
static void fx_echo_f32_run(const void *in, void *out) {
    dsp_fx_echo_f32_init(&s_8b.echo, 48000.0f, s_pool8b, kPool8b);
    dsp_fx_echo_f32_set_time_ms(&s_8b.echo, 3.0f);
    dsp_fx_echo_f32_set_feedback(&s_8b.echo, 0.6f);
    dsp_fx_echo_f32_set_ping_pong(&s_8b.echo, 1);
    dsp_fx_echo_f32_set_amount(&s_8b.echo, 1.0f);
    dsp_fx_echo_f32_reset(&s_8b.echo, 1);
    run_stereo16(echo_fn, &s_8b.echo, in, out);
}

/* The echo at 96 kHz: the core at 48 kHz between the half-band filters. 3 ms, feedback 0.6. */
static void fx_echo96_f32_run(const void *in, void *out) {
    dsp_fx_echo_f32_init(&s_8b.echo, 96000.0f, s_pool8b, kPool8b);
    dsp_fx_echo_f32_set_time_ms(&s_8b.echo, 3.0f);
    dsp_fx_echo_f32_set_feedback(&s_8b.echo, 0.6f);
    dsp_fx_echo_f32_set_amount(&s_8b.echo, 1.0f);
    dsp_fx_echo_f32_reset(&s_8b.echo, 1);
    run_stereo16(echo_fn, &s_8b.echo, in, out);
}

/* At 16 kHz: 512 frames are 32 ms, longer than the chorus's shortest delay (13 ms). */
static void fx_chorus_f32_run(const void *in, void *out) {
    dsp_fx_chorus_f32_init(&s_8b.chorus, 16000.0f, s_pool8b, kPool8b);
    dsp_lfo_f32_set_rate(&s_8b.chorus.lfo, 20.0f); /* Fast, so the short case sweeps. */
    dsp_fx_chorus_f32_set_amount(&s_8b.chorus, 1.0f);
    run_stereo16(chorus_fn, &s_8b.chorus, in, out);
}

static void fx_flanger_f32_run(const void *in, void *out) {
    dsp_fx_flanger_f32_init(&s_8b.flanger, 48000.0f, s_pool8b, kPool8b);
    dsp_lfo_f32_set_rate(&s_8b.flanger.lfo, 20.0f);
    dsp_fx_flanger_f32_set_feedback(&s_8b.flanger, 0.7f);
    dsp_fx_flanger_f32_set_amount(&s_8b.flanger, 1.0f);
    run_stereo16(flanger_fn, &s_8b.flanger, in, out);
}

static void fx_phaser_f32_run(const void *in, void *out) {
    dsp_fx_phaser_f32_init(&s_8b.phaser, 48000.0f);
    dsp_lfo_f32_set_rate(&s_8b.phaser.lfo, 20.0f);
    dsp_fx_phaser_f32_set_stages(&s_8b.phaser, 8);
    dsp_fx_phaser_f32_set_amount(&s_8b.phaser, 1.0f);
    run_stereo16(phaser_fn, &s_8b.phaser, in, out);
}

/* Sweep: the position ramps from the default 0.5 down to 0.1 (low-pass, closing). */
static void fx_sweep_f32_run(const void *in, void *out) {
    dsp_fx_sweep_f32_init(&s_8b.sweep, 48000.0f);
    dsp_fx_sweep_f32_set_resonance(&s_8b.sweep, 3.0f);
    dsp_fx_sweep_f32_set_amount(&s_8b.sweep, 0.1f);
    run_stereo16(sweep_fn, &s_8b.sweep, in, out);
}

static void fx_overdrive_f32_run(const void *in, void *out) {
    dsp_fx_overdrive_f32_init(&s_8b.overdrive, 48000.0f);
    dsp_fx_overdrive_f32_set_asymmetric(&s_8b.overdrive, 1);
    dsp_fx_overdrive_f32_set_amount(&s_8b.overdrive, 0.8f);
    run_stereo16(overdrive_fn, &s_8b.overdrive, in, out);
}

static void fx_crusher_f32_run(const void *in, void *out) {
    dsp_fx_crusher_f32_init(&s_8b.crusher, 48000.0f);
    dsp_fx_crusher_f32_set_dither(&s_8b.crusher, 1);
    dsp_fx_crusher_f32_set_amount(&s_8b.crusher, 1.0f);
    run_stereo16(crusher_fn, &s_8b.crusher, in, out);
}

/* The slot: phaser on at once (no delay memory to clear), then switched to the flanger. */
static void fxslot_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    dsp_fxslot_f32_init(&s_8b.slot, 48000.0f, s_pool8b, kPool8b);
    dsp_fxslot_f32_select(&s_8b.slot, kDspFxPhaser);
    dsp_fxslot_f32_reset(&s_8b.slot);
    s_8b.slot.dirty_len = 0; /* The pool was just cleared by init. */
    dsp_fxslot_f32_set_on(&s_8b.slot, 1);
    mark();
    for (size_t i = 0; i < half; i += 16) {
        if (i == half / 2) {
            dsp_fxslot_f32_select(&s_8b.slot, kDspFxFlanger);
        }
        dsp_fxslot_f32_process(&s_8b.slot, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

/* The reverb at 16 kHz, so its lines fit the shared pool (7610 floats); 0.5 s low, 0.2 s high. */
static void reverb_f32_run(const void *in, void *out) {
    dsp_reverb_f32_init(&s_8b.reverb, 16000.0f, s_pool8b, kPool8b);
    dsp_reverb_f32_set_decay(&s_8b.reverb, 0.5f, 0.2f);
    dsp_reverb_f32_set_predelay_ms(&s_8b.reverb, 0.0f);
    run_stereo16(reverb_fn, &s_8b.reverb, in, out);
}

/* Batch 8c. Small states, so plain statics (one union: the cases never run together). */
static union {
    DspMixerF32 mixer;
    DspCrossfeedF32 crossfeed;
    DspMeterF32 meter;
} s_8c;

/* The monitor mixer as the device will use it: 8 mono channels of 128 frames each (the input
 * buffer cut in eight). 0 and 1: the strips, panned and sent to the reverb; 2 and 3: USB
 * playback, hard left and right, sent; 4 and 5: S/PDIF, muted (skipped); 6 and 7: the reverb
 * return, hard left and right, no send. Half-way, input 1 pans right and input 2 mutes, so two
 * channels run their ramps (20 ms, longer than the case) to the end. Output: main L, main R,
 * send L, send R, 128 words each; the rest 0. Frames: 128, so channels = 8 for the bench. */
static void mixer_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    enum { kN = kDspSelftestFrames / 8 };
    static const float kPan[8] = {-0.5f, 0.3f, -1.0f, 1.0f, -1.0f, 1.0f, -1.0f, 1.0f};
    static const float kSend[8] = {0.5f, 0.25f, 0.1f, 0.1f, 0.0f, 0.0f, 0.0f, 0.0f};
    (void)dsp_mixer_f32_init(&s_8c.mixer, 48000.0f, 8, 20.0f);
    for (int32_t c = 0; c < 8; ++c) {
        dsp_mixer_f32_set_channel(&s_8c.mixer, c, c < 2 ? 0.8f : 1.0f, kPan[c], kSend[c],
                                  c == 4 || c == 5);
    }
    dsp_mixer_f32_reset(&s_8c.mixer);
    const float *ins[8];
    for (int c = 0; c < 8; ++c) {
        ins[c] = x + c * kN;
    }
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        y[i] = 0.0f;
    }
    mark();
    for (size_t i = 0; i < kN; i += 16) {
        if (i == kN / 2) {
            dsp_mixer_f32_set_channel(&s_8c.mixer, 0, 0.8f, 0.8f, 0.5f, 0);
            dsp_mixer_f32_set_channel(&s_8c.mixer, 1, 0.8f, 0.3f, 0.25f, 1);
        }
        const float *blk[8];
        for (int c = 0; c < 8; ++c) {
            blk[c] = ins[c] + i;
        }
        dsp_mixer_f32_process(&s_8c.mixer, blk, y + i, y + kN + i, y + 2 * kN + i,
                              y + 3 * kN + i, 16);
    }
}

/* Crossfeed at full amount (settled), then at 256 frames down to 0.5 (ramped over 10 ms). */
static void crossfeed_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    dsp_crossfeed_f32_init(&s_8c.crossfeed, 48000.0f, 10.0f);
    dsp_crossfeed_f32_set_amount(&s_8c.crossfeed, 1.0f);
    dsp_crossfeed_f32_reset(&s_8c.crossfeed);
    mark();
    for (size_t i = 0; i < half; i += 16) {
        if (i == half / 2) {
            dsp_crossfeed_f32_set_amount(&s_8c.crossfeed, 0.5f);
        }
        dsp_crossfeed_f32_process(&s_8c.crossfeed, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

/* BS.1770-4's published 48 kHz K-weighting, as float: the meter case does not depend on the
 * owner's exercise or on the C library. */
static const DspBiquadCoefsF32 kKweight48[2] = {
    {1.53512485958697f, -2.69169618940638f, 1.19839281085285f, -1.69065929318241f,
     0.73248077421585f},
    {1.0f, -2.0f, 1.0f, -1.99004745483398f, 0.99007225036621f},
};

/* The meter, stereo. The nominal rate is 4800 Hz, so a 100 ms loudness block is 480 samples and
 * one completes inside the case; the K-weighting is the 48 kHz one, and the ballistics are set
 * as plain numbers, so no C library function shapes the output. After each block of 16 frames
 * the case writes 16 words: held peak L R, largest peak L R, mean square L R, true peak L R, the
 * newest block power, the blocks done, and zeros. */
static void meter_run(const void *in, void *out, int32_t flags) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    DspMeterF32 *m = &s_8c.meter;
    (void)dsp_meter_f32_init(m, 4800.0f, 2, flags);
    dsp_meter_f32_set_kweight(m, kKweight48);
    m->hold_samples = 48;
    m->decay_coef = 0.99f;
    m->rms_coef = 0.999f;
    for (size_t i = 0; i < kDspSelftestFrames; ++i) {
        y[i] = 0.0f;
    }
    mark();
    for (size_t i = 0; i < half; i += 16) {
        dsp_meter_f32_process(m, x + i, x + half + i, 16);
        float *o = y + i;
        o[0] = m->held[0];
        o[1] = m->held[1];
        o[2] = m->max_peak[0];
        o[3] = m->max_peak[1];
        o[4] = m->ms[0];
        o[5] = m->ms[1];
        o[6] = m->max_tp[0];
        o[7] = m->max_tp[1];
        o[8] = (float)dsp_meter_f32_power(m, 1);
        o[9] = (float)m->blocks_done;
    }
}

static void meter_f32_run(const void *in, void *out) {
    meter_run(in, out, kDspMeterTruePeak | kDspMeterLoudness);
}
static void meter_peak_f32_run(const void *in, void *out) { meter_run(in, out, 0); }

/* Batch 9's costing spike: the room correction's FFT and convolver at the sizes SPEC 3.4 assumes.
 * They come last in the list, so a build that left them out would keep every other index. */

/* rfft512_f32: two forward 512-point transforms of the noise; the output is their spectra. */
static void rfft512_f32_run(const void *in, void *out) {
    DspRfftF32 fft;
    (void)dsp_rfft_f32_init(&fft, 512);
    mark();
    dsp_rfft_f32_forward(&fft, (const float *)in, (float *)out);
    dsp_rfft_f32_forward(&fft, (const float *)in + 512, (float *)out + 512);
}

#if !defined(DSP_SELFTEST_NO_PCONV)
/* pconv_f32: stereo, 4096 taps per channel (85 ms at 48 kHz), B = 256, in 16-frame calls as
 * the audio interrupt will make them. Each channel steps twice in the 512 frames. The filters
 * are noise under an exponential decay (time constant 683 taps), different per side. On the M7
 * the 138 KB pool sits in AXI SRAM, where the real filters will. */
enum { kPconvTaps = 4096, kPconvBlock = 256, kPconvMem = 17664 /* mem_needed(256, 4096) */ };
static float s_pool9[2 * kPconvMem] SELFTEST_AXI;
/* The filter is built in the 8b pool (7680 floats, idle while this case runs), which keeps the
 * M4's image inside its 256 KB of SRAM. */
static float *const s_filter9 = s_pool8b;
static DspPconvF32 s_pconv[2];

static void room_filter(uint32_t seed) {
    DspNoise noise;
    dsp_noise_seed(&noise, seed);
    dsp_noise_f32(&noise, s_filter9, kPconvTaps, 0.2f);
    float g = 1.0f;
    for (size_t i = 0; i < kPconvTaps; ++i) {
        s_filter9[i] *= g;
        g *= 0.998536f; /* e^(-1/683) */
    }
}

static void pconv_f32_run(const void *in, void *out) {
    const float *x = (const float *)in;
    float *y = (float *)out;
    const size_t half = kDspSelftestFrames / 2;
    for (int ch = 0; ch < 2; ++ch) {
        (void)dsp_pconv_f32_init(&s_pconv[ch], kPconvBlock, kPconvTaps, s_pool9 + ch * kPconvMem,
                                 kPconvMem);
        room_filter(11u + (uint32_t)ch);
        (void)dsp_pconv_f32_set_filter(&s_pconv[ch], s_filter9, kPconvTaps);
    }
    mark();
    for (size_t i = 0; i < half; i += 16) {
        dsp_pconv_f32_process(&s_pconv[0], x + i, y + i, 16);
        dsp_pconv_f32_process(&s_pconv[1], x + half + i, y + half + i, 16);
    }
}
#endif

static const SelftestCase kCases[] = {
    {"gain_f32", kDspFmtF32, 1, gain_f32_input, gain_f32_run},
    {"noise_q31", kDspFmtQ31, 1, noise_q31_input, noise_q31_run},
    {"biquad_f32", kDspFmtF32, 1, noise_half_f32_input, biquad_f32_run},
    {"biquad_f64", kDspFmtF32, 1, noise_half_f32_input, biquad_f64_run},
    {"biquad_q31_round", kDspFmtQ31, 1, noise_quarter_q31_input, biquad_q31_round_run},
    {"biquad_q31_ef", kDspFmtQ31, 1, noise_quarter_q31_input, biquad_q31_ef_run},
    {"tone_f32", kDspFmtF32, 2, noise_half_f32_input, tone_f32_run},
    {"comp_f32", kDspFmtF32, 1, bursts_f32_input, comp_f32_run},
    {"gate_f32", kDspFmtF32, 1, bursts_f32_input, gate_f32_run},
    {"limiter_f32", kDspFmtF32, 2, bursts_f32_input, limiter_f32_run},
    {"limiter_sp_f32", kDspFmtF32, 2, bursts_f32_input, limiter_sp_f32_run},
    {"sat_os4_f32", kDspFmtF32, 1, bursts_f32_input, sat_os4_f32_run},
    {"sat_adaa_f32", kDspFmtF32, 1, bursts_f32_input, sat_adaa_f32_run},
    {"sat_os2_f32", kDspFmtF32, 1, bursts_f32_input, sat_os2_f32_run},
    {"tanh_libm_f32", kDspFmtF32, 1, bursts_f32_input, tanh_libm_f32_run},
    {"tanh_fast_f32", kDspFmtF32, 1, bursts_f32_input, tanh_fast_f32_run},
    {"os4_pass_f32", kDspFmtF32, 1, bursts_f32_input, os4_pass_f32_run},
    {"delay_lagrange_f32", kDspFmtF32, 1, bursts_f32_input, delay_lagrange_f32_run},
    {"svf_f32", kDspFmtF32, 1, bursts_f32_input, svf_f32_run},
    {"fx_echo_f32", kDspFmtF32, 2, bursts_f32_input, fx_echo_f32_run},
    {"fx_echo96_f32", kDspFmtF32, 2, bursts_f32_input, fx_echo96_f32_run},
    {"fx_chorus_f32", kDspFmtF32, 2, bursts_f32_input, fx_chorus_f32_run},
    {"fx_flanger_f32", kDspFmtF32, 2, bursts_f32_input, fx_flanger_f32_run},
    {"fx_phaser_f32", kDspFmtF32, 2, bursts_f32_input, fx_phaser_f32_run},
    {"fx_sweep_f32", kDspFmtF32, 2, bursts_f32_input, fx_sweep_f32_run},
    {"fx_overdrive_f32", kDspFmtF32, 2, bursts_f32_input, fx_overdrive_f32_run},
    {"fx_crusher_f32", kDspFmtF32, 2, bursts_f32_input, fx_crusher_f32_run},
    {"fxslot_f32", kDspFmtF32, 2, bursts_f32_input, fxslot_f32_run},
    {"reverb_f32", kDspFmtF32, 2, bursts_f32_input, reverb_f32_run},
    {"mixer_f32", kDspFmtF32, 8, bursts_f32_input, mixer_f32_run},
    {"crossfeed_f32", kDspFmtF32, 2, bursts_f32_input, crossfeed_f32_run},
    {"meter_f32", kDspFmtF32, 2, bursts_f32_input, meter_f32_run},
    {"meter_peak_f32", kDspFmtF32, 2, bursts_f32_input, meter_peak_f32_run},
    {"rfft512_f32", kDspFmtF32, 1, gain_f32_input, rfft512_f32_run},
#if !defined(DSP_SELFTEST_NO_PCONV) /* The M4's image: its 256 KB cannot hold the 138 KB pool too
                                       * (measured there once, 2026-11-18: 2545 cycles per frame). */
    {"pconv_f32", kDspFmtF32, 2, gain_f32_input, pconv_f32_run},
#endif
};

size_t dsp_selftest_count(void) { return sizeof(kCases) / sizeof(kCases[0]); }

const char *dsp_selftest_name(size_t index) {
    return index < dsp_selftest_count() ? kCases[index].name : NULL;
}

int dsp_selftest_fmt(size_t index) {
    return index < dsp_selftest_count() ? (int)kCases[index].fmt : -1;
}

void dsp_selftest_input(size_t index, void *in) {
    if (index < dsp_selftest_count()) {
        kCases[index].input(in);
    }
}

int dsp_selftest_channels(size_t index) {
    return index < dsp_selftest_count() ? kCases[index].channels : 0;
}

void dsp_selftest_run(size_t index, const void *in, void *out) {
    if (index < dsp_selftest_count()) {
        kCases[index].run(in, out);
    }
}
