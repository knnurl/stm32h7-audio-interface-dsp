#include "dsp/dsp_fastmath.h"

#include <stdint.h>
#include <string.h>

/* From tools/design/b6_coefficients.py. log2(1 + t) ~ t + t (t - 1) P(t), t in [0, 1). */
static const float kLog2Poly[4] = {
    -4.419170070e-01f, 2.671791442e-01f, -1.484260681e-01f, 4.514866894e-02f,
};
/* 2^f ~ 1 + f + f (f - 1) Q(f), f in [0, 1). */
static const float kExp2Poly[4] = {
    3.068470199e-01f, 6.669989668e-02f, 1.084460092e-02f, 1.896849487e-03f,
};

#define kLog2Floor 1e-30f
#define kDbPerLog2 6.0205999132796239f  /* 20 log10(2) */
#define kLog2PerDb 0.16609640474436813f /* 1 / kDbPerLog2 */

float dsp_fast_log2f(float x) {
    if (!(x > kLog2Floor)) {
        x = kLog2Floor; /* Also catches NaN. */
    }
    uint32_t bits;
    memcpy(&bits, &x, sizeof(bits));
    const int32_t exponent = (int32_t)((bits >> 23) & 0xFFu) - 127;
    bits = (bits & 0x007FFFFFu) | 0x3F800000u;
    float m;
    memcpy(&m, &bits, sizeof(m));
    const float t = m - 1.0f;
    const float p = kLog2Poly[0] + t * (kLog2Poly[1] + t * (kLog2Poly[2] + t * kLog2Poly[3]));
    return (float)exponent + t + t * (t - 1.0f) * p;
}

float dsp_fast_exp2f(float x) {
    if (!(x >= -126.0f)) {
        x = -126.0f; /* Also catches NaN, whose cast to int would be undefined. */
    } else if (x > 127.0f) {
        x = 127.0f;
    }
    int32_t i = (int32_t)x; /* Truncates towards zero; make it a floor. */
    if ((float)i > x) {
        --i;
    }
    const float f = x - (float)i;
    const float q = kExp2Poly[0] + f * (kExp2Poly[1] + f * (kExp2Poly[2] + f * kExp2Poly[3]));
    const float mantissa = 1.0f + f + f * (f - 1.0f) * q;
    const uint32_t scale_bits = (uint32_t)(i + 127) << 23;
    float scale;
    memcpy(&scale, &scale_bits, sizeof(scale));
    return mantissa * scale;
}

float dsp_fast_lin_to_db(float x) {
    return kDbPerLog2 * dsp_fast_log2f(x < 0.0f ? -x : x);
}

float dsp_fast_db_to_lin(float db) { return dsp_fast_exp2f(db * kLog2PerDb); }
