# Exercise 6: design a half-band filter and prove it in the C oversampler

Batch 6. Yours to do. Claude reviews it when you ask and does not do it.

## Why this one

The built-in 2x filter has 83 taps and 113 dB of stopband: more than the saturation needs, and
42 multiply-adds per sample each way. Designing a cheaper one to a stated specification, then
proving it in the real code, is the everyday filter job of an embedded DSP engineer.

## The task

1. Design, in Python, a half-band low-pass for the first 2x stage at a 48 kHz base rate (96 kHz
   high rate) that meets:
   - passband flat to 18 kHz within 0.01 dB;
   - stopband at least 90 dB down from 30 kHz;
   - length 4K + 3, as few taps as you can manage.
   `tools/design/b6_coefficients.py` shows one way; you may use another.
2. Write its taps, one per line, to `tools/design/ex6_halfband.txt`.
3. Run `python -m pytest tests/exercises/test_ex6_halfband.py`. The tests load your file, build
   the C up and down stages with `dsp_halfband_up_init` and `dsp_halfband_down_init`, and measure
   what the C code actually does: passband flatness, image rejection of a tone, alias rejection
   on the way down, and the round-trip latency the length implies.

## Done when

All tests pass, and you can say how many multiply-adds per sample your filter saves against the
built-in one, and what that buys at 96 kHz on a 400 MHz M7 (the budget is 4166 cycles per
sample).

## Things to think about

- Why is the centre tap exactly 0.5, and why must every other even-offset tap be zero?
- What does the length 4K + 3 (rather than 4K + 1) guarantee about the centre tap's index?
- Your stopband starts at 30 kHz. What does that let through on the way down, and can anyone
  hear it?
