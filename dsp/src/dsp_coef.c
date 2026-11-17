#include "dsp/dsp_coef.h"

#include <math.h>
#include <stdint.h>

#define kPi 3.14159265358979323846

/* Guards for every design: a frequency inside (0, 0.49 fs), a Q of at least 0.01, a shelf slope
 * in [0.05, 1]. Outside those the formulas give division by zero (Q <= 0), negative alpha and
 * an unstable section (f0 >= fs / 2), or the square root of a negative number (a shelf slope
 * above about 1 / (1 - 2 / (A + 1/A)): 5 at +12 dB, 1.9 at +24 dB). Slope 1 is the steepest
 * shelf without overshoot, so nothing useful is lost by stopping there. */
static double clamp(double v, double lo, double hi) { return v < lo ? lo : (v > hi ? hi : v); }
static double safe_f0(double fs_hz, double f0_hz) { return clamp(f0_hz, 1e-6 * fs_hz, 0.49 * fs_hz); }
static double safe_q(double q) { return q != q ? 0.7071 : clamp(q, 0.01, 1000.0); }
static double safe_slope(double s) { return s != s ? 1.0 : clamp(s, 0.05, 1.0); }

static void normalise(DspBiquadCoefsD *out, double b0, double b1, double b2, double a0, double a1,
                      double a2) {
    out->b0 = b0 / a0;
    out->b1 = b1 / a0;
    out->b2 = b2 / a0;
    out->a1 = a1 / a0;
    out->a2 = a2 / a0;
}

void dsp_coef_identity(DspBiquadCoefsD *out) {
    out->b0 = 1.0;
    out->b1 = 0.0;
    out->b2 = 0.0;
    out->a1 = 0.0;
    out->a2 = 0.0;
}

void dsp_coef_peak(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q, double gain_db) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    q = safe_q(q);
    const double a = pow(10.0, gain_db / 40.0);
    const double w0 = 2.0 * kPi * f0_hz / fs_hz;
    const double cw = cos(w0);
    const double alpha = sin(w0) / (2.0 * q);
    normalise(out, 1.0 + alpha * a, -2.0 * cw, 1.0 - alpha * a, 1.0 + alpha / a, -2.0 * cw,
              1.0 - alpha / a);
}

static double shelf_alpha(double w0, double a, double slope) {
    return sin(w0) / 2.0 * sqrt((a + 1.0 / a) * (1.0 / slope - 1.0) + 2.0);
}

void dsp_coef_low_shelf(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double slope,
                        double gain_db) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    slope = safe_slope(slope);
    const double a = pow(10.0, gain_db / 40.0);
    const double w0 = 2.0 * kPi * f0_hz / fs_hz;
    const double cw = cos(w0);
    const double k = 2.0 * sqrt(a) * shelf_alpha(w0, a, slope);
    normalise(out, a * ((a + 1.0) - (a - 1.0) * cw + k), 2.0 * a * ((a - 1.0) - (a + 1.0) * cw),
              a * ((a + 1.0) - (a - 1.0) * cw - k), (a + 1.0) + (a - 1.0) * cw + k,
              -2.0 * ((a - 1.0) + (a + 1.0) * cw), (a + 1.0) + (a - 1.0) * cw - k);
}

void dsp_coef_high_shelf(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double slope,
                         double gain_db) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    slope = safe_slope(slope);
    const double a = pow(10.0, gain_db / 40.0);
    const double w0 = 2.0 * kPi * f0_hz / fs_hz;
    const double cw = cos(w0);
    const double k = 2.0 * sqrt(a) * shelf_alpha(w0, a, slope);
    normalise(out, a * ((a + 1.0) + (a - 1.0) * cw + k), -2.0 * a * ((a - 1.0) + (a + 1.0) * cw),
              a * ((a + 1.0) + (a - 1.0) * cw - k), (a + 1.0) - (a - 1.0) * cw + k,
              2.0 * ((a - 1.0) - (a + 1.0) * cw), (a + 1.0) - (a - 1.0) * cw - k);
}

void dsp_coef_lowpass(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    q = safe_q(q);
    const double w0 = 2.0 * kPi * f0_hz / fs_hz;
    const double cw = cos(w0);
    const double alpha = sin(w0) / (2.0 * q);
    normalise(out, (1.0 - cw) / 2.0, 1.0 - cw, (1.0 - cw) / 2.0, 1.0 + alpha, -2.0 * cw,
              1.0 - alpha);
}

void dsp_coef_highpass(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    q = safe_q(q);
    const double w0 = 2.0 * kPi * f0_hz / fs_hz;
    const double cw = cos(w0);
    const double alpha = sin(w0) / (2.0 * q);
    normalise(out, (1.0 + cw) / 2.0, -(1.0 + cw), (1.0 + cw) / 2.0, 1.0 + alpha, -2.0 * cw,
              1.0 - alpha);
}

void dsp_coef_lowpass1(DspBiquadCoefsD *out, double fs_hz, double f0_hz) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    const double k = tan(kPi * f0_hz / fs_hz);
    out->b0 = k / (1.0 + k);
    out->b1 = out->b0;
    out->b2 = 0.0;
    out->a1 = (k - 1.0) / (k + 1.0);
    out->a2 = 0.0;
}

void dsp_coef_highpass1(DspBiquadCoefsD *out, double fs_hz, double f0_hz) {
    f0_hz = safe_f0(fs_hz, f0_hz);
    const double k = tan(kPi * f0_hz / fs_hz);
    out->b0 = 1.0 / (1.0 + k);
    out->b1 = -out->b0;
    out->b2 = 0.0;
    out->a1 = (k - 1.0) / (k + 1.0);
    out->a2 = 0.0;
}

size_t dsp_coef_butterworth(DspBiquadCoefsD *out, size_t capacity, double fs_hz, double fc_hz,
                            int order, int highpass) {
    if (order < 1 || order > 8) {
        return 0;
    }
    const size_t n_sections = (size_t)(order + 1) / 2;
    if (capacity < n_sections) {
        return 0;
    }
    size_t s = 0;
    if (order % 2 == 1) {
        if (highpass) {
            dsp_coef_highpass1(&out[s++], fs_hz, fc_hz);
        } else {
            dsp_coef_lowpass1(&out[s++], fs_hz, fc_hz);
        }
    }
    /* Pole pairs, lowest Q first: Q = 1 / (2 sin((2k - 1) pi / (2 n))), k = n/2 down to 1. */
    for (int k = order / 2; k >= 1; --k) {
        const double q = 1.0 / (2.0 * sin((2.0 * k - 1.0) * kPi / (2.0 * order)));
        if (highpass) {
            dsp_coef_highpass(&out[s++], fs_hz, fc_hz, q);
        } else {
            dsp_coef_lowpass(&out[s++], fs_hz, fc_hz, q);
        }
    }
    return n_sections;
}

double dsp_coef_magnitude_db(const DspBiquadCoefsD *sections, size_t n_sections, double fs_hz,
                             double f_hz) {
    const double w = 2.0 * kPi * f_hz / fs_hz;
    const double c1 = cos(w), s1 = sin(w), c2 = cos(2.0 * w), s2 = sin(2.0 * w);
    double db = 0.0;
    for (size_t i = 0; i < n_sections; ++i) {
        const DspBiquadCoefsD *c = &sections[i];
        const double nr = c->b0 + c->b1 * c1 + c->b2 * c2;
        const double ni = -(c->b1 * s1 + c->b2 * s2);
        const double dr = 1.0 + c->a1 * c1 + c->a2 * c2;
        const double di = -(c->a1 * s1 + c->a2 * s2);
        db += 10.0 * log10((nr * nr + ni * ni) / (dr * dr + di * di));
    }
    return db;
}

void dsp_coef_to_f32(const DspBiquadCoefsD *in, DspBiquadCoefsF32 *out) {
    out->b0 = (float)in->b0;
    out->b1 = (float)in->b1;
    out->b2 = (float)in->b2;
    out->a1 = (float)in->a1;
    out->a2 = (float)in->a2;
}

int dsp_coef_is_stable(double a1, double a2) {
    /* Both poles inside the unit circle: the stability triangle. */
    return a2 < 1.0 && a2 > -1.0 && a1 < 1.0 + a2 && -a1 < 1.0 + a2;
}

int dsp_coef_f32_is_stable(const DspBiquadCoefsF32 *c) {
    return dsp_coef_is_stable((double)c->a1, (double)c->a2);
}

int dsp_coef_to_q31(const DspBiquadCoefsD *in, DspBiquadCoefsQ31 *out, double *max_error) {
    const double values[5] = {in->b0, in->b1, in->b2, in->a1, in->a2};
    for (int i = 0; i < 5; ++i) {
        if (!isfinite(values[i])) {
            return -1; /* llround of NaN or infinity is undefined. */
        }
    }
    /* Bound on the accumulator: |acc| <= sum |C| x 2^31 + err, with err < 2^30. With
     * sum |C| <= 2^32 - 1 that is at most 2^63 - 2^31 + 2^30 - 1, inside int64. */
    const int64_t sum_limit = ((int64_t)1 << 32) - 1;
    for (int shift = 0; shift <= 7; ++shift) {
        const double scale = ldexp(1.0, 30 - shift);
        int64_t q[5];
        int64_t sum = 0;
        int fits = 1;
        for (int i = 0; i < 5; ++i) {
            q[i] = llround(values[i] * scale);
            if (q[i] > INT32_MAX || q[i] < INT32_MIN) {
                fits = 0;
                break;
            }
            sum += q[i] < 0 ? -q[i] : q[i];
        }
        if (!fits || sum > sum_limit) {
            continue;
        }
        if (!dsp_coef_is_stable((double)q[3] / scale, (double)q[4] / scale)) {
            return -1; /* Quantisation moved a pole onto or outside the unit circle. */
        }
        out->b0 = (int32_t)q[0];
        out->b1 = (int32_t)q[1];
        out->b2 = (int32_t)q[2];
        out->a1 = (int32_t)q[3];
        out->a2 = (int32_t)q[4];
        out->shift = shift;
        if (max_error != NULL) {
            double worst = 0.0;
            for (int i = 0; i < 5; ++i) {
                const double e = fabs((double)q[i] / scale - values[i]);
                worst = e > worst ? e : worst;
            }
            *max_error = worst;
        }
        return shift;
    }
    return -1;
}

/* EXERCISE EX3: replace these two with the cookbook's notch and all-pass. */
void dsp_coef_notch(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q) {
    (void)fs_hz;
    (void)f0_hz;
    (void)q;
    dsp_coef_identity(out);
}

void dsp_coef_allpass(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q) {
    (void)fs_hz;
    (void)f0_hz;
    (void)q;
    dsp_coef_identity(out);
}
