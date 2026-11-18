"""Reference models of the panel input (ctl_pot.h, ctl_button.h), written from the design note
(docs/notes/panel_input.md) in float32 with the C's order of operations, so the C must match them
bit for bit. Slow: for short streams only."""
import numpy as np

F = np.float32
RATE_HZ = 1000
AVERAGE = 16
HYSTERESIS = F(0.004)
STEP = F(1.0 / 4096.0)
STILL_MS = 50
REST_WINDOW = F(1.0 / 1024.0)
END_ZONE = F(0.01)
CENTRE_ZONE = F(0.03)
OFF_ZONE = F(0.03)
LINEAR, CENTRE, VOLUME = 0, 1, 2

INTEGRATE = 5
LONG_MS = 600
PRESS, RELEASE, LONG, SHORT = 1, 2, 4, 8


class Pot:
    def __init__(self, adc_bits, coef):
        self.den = F(AVERAGE) * F((1 << adc_bits) - 1)
        self.coef = F(coef)  # From ctl_pot_coef: expf is the C library's, not modelled here.
        self.smooth = self.out = self.window = F(0)
        self.still = 0
        self.started = False
        self.at_rest = False

    def _report(self):
        self.out = self.smooth
        return True

    def update(self, total):
        x = F(F(total) / self.den)
        x = min(max(x, F(0)), F(1))
        if not self.started:
            self.started = True
            self.smooth = self.window = x
            self.still = 0
            return self._report()
        self.smooth = F(self.smooth + F(self.coef * F(x - self.smooth)))
        if abs(F(self.smooth - self.window)) > REST_WINDOW:
            self.window = self.smooth
            self.still = 0
        elif self.still < STILL_MS:
            self.still += 1
        if self.at_rest:
            if abs(F(self.smooth - self.out)) > HYSTERESIS:
                self.at_rest = False
                return self._report()
            return False
        if self.still >= STILL_MS:
            self.at_rest = True
            return False
        if abs(F(self.smooth - self.out)) >= STEP:
            return self._report()
        return False


def _zoned(d, zone, half):
    span = F(F(half - zone) - END_ZONE)
    y = F(F(F(d - zone) / span) * half)
    return min(max(y, F(0)), F(half))


def shape(travel, kind, lo=0.0, centre=0.5, hi=1.0):
    t, lo, c, hi = F(travel), F(lo), F(centre), F(hi)
    if kind == CENTRE:
        if t <= c:
            d = F(F(F(c - t) / F(c - lo)) * F(0.5))
            return F(F(0.5) - _zoned(d, CENTRE_ZONE, F(0.5)))
        d = F(F(F(t - c) / F(hi - c)) * F(0.5))
        return F(F(0.5) + _zoned(d, CENTRE_ZONE, F(0.5)))
    u = F(F(t - lo) / F(hi - lo))
    x = _zoned(u, END_ZONE, F(1))
    if kind == VOLUME and x < OFF_ZONE:
        return F(0)
    return x


class Button:
    def __init__(self):
        self.count = 0
        self.pressed = False
        self.long_sent = False
        self.held_ms = 0

    def update(self, closed):
        if closed:
            self.count = min(self.count + 1, INTEGRATE)
        else:
            self.count = max(self.count - 1, 0)
        if not self.pressed and self.count == INTEGRATE:
            self.pressed, self.long_sent, self.held_ms = True, False, 0
            return PRESS
        if self.pressed and self.count == 0:
            self.pressed = False
            return RELEASE | (0 if self.long_sent else SHORT)
        if self.pressed:
            self.held_ms += 1
            if not self.long_sent and self.held_ms >= LONG_MS:
                self.long_sent = True
                return LONG
        return 0
