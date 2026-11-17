#include "ctl/ctl_params.h"

#include <math.h>

static float clamp01(float x) {
    if (!(x > 0.0f)) { /* Also catches NaN. */
        return 0.0f;
    }
    return x < 1.0f ? x : 1.0f;
}

float ctl_param_clamp(const CtlParamDesc *desc, float value) {
    if (isnan(value)) {
        return desc->def;
    }
    if (desc->curve == kCtlCurveStep) {
        value = floorf(value + 0.5f);
    }
    if (value < desc->min) {
        return desc->min;
    }
    if (value > desc->max) {
        return desc->max;
    }
    return value;
}

float ctl_param_from_norm(const CtlParamDesc *desc, float x) {
    x = clamp01(x);
    float v;
    switch (desc->curve) {
    case kCtlCurveLog:
        v = desc->min * powf(desc->max / desc->min, x);
        break;
    case kCtlCurveVolume:
        v = x > 0.0f ? desc->max + 60.0f * log10f(x) : desc->min;
        break;
    case kCtlCurveStep:
    case kCtlCurveLinear:
    default:
        v = desc->min + x * (desc->max - desc->min);
        break;
    }
    /* Exact ends, whatever the rounding of the curve. */
    if (x == 0.0f) {
        v = desc->min;
    } else if (x == 1.0f) {
        v = desc->max;
    }
    return ctl_param_clamp(desc, v);
}

float ctl_param_to_norm(const CtlParamDesc *desc, float value) {
    value = ctl_param_clamp(desc, value);
    float x;
    switch (desc->curve) {
    case kCtlCurveLog:
        x = logf(value / desc->min) / logf(desc->max / desc->min);
        break;
    case kCtlCurveVolume:
        x = value <= desc->min ? 0.0f : powf(10.0f, (value - desc->max) / 60.0f);
        break;
    case kCtlCurveStep:
    case kCtlCurveLinear:
    default:
        x = (value - desc->min) / (desc->max - desc->min);
        break;
    }
    return clamp01(x);
}

float ctl_midi7_to_norm(uint8_t value) {
    if (value > 127u) {
        value = 127u;
    }
    if (value <= 64u) {
        return (float)value / 128.0f;
    }
    return 0.5f + (float)(value - 64u) / 126.0f;
}

uint8_t ctl_norm_to_midi7(float x) {
    x = clamp01(x);
    const float v = x <= 0.5f ? x * 128.0f : 64.0f + (x - 0.5f) * 126.0f;
    return (uint8_t)(v + 0.5f);
}
