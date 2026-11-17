#include "dsp/dsp_peq.h"

#include "dsp/dsp_coef.h"

#include <string.h>

static const DspBiquadCoefsF64 kIdentity = {1.0, 0.0, 0.0, 0.0, 0.0};

static void from_design(const DspBiquadCoefsD *d, DspBiquadCoefsF64 *out) {
    out->b0 = d->b0;
    out->b1 = d->b1;
    out->b2 = d->b2;
    out->a1 = d->a1;
    out->a2 = d->a2;
}

/* Starts a ramp from wherever the coefficients are now towards the targets. */
static void start_ramp(DspPeqF32 *peq) {
    if (peq->ramp_blocks <= 1) {
        memcpy(peq->current, peq->target, sizeof(peq->current));
        peq->remaining = 0;
        return;
    }
    const double n = (double)peq->ramp_blocks;
    for (int s = 0; s < kDspPeqSections; ++s) {
        const DspBiquadCoefsF64 *c = &peq->current[s];
        const DspBiquadCoefsF64 *t = &peq->target[s];
        DspBiquadCoefsF64 *d = &peq->step[s];
        d->b0 = (t->b0 - c->b0) / n;
        d->b1 = (t->b1 - c->b1) / n;
        d->b2 = (t->b2 - c->b2) / n;
        d->a1 = (t->a1 - c->a1) / n;
        d->a2 = (t->a2 - c->a2) / n;
    }
    peq->remaining = peq->ramp_blocks;
}

void dsp_peq_f32_init(DspPeqF32 *peq, float sample_rate_hz, int32_t ramp_blocks) {
    peq->sample_rate_hz = sample_rate_hz;
    peq->ramp_blocks = ramp_blocks;
    for (int s = 0; s < kDspPeqSections; ++s) {
        peq->current[s] = kIdentity;
        peq->target[s] = kIdentity;
    }
    memset(peq->step, 0, sizeof(peq->step));
    peq->remaining = 0;
    memset(peq->state, 0, sizeof(peq->state));
}

void dsp_peq_f32_reset(DspPeqF32 *peq) {
    memcpy(peq->current, peq->target, sizeof(peq->current));
    peq->remaining = 0;
    memset(peq->state, 0, sizeof(peq->state));
}

void dsp_peq_f32_set_highpass(DspPeqF32 *peq, float cutoff_hz) {
    if (cutoff_hz <= 0.0f) {
        peq->target[0] = kIdentity;
    } else {
        DspBiquadCoefsD d;
        dsp_coef_highpass(&d, peq->sample_rate_hz, cutoff_hz, 0.70710678118654752);
        from_design(&d, &peq->target[0]);
    }
    start_ramp(peq);
}

void dsp_peq_f32_set_band(DspPeqF32 *peq, int32_t index, const DspPeqBand *band) {
    if (index < 0 || index >= kDspPeqBands) {
        return;
    }
    DspBiquadCoefsD d;
    switch (band->type) {
    case kDspPeqPeak:
        dsp_coef_peak(&d, peq->sample_rate_hz, band->freq_hz, band->q, band->gain_db);
        break;
    case kDspPeqLowShelf:
        dsp_coef_low_shelf(&d, peq->sample_rate_hz, band->freq_hz, band->q, band->gain_db);
        break;
    case kDspPeqHighShelf:
        dsp_coef_high_shelf(&d, peq->sample_rate_hz, band->freq_hz, band->q, band->gain_db);
        break;
    default:
        dsp_coef_identity(&d);
        break;
    }
    from_design(&d, &peq->target[index + 1]);
    start_ramp(peq);
}

void dsp_peq_f32_process(DspPeqF32 *peq, const float *in, float *out, size_t n_frames) {
    if (peq->remaining > 0) {
        if (--peq->remaining == 0) {
            memcpy(peq->current, peq->target, sizeof(peq->current));
        } else {
            for (int s = 0; s < kDspPeqSections; ++s) {
                DspBiquadCoefsF64 *c = &peq->current[s];
                const DspBiquadCoefsF64 *d = &peq->step[s];
                c->b0 += d->b0;
                c->b1 += d->b1;
                c->b2 += d->b2;
                c->a1 += d->a1;
                c->a2 += d->a2;
            }
        }
    }
    const float *src = in;
    for (int s = 0; s < kDspPeqSections; ++s) {
        dsp_biquad_f64_section(&peq->current[s], &peq->state[s], src, out, n_frames);
        src = out;
    }
}
