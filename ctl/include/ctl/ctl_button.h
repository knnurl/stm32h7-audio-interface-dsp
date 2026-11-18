/* Panel buttons: debouncing and press events (batch 8d,
 * docs/notes/panel_input.md).
 *
 * Input: the contact sampled once per millisecond (1 = closed; the firmware inverts an
 * active-low pin). An integrator counts up on a closed sample and down on an open one, held
 * between 0 and CTL_BUTTON_INTEGRATE (5, so 5 ms); the button becomes pressed when it reaches
 * the top and released when it reaches 0. Contact bounce shorter than 5 ms never changes the
 * state, and a single-sample glitch (interference) never does. Latency: 5 ms after the contact
 * settles, the same for every press, so tap-tempo intervals are unaffected.
 *
 * Events: kCtlButtonPress and kCtlButtonRelease on the debounced edges; kCtlButtonLong once per
 * hold, CTL_BUTTON_LONG_MS after the press; kCtlButtonShort with the release of a press that
 * never became long.
 *
 * Hardware-free C11, integers only. Main loop only.
 */
#ifndef CTL_BUTTON_H
#define CTL_BUTTON_H

#include <stdint.h>

#define CTL_BUTTON_INTEGRATE 5u
#define CTL_BUTTON_LONG_MS 600u

enum {
    kCtlButtonPress = 1u << 0,
    kCtlButtonRelease = 1u << 1,
    kCtlButtonLong = 1u << 2,
    kCtlButtonShort = 1u << 3,
};

typedef struct {
    uint8_t count;   /* The integrator, 0 to CTL_BUTTON_INTEGRATE. */
    uint8_t pressed; /* Debounced state. */
    uint8_t long_sent;
    uint32_t held_ms; /* Since the debounced press. */
} CtlButton;

void ctl_button_init(CtlButton *b);
/* One sample (1 ms). Returns the events it caused, a mask of kCtlButton*. */
uint32_t ctl_button_update(CtlButton *b, int closed);

/* Exercise EX8d (ctl/src/ctl_button_double.c, the owner's; docs/exercises/EX8d_doublepress.md):
 * a double-press detector fed with one button's events, once per millisecond like the
 * debouncer. Returns 1 at the moment a double press is recognised. The stub never does.
 * Proposed contract, the owner's to change with the tests: two presses whose press events are
 * at most CTL_DOUBLE_WINDOW_MS apart, reported at the second press; the press after a double
 * starts a new pair. */
#define CTL_DOUBLE_WINDOW_MS 300u

typedef struct {
    uint32_t since_ms; /* Free for the owner's design; add fields as needed. */
    uint8_t state;
} CtlDoublePress;

void ctl_double_init(CtlDoublePress *d);
int ctl_double_update(CtlDoublePress *d, uint32_t events);

#endif
