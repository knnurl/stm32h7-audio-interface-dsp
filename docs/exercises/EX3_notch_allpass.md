# Exercise 3: a notch and an all-pass

Batch 3. Yours to write. Claude reviews it when you ask and does not write it.

## Why these two

A notch removes one frequency and leaves the rest alone: hum, a feedback ring, a room mode. An
all-pass leaves every level alone and changes only the phase: it is the building block of the
phaser in batch 8b and of crossover alignment. Both are a few lines in the cookbook family you
now have in `dsp/src/dsp_coef.c`, and both have exact properties a test can check.

## The task

In `dsp/src/dsp_coef.c`, replace the two stubs `dsp_coef_notch` and `dsp_coef_allpass` (they
return the identity now). Same conventions as the other designs: double precision, normalised to
a0 = 1, H(z) = (b0 + b1 z^-1 + b2 z^-2) / (1 + a1 z^-1 + a2 z^-2).

## Done when

```
cmake --build --preset host-release
python -m pytest tests/exercises/test_ex3_notch_allpass.py
```

passes. The tests check properties, not formulas:

| Test | What it checks |
|---|---|
| `test_notch` | Below -100 dB at f0; flat far below and far above; -3 dB points about f0 / Q apart |
| `test_allpass` | 0 dB at every frequency (to 1e-9 dB); -180 degrees at f0; 0 degrees at DC |
| `test_both_are_stable` | Poles inside the unit circle |

(`test_both_are_stable` already passes on the identity stubs. The others fail.)

## Second part, on the board

Write a variant of `dsp_biquad_f32_section` that filters two channels in one loop, sharing the
coefficient loads. Measure both with `bench` and beat the single-channel version's cycles per
sample per channel. Say why it is faster, or why it is not.

## Things to think about

- Where are the notch's zeros, and why does that make its depth infinite in theory? What limits
  it in float32?
- The all-pass's numerator is its denominator reversed. Why does that give |H| = 1?
- What happens to the all-pass's phase at f0 as Q goes up, and what does that do to a phaser?
