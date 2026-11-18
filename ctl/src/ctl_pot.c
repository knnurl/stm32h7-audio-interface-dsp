/* One panel potentiometer: average, smoother, rest detection, shaping (ctl_pot.h). */
#include "ctl/ctl_pot.h"

#include <math.h>

float ctl_pot_coef(float tau_ms) {
    const float readings = tau_ms * ((float)CTL_POT_RATE_HZ / 1000.0f);
    return readings <= 0.0f ? 1.0f : 1.0f - expf(-1.0f / readings);
}

void ctl_pot_init(CtlPot *pot, uint32_t adc_bits, float tau_ms) {
    const uint32_t max_code = (adc_bits >= 32u) ? 0xFFFFFFFFu : ((1u << adc_bits) - 1u);
    pot->scale_den = (float)CTL_POT_AVERAGE * (float)max_code;
    pot->coef = ctl_pot_coef(tau_ms);
    pot->smooth = 0.0f;
    pot->out = 0.0f;
    pot->window = 0.0f;
    pot->still = 0u;
    pot->started = 0u;
    pot->at_rest = 0u;
    pot->reports = 0u;
}

static float clamp01(float x) { return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x); }

static int report(CtlPot *pot, float *travel) {
    pot->out = pot->smooth;
    ++pot->reports;
    *travel = pot->out;
    return 1;
}

int ctl_pot_update(CtlPot *pot, uint32_t sum, float *travel) {
    const float x = clamp01((float)sum / pot->scale_den);
    if (pot->started == 0u) {
        /* The first reading is the position: no ramp up from zero at start-up. */
        pot->started = 1u;
        pot->smooth = x;
        pot->window = x;
        pot->still = 0u;
        return report(pot, travel);
    }
    pot->smooth += pot->coef * (x - pot->smooth);

    /* Rest detection: the smoothed travel inside a window of +/- CTL_POT_REST_WINDOW around
     * where it last moved to, for CTL_POT_STILL_MS. */
    if (fabsf(pot->smooth - pot->window) > CTL_POT_REST_WINDOW) {
        pot->window = pot->smooth;
        pot->still = 0u;
    } else if (pot->still < CTL_POT_STILL_MS) {
        ++pot->still;
    }

    if (pot->at_rest != 0u) {
        if (fabsf(pot->smooth - pot->out) > CTL_POT_HYSTERESIS) {
            pot->at_rest = 0u;
            return report(pot, travel);
        }
        return 0;
    }
    if (pot->still >= CTL_POT_STILL_MS) {
        pot->at_rest = 1u;
        return 0;
    }
    if (fabsf(pot->smooth - pot->out) >= CTL_POT_STEP) {
        return report(pot, travel);
    }
    return 0;
}

void ctl_pot_cal_default(CtlPotCal *cal) {
    cal->lo = 0.0f;
    cal->centre = 0.5f;
    cal->hi = 1.0f;
}

/* Distance d from a reference, 0 to `half`, with a dead zone of `zone` at its start and
 * CTL_POT_END_ZONE at its end, stretched back to 0..half. */
static float zoned(float d, float zone, float half) {
    const float span = half - zone - CTL_POT_END_ZONE;
    float y = (d - zone) / span * half;
    return y < 0.0f ? 0.0f : (y > half ? half : y);
}

float ctl_pot_shape(const CtlPotCal *cal, CtlPotKind kind, float travel) {
    if (kind == kCtlPotCentre) {
        if (travel <= cal->centre) {
            const float d = (cal->centre - travel) / (cal->centre - cal->lo) * 0.5f;
            return 0.5f - zoned(d, CTL_POT_CENTRE_ZONE, 0.5f);
        }
        const float d = (travel - cal->centre) / (cal->hi - cal->centre) * 0.5f;
        return 0.5f + zoned(d, CTL_POT_CENTRE_ZONE, 0.5f);
    }
    const float u = (travel - cal->lo) / (cal->hi - cal->lo);
    /* Both end zones: the same stretch as zoned() with the bottom end zone as its dead zone. */
    const float x = zoned(u, CTL_POT_END_ZONE, 1.0f);
    if (kind == kCtlPotVolume && x < CTL_POT_OFF_ZONE) {
        return 0.0f;
    }
    return x;
}
