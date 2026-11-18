#include "dsp/dsp_meter.h"

#include "dsp/dsp_kweight.h"

#include <math.h>

enum { kChunk = 16 };

int32_t dsp_meter_f32_init(DspMeterF32 *meter, float sample_rate_hz, int32_t channels,
                           int32_t flags) {
    if (channels < 1 || channels > 2) {
        return -1;
    }
    meter->sample_rate_hz = sample_rate_hz;
    meter->channels = channels;
    meter->flags = flags;
    dsp_meter_f32_set_ballistics(meter, 1000.0f, 20.0f / 1.7f, 300.0f);
    DspBiquadCoefsF64 d[2];
    meter->kweighted = dsp_kweight_design((double)sample_rate_hz, d) == 0;
    for (int s = 0; s < 2; ++s) {
        if (!meter->kweighted) {
            d[s].b0 = 1.0;
            d[s].b1 = d[s].b2 = d[s].a1 = d[s].a2 = 0.0;
        }
        meter->kw[s].b0 = (float)d[s].b0;
        meter->kw[s].b1 = (float)d[s].b1;
        meter->kw[s].b2 = (float)d[s].b2;
        meter->kw[s].a1 = (float)d[s].a1;
        meter->kw[s].a2 = (float)d[s].a2;
    }
    meter->block_len = (int32_t)(sample_rate_hz * 0.1f + 0.5f);
    if (meter->block_len < 1) {
        meter->block_len = 1;
    }
    dsp_meter_f32_reset(meter);
    return 0;
}

void dsp_meter_f32_set_ballistics(DspMeterF32 *meter, float hold_ms, float decay_db_per_s,
                                  float rms_ms) {
    const float fs = meter->sample_rate_hz;
    meter->hold_samples = (int32_t)(hold_ms * 0.001f * fs + 0.5f);
    meter->decay_coef = powf(10.0f, -decay_db_per_s / (20.0f * fs));
    meter->rms_coef = rms_ms > 0.0f ? expf(-1.0f / (rms_ms * 0.001f * fs)) : 0.0f;
}

void dsp_meter_f32_set_kweight(DspMeterF32 *meter, const DspBiquadCoefsF32 sections[2]) {
    meter->kw[0] = sections[0];
    meter->kw[1] = sections[1];
    meter->kweighted = 1;
}

void dsp_meter_f32_reset(DspMeterF32 *meter) {
    for (int ch = 0; ch < 2; ++ch) {
        meter->held[ch] = 0.0f;
        meter->hold_left[ch] = 0;
        meter->max_peak[ch] = 0.0f;
        meter->ms[ch] = 0.0f;
        meter->max_tp[ch] = 0.0f;
        for (int32_t i = 0; i < 2 * kDspTruePeakTaps; ++i) {
            meter->tp_hist[ch][i] = 0.0f;
        }
        for (int s = 0; s < 2; ++s) {
            meter->kw_state[ch][s].z1 = 0.0f;
            meter->kw_state[ch][s].z2 = 0.0f;
        }
    }
    meter->tp_pos = 0;
    meter->block_fill = 0;
    meter->block_sum = 0.0;
    for (int32_t b = 0; b < kDspMeterBlocks; ++b) {
        meter->block_power[b] = 0.0;
    }
    meter->block_pos = 0;
    meter->blocks_done = 0u;
}

static void peak_rms(DspMeterF32 *m, int ch, const float *x, size_t n) {
    float held = m->held[ch], mx = m->max_peak[ch], ms = m->ms[ch];
    int32_t left = m->hold_left[ch];
    const float decay = m->decay_coef, c = m->rms_coef;
    const int32_t hold = m->hold_samples;
    for (size_t i = 0; i < n; ++i) {
        const float a = fabsf(x[i]);
        if (a >= held) {
            held = a;
            left = hold;
        } else if (left > 0) {
            --left;
        } else {
            held *= decay;
        }
        mx = a > mx ? a : mx;
        const float x2 = x[i] * x[i];
        ms = x2 + c * (ms - x2);
    }
    m->held[ch] = held;
    m->hold_left[ch] = left;
    m->max_peak[ch] = mx;
    m->ms[ch] = ms;
}

static void true_peak(DspMeterF32 *m, const float *const *x, size_t n) {
    const int32_t taps = kDspTruePeakTaps;
    int32_t pos = m->tp_pos;
    for (size_t i = 0; i < n; ++i) {
        pos = pos == 0 ? taps - 1 : pos - 1;
        for (int ch = 0; ch < m->channels; ++ch) {
            float *hist = m->tp_hist[ch];
            hist[pos] = x[ch][i];
            hist[pos + taps] = x[ch][i];
            const float p = dsp_true_peak16(&hist[pos]);
            m->max_tp[ch] = p > m->max_tp[ch] ? p : m->max_tp[ch];
        }
    }
    m->tp_pos = pos;
}

static void loudness(DspMeterF32 *m, const float *const *x, size_t n) {
    float k[2][kChunk];
    for (size_t start = 0; start < n; start += kChunk) {
        const size_t len = n - start < kChunk ? n - start : kChunk;
        for (int ch = 0; ch < m->channels; ++ch) {
            dsp_biquad_f32_section(&m->kw[0], &m->kw_state[ch][0], x[ch] + start, k[ch], len);
            dsp_biquad_f32_section(&m->kw[1], &m->kw_state[ch][1], k[ch], k[ch], len);
        }
        for (size_t i = 0; i < len; ++i) {
            float p = k[0][i] * k[0][i];
            if (m->channels == 2) {
                p += k[1][i] * k[1][i];
            }
            m->block_sum += (double)p;
            if (++m->block_fill == m->block_len) {
                m->block_power[m->block_pos] = m->block_sum / (double)m->block_len;
                m->block_pos = m->block_pos + 1 == kDspMeterBlocks ? 0 : m->block_pos + 1;
                m->block_sum = 0.0;
                m->block_fill = 0;
                ++m->blocks_done;
            }
        }
    }
}

void dsp_meter_f32_process(DspMeterF32 *meter, const float *in_l, const float *in_r,
                           size_t n_frames) {
    const float *x[2] = {in_l, meter->channels == 2 ? in_r : in_l};
    for (int ch = 0; ch < meter->channels; ++ch) {
        peak_rms(meter, ch, x[ch], n_frames);
    }
    if (meter->flags & kDspMeterTruePeak) {
        true_peak(meter, x, n_frames);
    }
    if (meter->flags & kDspMeterLoudness) {
        loudness(meter, x, n_frames);
    }
}

double dsp_meter_f32_power(const DspMeterF32 *meter, int32_t n_blocks) {
    if (n_blocks < 1) {
        n_blocks = 1;
    }
    if (n_blocks > kDspMeterBlocks) {
        n_blocks = kDspMeterBlocks;
    }
    double sum = 0.0;
    int32_t b = meter->block_pos;
    for (int32_t i = 0; i < n_blocks; ++i) {
        b = b == 0 ? kDspMeterBlocks - 1 : b - 1;
        sum += meter->block_power[b];
    }
    return sum / (double)n_blocks;
}

static float to_db(float lin) {
    return lin > 1e-6f ? 20.0f * log10f(lin) : DSP_METER_FLOOR_DB; /* 1e-6 is -120 dB. */
}

static float to_lufs(double power) {
    const float l = power > 0.0 ? -0.691f + 10.0f * (float)log10(power) : DSP_METER_FLOOR_DB;
    return l > DSP_METER_FLOOR_DB ? l : DSP_METER_FLOOR_DB;
}

void dsp_meter_f32_snapshot(DspMeterF32 *meter, DspMeterRaw *raw) {
    for (int ch = 0; ch < 2; ++ch) {
        raw->held[ch] = meter->held[ch];
        raw->max_peak[ch] = meter->max_peak[ch];
        raw->ms[ch] = meter->ms[ch];
        raw->max_tp[ch] = meter->max_tp[ch];
        meter->max_peak[ch] = 0.0f;
        meter->max_tp[ch] = 0.0f;
    }
    const int loud = (meter->flags & kDspMeterLoudness) != 0;
    raw->momentary_power = loud ? dsp_meter_f32_power(meter, kDspMeterMomentaryBlocks) : 0.0;
    raw->short_term_power = loud ? dsp_meter_f32_power(meter, kDspMeterBlocks) : 0.0;
    raw->loudness_blocks = meter->blocks_done;
    raw->channels = meter->channels;
    raw->flags = meter->flags;
    raw->kweighted = meter->kweighted;
}

void dsp_meter_raw_to_reading(const DspMeterRaw *raw, DspMeterReading *r) {
    for (int ch = 0; ch < 2; ++ch) {
        const int on = ch < raw->channels;
        r->peak_db[ch] = on ? to_db(raw->held[ch]) : DSP_METER_FLOOR_DB;
        r->max_peak_db[ch] = on ? to_db(raw->max_peak[ch]) : DSP_METER_FLOOR_DB;
        r->rms_db[ch] = on ? to_db(sqrtf(raw->ms[ch])) : DSP_METER_FLOOR_DB;
        r->true_peak_db[ch] = on && (raw->flags & kDspMeterTruePeak)
                                  ? to_db(raw->max_tp[ch])
                                  : DSP_METER_FLOOR_DB;
    }
    if (raw->flags & kDspMeterLoudness) {
        r->momentary_lufs = to_lufs(raw->momentary_power);
        r->short_term_lufs = to_lufs(raw->short_term_power);
    } else {
        r->momentary_lufs = DSP_METER_FLOOR_DB;
        r->short_term_lufs = DSP_METER_FLOOR_DB;
    }
    r->loudness_blocks = raw->loudness_blocks;
    r->kweighted = raw->kweighted;
}

void dsp_meter_f32_read(DspMeterF32 *meter, DspMeterReading *r) {
    DspMeterRaw raw;
    dsp_meter_f32_snapshot(meter, &raw);
    dsp_meter_raw_to_reading(&raw, r);
}
