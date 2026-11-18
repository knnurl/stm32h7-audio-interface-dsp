/* Panel buttons: the integrating debouncer and press events (ctl_button.h). */
#include "ctl/ctl_button.h"

void ctl_button_init(CtlButton *b) {
    b->count = 0u;
    b->pressed = 0u;
    b->long_sent = 0u;
    b->held_ms = 0u;
}

uint32_t ctl_button_update(CtlButton *b, int closed) {
    uint32_t events = 0u;
    if (closed != 0) {
        if (b->count < CTL_BUTTON_INTEGRATE) {
            ++b->count;
        }
    } else if (b->count > 0u) {
        --b->count;
    }

    if (b->pressed == 0u && b->count == CTL_BUTTON_INTEGRATE) {
        b->pressed = 1u;
        b->long_sent = 0u;
        b->held_ms = 0u;
        return kCtlButtonPress;
    }
    if (b->pressed != 0u && b->count == 0u) {
        b->pressed = 0u;
        events = kCtlButtonRelease;
        if (b->long_sent == 0u) {
            events |= kCtlButtonShort;
        }
        return events;
    }
    if (b->pressed != 0u) {
        if (b->held_ms < 0xFFFFFFFFu) {
            ++b->held_ms;
        }
        if (b->long_sent == 0u && b->held_ms >= CTL_BUTTON_LONG_MS) {
            b->long_sent = 1u;
            events = kCtlButtonLong;
        }
    }
    return events;
}
