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
