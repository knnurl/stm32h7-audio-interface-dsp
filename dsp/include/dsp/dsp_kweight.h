/* The K-weighting filter of ITU-R BS.1770-4: the loudness meter's frequency weighting.
 * THE OWNER'S EXERCISE (docs/exercises/EX8c_kweighting.md): this header is the specification;
 * dsp/src/dsp_kweight.c is a stub until he writes it, and tests/exercises/test_ex8c_kweight.py
 * fails until then.
 *
 * Two sections, in this order:
 *   sections[0]: the pre-filter, a high shelf of about +4 dB above about 1.5 kHz (the head's
 *                acoustic effect);
 *   sections[1]: the RLB weighting, a second-order high-pass at about 38 Hz.
 * Normalised (a0 = 1), the sign convention of dsp_biquad.h (y = b0 x + b1 x1 + b2 x2 - a1 y1 -
 * a2 y2).
 * At 48 kHz the coefficients equal the ones BS.1770-4 publishes (its tables 1 and 2). At any
 * other rate from 32 kHz to 192 kHz they are re-derived, so the response matches the 48 kHz
 * filter's within 0.05 dB from 20 Hz to 20 kHz; the standard gives no other rate.
 *
 * Returns 0, or -1 for a rate outside 32 to 192 kHz (sections untouched) or while the stub is in
 * place (sections set to pass-through). Control level only: it may use the C library's maths.
 */
#ifndef DSP_KWEIGHT_H
#define DSP_KWEIGHT_H

#include "dsp/dsp_biquad.h"

#include <stdint.h>

int32_t dsp_kweight_design(double sample_rate_hz, DspBiquadCoefsF64 sections[2]);

#endif
