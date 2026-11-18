/* The true-peak detector shared by the limiter and the meters: a 4x Nyquist interpolator, a
 * 63-tap Kaiser-windowed sinc (beta 4.1) cut at the base rate's Nyquist, from
 * tools/design/tp_detector.py. Phase 0 is the sample itself; phases 1/4, 1/2 and 3/4 are 16 taps
 * each, the 3/4 phase being the 1/4 phase reversed and the 1/2 phase symmetric.
 * Passband flat within +/-0.07 dB to 20 kHz at 48 kHz; under-reads a sine's peak by up to
 * cos(pi f / 4 fs) plus the filter's ripple (0.198 dB measured on the limiter's hostile set).
 *
 * Header-only (static inline) so each user keeps the loop in its own translation unit, as the
 * limiter had it before the meters needed it too; the tables are 96 bytes per user.
 * Latency: the peak returned is the one around the sample kDspTruePeakTaps / 2 = 8 steps back.
 */
#ifndef DSP_TRUEPEAK_H
#define DSP_TRUEPEAK_H

#include <math.h>
#include <stdint.h>

enum { kDspTruePeakTaps = 16 };

/* Index i meets the sample i steps back from the newest. */
static const float kDspTpQuarter[kDspTruePeakTaps] = {
    -2.356659854e-03f, 6.230897736e-03f, -1.268179156e-02f, 2.283323370e-02f,
    -3.870575503e-02f, 6.502874196e-02f, -1.173553094e-01f, 2.951403856e-01f,
    8.986518979e-01f, -1.718815416e-01f, 8.588046581e-02f, -5.004023388e-02f,
    2.986130491e-02f, -1.720060594e-02f, 9.075933136e-03f, -4.025056027e-03f,
};
static const float kDspTpHalf[kDspTruePeakTaps / 2] = {
    -4.425711464e-03f, 1.070061512e-02f, -2.095292322e-02f, 3.698274866e-02f,
    -6.223199144e-02f, 1.053786874e-01f, -1.984295547e-01f, 6.319220662e-01f,
};

/* The true peak around the sample 8 steps back: the largest |value| of the sample itself and the
 * three phases after it, from a history `x` holding the newest 16 samples, newest first. */
static inline float dsp_true_peak16(const float *x) {
    float q1a = 0.0f, q1b = 0.0f, q3a = 0.0f, q3b = 0.0f, h0 = 0.0f, h1 = 0.0f;
    for (int32_t i = 0; i < kDspTruePeakTaps / 2; ++i) {
        const float a = x[i], b = x[kDspTruePeakTaps - 1 - i];
        q1a += kDspTpQuarter[i] * a;
        q1b += kDspTpQuarter[kDspTruePeakTaps - 1 - i] * b;
        q3a += kDspTpQuarter[kDspTruePeakTaps - 1 - i] * a;
        q3b += kDspTpQuarter[i] * b;
        if ((i & 1) == 0) {
            h0 += kDspTpHalf[i] * (a + b);
        } else {
            h1 += kDspTpHalf[i] * (a + b);
        }
    }
    const float p0 = fabsf(x[kDspTruePeakTaps / 2]);
    const float p1 = fabsf(q1a + q1b), p2 = fabsf(h0 + h1), p3 = fabsf(q3a + q3b);
    const float m01 = p0 > p1 ? p0 : p1, m23 = p2 > p3 ? p2 : p3;
    return m01 > m23 ? m01 : m23;
}

#endif
