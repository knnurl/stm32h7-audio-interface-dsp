/* Panel buttons and the footswitch: debouncing and press events (batch 8d,
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

#endif
