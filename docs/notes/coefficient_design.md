# Design note: coefficient design and quantisation

Batch 3. `dsp/src/dsp_coef.c`.

## Purpose

Turn "a peak at 1 kHz, +6 dB, Q 1" into five numbers, in double precision, and quantise them
for whichever kernel will run them.

## The maths

All designs are the RBJ "Audio EQ cookbook": an analogue prototype mapped to z by the bilinear
transform, with the frequency prewarped so that f0 lands exactly. Peaks reach their gain at f0
exactly (tested to 1e-9 dB). Shelves reach their gain at DC or Nyquist and half of it, in dB, at
f0. Butterworth filters of order n are cascades of second-order sections with
Q = 1 / (2 sin((2k - 1) pi / (2n))), plus a first-order section when n is odd, lowest Q first.

## Choices and what was rejected

- **Double precision, in control code only.** Design runs when a parameter changes, never per
  sample. The M7 has hardware double precision. The tone control is the one block that redesigns
  per block while a knob moves; its cost is to be measured on the board.
- **Lowest Q first in Butterworth cascades.** The high-Q section has the resonant peak in its
  impulse response; putting it last keeps the intermediate signal smaller.
- **Quantisation separate from design.** `dsp_coef_to_f32` and `dsp_coef_to_q31` take a double
  design. The Q31 one picks the smallest shift that keeps every coefficient in range and the
  accumulator safe (`docs/notes/biquad.md`) and reports the largest coefficient error.
- **Rejected for now: a matched (Vicanek) design** that removes cramping. It is a stretch item;
  the numbers below say when it would matter.

## Numerical behaviour: cramping

The bilinear transform squeezes the whole analogue frequency axis into 0 to fs/2, so a peak near
Nyquist comes out narrower and falls faster above f0 than its analogue prototype.
`docs/results/b3_cramping.md` (`python tools/studies/b3_cramping.py`), a +12 dB peak with Q 1:

| fs | f0 | at f0 / 2 | at f0 | at 1.2 f0 |
|---|---|---|---|---|
| 48 kHz | 5 kHz | -0.21 dB | 0.00 | -0.26 dB |
| 48 kHz | 10 kHz | -0.85 dB | 0.00 | -1.29 dB |
| 48 kHz | 15 kHz | -1.92 dB | 0.00 | -4.25 dB |
| 96 kHz | 15 kHz | -0.47 dB | 0.00 | -0.64 dB |

The device runs at 96 kHz where it can, which cuts the error about four times. The tone
control's treble shelf at 10 kHz is a shelf, whose high-frequency gain is set at Nyquist, so it
reaches its full gain regardless.

## Test evidence

`tests/unit/test_coef.py`: every design against an independent Python implementation of the
formulas (1e-12 relative); the gain at f0, the shelf gains at DC and Nyquist, the Butterworth
-3.01 dB point and passband; the Q31 quantiser against the Python rule on 200 random designs.

## Open questions

- Whether the cramping of the speaker-stage PEQ at 48 kHz (the USB rates on rev A) is worth a
  matched design. Above 10 kHz it is; whether anyone will set a peak there is another question.

## From the transcripts

Read in full on 2026-11-17: Biquad Filters (#172), Audio EQ Software Implementation (#89),
Bilinear Transform IIR Filter Design, IIR Filters (#32), Real-Time Software Implementation of
Analog Filters (#20), Notch Filters (#49), All-Pass Filter (#162). Every formula in
`dsp_coef.c` was rechecked by hand against the cookbook at the same time: all correct.

**Agrees**
- #172: compute the cookbook equations in code when a parameter changes, "not every single
  sample", because the trigonometry is expensive.
- #89 and the bilinear transform video: Tustin with prewarping gives the best frequency match,
  and prewarping is exact only at DC and at the chosen frequency. Our cramping study measures
  what is left everywhere else.
- The bilinear transform video: a stable analogue prototype maps to a stable digital filter.

**Differs, and why**
- #89 derives its peak from an analogue prototype with a linear gain G and Q = fc / bandwidth at
  the -3 dB points, using the unprewarped fc ("fairly rough"). The cookbook uses A = 10^(dB/40)
  and its own Q definition, so a Q value from his EQ is not the same filter here. We keep the
  cookbook: exact gain at f0, prewarped, well documented.
- The videos name the coefficients differently: #89 calls the numerator "a"; #32 writes the
  feedback terms with a plus sign; #172 warns that calculators "flip them around". Our headers
  state H(z) explicitly, which is the defence.

**Suggested and not done, until this pass**
- #89: keep the "centre frequency away from 0 Hz and away from the Nyquist limit". #162: the
  cutoff must be below Nyquist, "this isn't implemented here". Neither was implemented here
  either. Fixed: every design now clamps f0 to (0, 0.49 fs) and Q to at least 0.01, so an
  out-of-range setting gives the nearest valid filter (`test_bad_frequency_and_q_give_a_stable_section`).
- Found in the same review, not in a transcript: a shelf slope above about 1.9 to 5 (depending
  on gain) takes the square root of a negative number, and the PEQ passed its band Q straight
  through as the slope. A NaN coefficient would have poisoned the PEQ's state for good. Fixed:
  the slope is clamped to [0.05, 1] (`test_shelf_slope_never_gives_nan`,
  `test_shelf_slope_above_one_stays_finite`).
- `dsp_coef_to_q31` now refuses non-finite input, where `llround` is undefined.

**For exercise 3:** #49 and #162 give design methods for a notch and an all-pass from analogue
prototypes, parameterised by a bandwidth in hertz rather than a Q, so the -3 dB definition
matters when you compare. The exercise is yours; the transcripts are fair to read.
