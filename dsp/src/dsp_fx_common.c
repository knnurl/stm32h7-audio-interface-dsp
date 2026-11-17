#include "dsp/dsp_fx_common.h"

#include <math.h>

float dsp_onepole_coef(float sample_rate_hz, float fc_hz) {
    if (!(fc_hz > 0.0f)) {
        return 0.0f; /* No filtering for a non-positive or NaN corner. */
    }
    const float limit = 0.49f * sample_rate_hz;
    return expf(-6.28318530718f * (fc_hz > limit ? limit : fc_hz) / sample_rate_hz);
}
