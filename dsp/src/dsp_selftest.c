#include "dsp/dsp_selftest.h"

#include "dsp/dsp_biquad.h"
#include "dsp/dsp_gain.h"
#include "dsp/dsp_testsig.h"
#include "dsp/dsp_tone.h"

typedef struct {
    const char *name;
    DspFmt fmt;
    void (*input)(void *in);
    void (*run)(const void *in, void *out);
} SelftestCase;

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
    /* In blocks of 16, as the audio interrupt will call it. */
    for (size_t i = 0; i < kDspSelftestFrames; i += 16) {
        dsp_biquad_f32_process(&filter, (const float *)in + i, (float *)out + i, 16);
    }
}

/* The same cascade with double state: the kernel the PEQ and tone control use. */
static void biquad_f64_run(const void *in, void *out) {
    DspBiquadStateF64 state[3] = {{0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}};
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
    for (size_t i = 0; i < half; i += 16) {
        if (i == 256) {
            dsp_tone_f32_set_db(&tone, kDspToneBass, -12.0f);
        }
        dsp_tone_f32_process(&tone, x + i, x + half + i, y + i, y + half + i, 16);
    }
}

static const SelftestCase kCases[] = {
    {"gain_f32", kDspFmtF32, gain_f32_input, gain_f32_run},
    {"noise_q31", kDspFmtQ31, noise_q31_input, noise_q31_run},
    {"biquad_f32", kDspFmtF32, noise_half_f32_input, biquad_f32_run},
    {"biquad_f64", kDspFmtF32, noise_half_f32_input, biquad_f64_run},
    {"biquad_q31_round", kDspFmtQ31, noise_quarter_q31_input, biquad_q31_round_run},
    {"biquad_q31_ef", kDspFmtQ31, noise_quarter_q31_input, biquad_q31_ef_run},
    {"tone_f32", kDspFmtF32, noise_half_f32_input, tone_f32_run},
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

void dsp_selftest_run(size_t index, const void *in, void *out) {
    if (index < dsp_selftest_count()) {
        kCases[index].run(in, out);
    }
}
