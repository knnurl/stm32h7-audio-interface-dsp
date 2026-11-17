# Exercise 8a: 14-bit control change for the tone gains

Batch 8a. Yours to do. Claude reviews it when you ask and does not do it.

## Why this one

A 7-bit control change gives 128 steps: 0.19 dB per step on a +/-12 dB tone gain, enough to hear
as a zipper on a slow sweep from a DAW automation lane before the smoothing hides it. MIDI's
answer is the coarse and fine pair: CC n (0 to 31) carries the most significant 7 bits and
CC n + 32 the least. Getting it right with real controllers, most of which send only the coarse
half, is the kind of protocol edge case an embedded audio job is full of.

## The task

Write `ctl_midi_cc14()` in `ctl/src/ctl_midi_cc14.c`. Its contract is in `ctl/include/ctl/ctl_midi.h`.
It is called for CC 20, 21 and 22 (bass, mid, treble) and for their fine halves 52, 53 and 54. It
returns 1 and the position `*x` (0 to 1) when the gain should be set, 0 when the message only
updates state. `CtlMidi` already has `msb[32]` and `msb_valid[32]` for you; add fields if you
need them, and keep the struct free of pointers to anything but what it has.

The stub there is 7-bit only. Keep the device working at every step: a controller that never
sends the fine half must behave exactly as it does today.

Run `python -m pytest tests/exercises/test_ex8a_cc14.py`, and `python -m pytest` for the rest.

## Done when

All the exercise tests pass, the unit tests still pass, and you can say:

- what a 7-bit-only controller at 127 gives, and why that constrains your mapping;
- what your mapping does at coarse 127 with fine values above 0;
- how many distinct gain values the full 14-bit sweep produces.

## Things to think about

- 64 must be exactly flat for a 7-bit controller (the centred scaling, `ctl_midi7_to_norm`).
  What does that force on the 14-bit mapping, given that coarse alone and coarse with fine 0
  must agree?
- The MIDI specification says a new coarse value without a fine one means fine 0. What does a
  controller that sends the fine half first do to you?
- Running status: the pair often arrives as `B0 14 40 34 7F`. Does anything in your code
  depend on two separate status bytes?
- Would NRPN (CC 99, 98, 6, 38) have been the better route for the other parameters? Note it
  as an open question; do not build it.
