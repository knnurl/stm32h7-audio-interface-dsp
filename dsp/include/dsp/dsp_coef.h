/* Biquad coefficient design, in double precision.
 *
 * Peaking and shelving filters, second-order low-pass and high-pass: the RBJ "Audio EQ
 * cookbook" formulas (bilinear transform with the frequency prewarped at f0). Butterworth
 * low-pass and high-pass of order 1 to 8 as cascades. All results are normalised (a0 = 1) and
 * use the sign convention H(z) = (b0 + b1 z^-1 + b2 z^-2) / (1 + a1 z^-1 + a2 z^-2).
 *
 * Bilinear designs "cramp" near Nyquist: a peak at 15 kHz at 48 kHz is narrower and its gain
 * at higher frequencies falls faster than the analogue prototype's. docs/results/b3_cramping.md
 * measures it.
 *
 * These run in init and control code, never per sample. On the M7 double precision is in
 * hardware.
 */
#ifndef DSP_COEF_H
#define DSP_COEF_H

#include "dsp/dsp_biquad.h"

#include <stddef.h>

typedef struct {
    double b0, b1, b2, a1, a2;
} DspBiquadCoefsD;

void dsp_coef_identity(DspBiquadCoefsD *out);
void dsp_coef_peak(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q, double gain_db);
/* Shelves take the cookbook's slope S (1 = the steepest without overshoot). */
void dsp_coef_low_shelf(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double slope,
                        double gain_db);
void dsp_coef_high_shelf(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double slope,
                         double gain_db);
void dsp_coef_lowpass(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q);
void dsp_coef_highpass(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q);
/* First-order sections, as biquads with b2 = a2 = 0. */
void dsp_coef_lowpass1(DspBiquadCoefsD *out, double fs_hz, double f0_hz);
void dsp_coef_highpass1(DspBiquadCoefsD *out, double fs_hz, double f0_hz);

/* Butterworth of order 1 to 8: writes (order + 1) / 2 sections, lowest Q first, and returns
 * the count, or 0 when the order is out of range or `capacity` is too small. -3 dB at fc. */
size_t dsp_coef_butterworth(DspBiquadCoefsD *out, size_t capacity, double fs_hz, double fc_hz,
                            int order, int highpass);

/* |H| of a cascade at frequency f, in dB. */
double dsp_coef_magnitude_db(const DspBiquadCoefsD *sections, size_t n_sections, double fs_hz,
                             double f_hz);

void dsp_coef_to_f32(const DspBiquadCoefsD *in, DspBiquadCoefsF32 *out);
/* Quantises to the Q31 section format of dsp_biquad.h, with the smallest shift (0 to 7) for
 * which every coefficient fits and the accumulator cannot overflow. Returns the shift, or -1
 * when none fits. `max_error` (may be NULL) receives the largest coefficient error. */
int dsp_coef_to_q31(const DspBiquadCoefsD *in, DspBiquadCoefsQ31 *out, double *max_error);

/* EXERCISE EX3 (docs/exercises/EX3_notch_allpass.md): written by the owner. Until then both
 * return the identity. */
void dsp_coef_notch(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q);
void dsp_coef_allpass(DspBiquadCoefsD *out, double fs_hz, double f0_hz, double q);

#endif
