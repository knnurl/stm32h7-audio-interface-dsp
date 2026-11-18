/* THE OWNER'S EXERCISE: replace this stub with the design that dsp/include/dsp/dsp_kweight.h
 * specifies (docs/exercises/EX8c_kweighting.md). Until then the loudness meter runs unweighted
 * (dsp_meter reports it), and tests/exercises/test_ex8c_kweight.py fails. */
#include "dsp/dsp_kweight.h"

int32_t dsp_kweight_design(double sample_rate_hz, DspBiquadCoefsF64 sections[2]) {
    (void)sample_rate_hz;
    for (int i = 0; i < 2; ++i) {
        sections[i].b0 = 1.0;
        sections[i].b1 = 0.0;
        sections[i].b2 = 0.0;
        sections[i].a1 = 0.0;
        sections[i].a2 = 0.0;
    }
    return -1;
}
