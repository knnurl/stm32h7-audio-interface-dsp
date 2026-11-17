/* Exercise EX8a: 14-bit control change for the tone gains. THE OWNER'S FILE: replace the body
 * (docs/exercises/EX8a_cc14.md; tests in tests/exercises/test_ex8a_cc14.py).
 *
 * This stub is 7-bit only: the coarse CC sets the value, the fine CC (32 to 63) is ignored. It
 * keeps the device working until the exercise is done. */
#include "ctl/ctl_midi.h"

int ctl_midi_cc14(CtlMidi *m, uint8_t cc, uint8_t value, float *x) {
    (void)m;
    if (cc >= 32u) {
        return 0;
    }
    *x = ctl_midi7_to_norm(value);
    return 1;
}
