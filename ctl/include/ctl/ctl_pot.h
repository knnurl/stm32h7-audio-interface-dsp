/* One panel potentiometer, from ADC readings to a knob position (batch 8d,
 * docs/notes/panel_input.md).
 *
 * Input: one reading per millisecond (CTL_POT_RATE_HZ), the sum of CTL_POT_AVERAGE ADC
 * conversions (the H7's hardware oversampler gives the sum directly [Verify on the board]).
 * Pipeline:
 * 1. Average: the sum over its full scale gives the travel, 0 to 1.
 * 2. One-pole smoother, time constant tau_ms (CTL_POT_TAU_MS by default).
 * 3. Rest detection with hysteresis. While the knob moves, the position follows the smoothed
 *    travel in steps of at least CTL_POT_STEP (1/4096 of travel: 12 bits). When the smoothed
 *    travel has stayed within +/- CTL_POT_REST_WINDOW (1/1024) for CTL_POT_STILL_MS, the knob
 *    is at rest: the position is held and nothing is reported until the travel leaves the held
 *    point by more than the hysteresis (CTL_POT_HYSTERESIS, 0.4 % of travel). So a knob at
 *    rest sends nothing while its smoothed reading noise stays inside the hysteresis, and a
 *    moving knob still resolves 12 bits. A crawl slower than the rest window per still time
 *    (about 2 % of travel per second) moves in hysteresis steps instead.
 * 4. Shape (ctl_pot_shape): the per-unit calibration and the curve kind: end zones, the tone
 *    knobs' centre zone, the volume knobs' off zone. The registry's own curve then maps the
 *    shaped position onto the parameter (ctl_param_from_norm).
 *
 * Latency: the smoother's; a step of travel reaches 63 % in tau_ms, and the first report of a
 * movement follows the first reading that moves the smoothed travel by more than the hysteresis
 * (at rest) or one step (moving).
 *
 * Hardware-free C11: no allocation, no stdio. Floats only, so the PC and the M7 give
 * bit-identical results (-ffp-contract=off). Main loop only.
 */
#ifndef CTL_POT_H
#define CTL_POT_H

#include <stdint.h>

#define CTL_POT_RATE_HZ 1000u
#define CTL_POT_AVERAGE 16u
#define CTL_POT_TAU_MS 4.0f
#define CTL_POT_HYSTERESIS 0.004f
#define CTL_POT_STEP (1.0f / 4096.0f)
#define CTL_POT_STILL_MS 50u
#define CTL_POT_REST_WINDOW (1.0f / 1024.0f)

typedef enum {
    kCtlPotLinear = 0, /* FX amount, blend: end zones only. */
    kCtlPotCentre = 1, /* Tone gains: a centre zone that is exactly the middle (0 dB). */
    kCtlPotVolume = 2, /* Monitor and phones: the bottom CTL_POT_OFF_ZONE of travel is off. */
} CtlPotKind;

/* Proposed for the owner (docs/notes/panel_input.md). */
#define CTL_POT_END_ZONE 0.01f    /* Each end: so a pot short of its rail still reaches it. */
#define CTL_POT_CENTRE_ZONE 0.03f /* Either side of the centre, for the tone gains. */
#define CTL_POT_OFF_ZONE 0.03f    /* Bottom of travel, for the volumes. */

/* A unit's measured travel: the readings at its two end stops and at its centre detent. The
 * default (ctl_pot_cal_default) is the ideal pot; batch 7 measures three pots and decides
 * whether each unit needs its own [Verify]. */
typedef struct {
    float lo;
    float centre;
    float hi;
} CtlPotCal;

typedef struct {
    float scale_den; /* Full scale of one reading: CTL_POT_AVERAGE * (2^bits - 1). */
    float coef;      /* The smoother's: 1 - exp(-1 / (tau_ms * rate)). */
    float smooth;    /* Smoothed travel, 0 to 1. */
    float out;       /* Travel last reported. */
    float window;    /* Centre of the rest window. */
    uint32_t still;  /* Readings the travel has stayed inside the rest window. */
    uint8_t started;
    uint8_t at_rest;
    uint32_t reports;
} CtlPot;

/* The smoother's coefficient for a time constant at CTL_POT_RATE_HZ (exported so the Python
 * reference model uses the same float). */
float ctl_pot_coef(float tau_ms);
void ctl_pot_init(CtlPot *pot, uint32_t adc_bits, float tau_ms);
/* One reading: the sum of CTL_POT_AVERAGE conversions. Returns 1 when the travel to report
 * changed (always on the first reading), with it in *travel (0 to 1, before shaping). */
int ctl_pot_update(CtlPot *pot, uint32_t sum, float *travel);

void ctl_pot_cal_default(CtlPotCal *cal);
/* Travel to the knob position handed to ctl_core_knob, 0 to 1. */
float ctl_pot_shape(const CtlPotCal *cal, CtlPotKind kind, float travel);

#endif
