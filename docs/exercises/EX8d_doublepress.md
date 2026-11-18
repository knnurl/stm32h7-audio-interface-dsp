# Exercise 8d: a double-press detector

Batch 8d. Yours to do. Claude reviews it when you ask and does not do it.

## Why this one

The panel has five buttons and a footswitch, and every extra function wants a button. A double
press is the usual way to get a second one out of the same switch, and it is a small state
machine with a real design trade-off in it: the moment you allow a double press on a button, its
single press can no longer act at once, because you cannot know yet whether a second press is
coming. Event timing on a debounced input, a window, and that trade-off are the kind of thing an
embedded audio product's firmware is full of.

## The task

Write `ctl_double_init()` and `ctl_double_update()` in `ctl/src/ctl_button_double.c`. The
contract is in `ctl/include/ctl/ctl_button.h`: the detector is fed one button's events from the
debouncer (`ctl_button_update`, `kCtlButton*` masks) once per millisecond, and returns 1 at the
moment it recognises a double press. `CtlDoublePress` has two fields to start with; add what you
need, no pointers.

The contract in the header and in `tests/exercises/test_ex8d_doublepress.py` is a proposal:
two presses whose press events are at most `CTL_DOUBLE_WINDOW_MS` (300 ms) apart, reported at the
second press; the press after a double starts a new pair. If you design it differently, change
the tests with it and write down why.

The stub never reports. Keep the device working at every step: the "never" tests pass with the
stub and must keep passing.

Run `python -m pytest tests/exercises/test_ex8d_doublepress.py`, and `python -m pytest` for the
rest.

## Done when

All the exercise tests pass, the unit tests still pass, and you can say:

- which button you would give a double press to, what it would do, and what that costs the
  single press on the same button (how late it acts, and whether it can act at once and be
  undone instead);
- why the detector takes the debouncer's events rather than the raw contact;
- what happens to your detector when the millisecond counter it implies wraps, or why it cannot.

## Things to think about

- Press-to-press, release-to-press, or press-to-release: which interval did you measure, and
  what does a slow presser do to each?
- A triple press: one double and a stray single, or one double and nothing? The test says one
  double; is that what you want on, say, the mute button?
- The tap button: tap tempo at 200 BPM is 300 ms between taps. What does that mean for a double
  press on TAP?
