/* Exercise EX8d: a double-press detector. THE OWNER'S FILE: replace the bodies
 * (docs/exercises/EX8d_doublepress.md; tests in tests/exercises/test_ex8d_doublepress.py).
 *
 * The stub never reports a double press, so the panel behaves as it does without one. */
#include "ctl/ctl_button.h"

void ctl_double_init(CtlDoublePress *d) {
    d->since_ms = 0u;
    d->state = 0u;
}

int ctl_double_update(CtlDoublePress *d, uint32_t events) {
    (void)d;
    (void)events;
    return 0;
}
