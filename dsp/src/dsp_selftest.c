#include "dsp/dsp_selftest.h"

#include "dsp/dsp_gain.h"
#include "dsp/dsp_testsig.h"

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

static const SelftestCase kCases[] = {
    {"gain_f32", kDspFmtF32, gain_f32_input, gain_f32_run},
    {"noise_q31", kDspFmtQ31, noise_q31_input, noise_q31_run},
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
