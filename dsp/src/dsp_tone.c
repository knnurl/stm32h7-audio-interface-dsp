#include "dsp/dsp_tone.h"

#include "dsp/dsp_coef.h"

#include <math.h>
#include <string.h>

#define kSnapDb 0.001f
#define kSilentState 1e-9
#define kMidQ 0.7
#define kShelfSlope 1.0

static void design(DspToneF32 *tone, int band) {
    DspBiquadCoefsD d;
    const double fs = tone->sample_rate_hz;
    const double f0 = tone->freq_hz[band];
    const double gain = tone->smoothed_db[band];
    switch (band) {
    case kDspToneBass:
        dsp_coef_low_shelf(&d, fs, f0, kShelfSlope, gain);
        break;
    case kDspToneMid:
        dsp_coef_peak(&d, fs, f0, kMidQ, gain);
        break;
    default:
        dsp_coef_high_shelf(&d, fs, f0, kShelfSlope, gain);
        break;
    }
    DspBiquadCoefsF64 *c = &tone->coefs[band];
    c->b0 = d.b0;
    c->b1 = d.b1;
    c->b2 = d.b2;
    c->a1 = d.a1;
    c->a2 = d.a2;
}

static int state_silent(const DspToneF32 *tone, int band) {
    for (int ch = 0; ch < 2; ++ch) {
        const DspBiquadStateF64 *st = &tone->state[ch][band];
        if (fabs(st->z1) > kSilentState || fabs(st->z2) > kSilentState) {
            return 0;
        }
    }
    return 1;
}

void dsp_tone_f32_init(DspToneF32 *tone, float sample_rate_hz) {
    memset(tone, 0, sizeof(*tone));
    tone->sample_rate_hz = sample_rate_hz;
    tone->smoothing_ms = 20.0f;
    tone->freq_hz[kDspToneBass] = 100.0f;
    tone->freq_hz[kDspToneMid] = 1000.0f;
    tone->freq_hz[kDspToneTreble] = 10000.0f;
}

void dsp_tone_f32_set_freqs(DspToneF32 *tone, float bass_hz, float mid_hz, float treble_hz) {
    tone->freq_hz[kDspToneBass] = bass_hz;
    tone->freq_hz[kDspToneMid] = mid_hz;
    tone->freq_hz[kDspToneTreble] = treble_hz;
    for (int b = 0; b < kDspToneBands; ++b) {
        tone->dirty[b] = 1;
    }
}

void dsp_tone_f32_set_db(DspToneF32 *tone, int32_t band, float gain_db) {
    if (band < 0 || band >= kDspToneBands) {
        return;
    }
    if (gain_db > 12.0f) {
        gain_db = 12.0f;
    } else if (gain_db < -12.0f) {
        gain_db = -12.0f;
    }
    tone->target_db[band] = gain_db;
}

void dsp_tone_f32_reset(DspToneF32 *tone) {
    memset(tone->state, 0, sizeof(tone->state));
    for (int b = 0; b < kDspToneBands; ++b) {
        tone->smoothed_db[b] = tone->target_db[b];
        tone->active[b] = tone->target_db[b] != 0.0f;
        tone->dirty[b] = 1;
    }
}

/* Moves the smoothed gains one block and redesigns what moved. */
static void update_bands(DspToneF32 *tone, size_t n_frames) {
    const float tau_blocks = tone->smoothing_ms * 0.001f * tone->sample_rate_hz / (float)n_frames;
    const float k = -expm1f(-1.0f / tau_blocks);
    for (int b = 0; b < kDspToneBands; ++b) {
        const float target = tone->target_db[b];
        if (tone->smoothed_db[b] != target) {
            float g = tone->smoothed_db[b] + k * (target - tone->smoothed_db[b]);
            if (fabsf(target - g) < kSnapDb) {
                g = target;
            }
            tone->smoothed_db[b] = g;
            tone->dirty[b] = 1;
        }
        if (!tone->active[b]) {
            if (tone->smoothed_db[b] == 0.0f) {
                continue; /* Skipped, and stays skipped. */
            }
            memset(&tone->state[0][b], 0, sizeof(DspBiquadStateF64));
            memset(&tone->state[1][b], 0, sizeof(DspBiquadStateF64));
            tone->active[b] = 1;
            tone->dirty[b] = 1;
        } else if (tone->smoothed_db[b] == 0.0f && state_silent(tone, b)) {
            tone->active[b] = 0; /* Identity response and no signal left inside: skip. */
            memset(&tone->state[0][b], 0, sizeof(DspBiquadStateF64));
            memset(&tone->state[1][b], 0, sizeof(DspBiquadStateF64));
            continue;
        }
        if (tone->dirty[b]) {
            design(tone, b);
            tone->dirty[b] = 0;
        }
    }
}

void dsp_tone_f32_process(DspToneF32 *tone, const float *in_l, const float *in_r, float *out_l,
                          float *out_r, size_t n_frames) {
    if (n_frames == 0) {
        return;
    }
    update_bands(tone, n_frames);
    const float *src_l = in_l;
    const float *src_r = in_r;
    for (int b = 0; b < kDspToneBands; ++b) {
        if (!tone->active[b]) {
            continue;
        }
        dsp_biquad_f64_section(&tone->coefs[b], &tone->state[0][b], src_l, out_l, n_frames);
        dsp_biquad_f64_section(&tone->coefs[b], &tone->state[1][b], src_r, out_r, n_frames);
        src_l = out_l;
        src_r = out_r;
    }
    /* Each channel on its own: one may be processed in place and the other not. */
    if (src_l != out_l) {
        memmove(out_l, in_l, n_frames * sizeof(float));
    }
    if (src_r != out_r) {
        memmove(out_r, in_r, n_frames * sizeof(float));
    }
}
