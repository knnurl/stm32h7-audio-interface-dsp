# Design note: float32 for the upper PEQ bands (budget option D)

Owner's decision, 2026-11-18 ("A + C + D"). Code: `dsp/include/dsp/dsp_peq.h`. Study:
`docs/results/peq_f32_noise.md` (`python tools/studies/peq_f32_noise.py`). Self-test case:
`peq_f32`.

## Why

Every PEQ section ran with double state (`biquad.md`, decision of 2026-11-17), because float32
state loses 40 to 90 dB at low corner frequencies. On the M7 a double section costs about 56
cycles per sample and a float32 one about 17 (`biquad_f64` 169 and `biquad_f32` 51 for three
sections, `bench_target.md`). The 48 kHz worst case runs six PEQ channels (two strips, speaker
left and right, headphone left and right), each with five sections. The M7 was about 1050 cycles
per frame over its ceiling after the 8c split.

`biquad.md` already named the fallback: double only for the low sections. That saves nothing in
the worst case unless the high bands are kept high, because the worst case lets every band sit
low. So the change has two halves: bands 3 and 4 run in float32, and the registry keeps them at
or above a corner where float32 is good enough.

## How good float32 is, by corner frequency

Criterion: at least 110 dB of arithmetic SNR (the noise the float32 state adds, against float64
with the same rounded coefficients), and the rounded coefficients' response within 0.01 dB of
the double design. 110 dB sits just under the PCM3168A DAC's 112 dB dynamic range [Verify].
Worst over peak Q 0.1 to 10, shelf slope 0.1 to 1 and gain -15 to +15 dB; the worst setting is
always the peak at Q 10 and +15 dB.

| Corner | 48 kHz, one section | 96 kHz, one section | 48 kHz, band 3 peak and band 4 shelf |
|---|---|---|---|
| 1 kHz | 103.8 dB | 94.8 dB | |
| 2 kHz | 113.7 dB | 103.7 dB | 110.4 dB on the kernel, 109.6 dB through the PEQ |
| 2.5 kHz | 116.5 dB | 106.9 dB | 113.9 dB |
| 3 kHz | 118.4 dB | 109.6 dB | 116.2 dB |
| 5 kHz | 125.0 dB | 116.1 dB | |

Response error from rounding the coefficients: at most 0.00007 dB at 48 kHz from 2 kHz up, 0.0004 dB
at 96 kHz.

The noise follows the corner relative to the sample rate: a pole pair at f0 with Q 10 sits
closer to z = 1 as f0 / fs falls, and the state's rounding is amplified by about the peak's gain
over the band. That is why 96 kHz needs about twice the corner.

## The change

- **Bands 3 and 4 (a peak and a high shelf in the registry) run in float32 when the sample rate
  is 48 kHz or less.** Their coefficients still ramp in double and are rounded to float each
  block, so a change ramps as smoothly as before. At 96 kHz every section stays double: rev B's
  budget is judged separately.
- **The corner is 2.5 kHz, not 2 kHz.** At 2 kHz one section passes (113.7 dB), but the pair
  that the registry can actually set, band 3's worst peak with band 4's worst shelf at the same
  corner, gives 109.6 dB through the PEQ. 2.5 kHz gives 113.9 dB.
- **The registry's range for bands 3 and 4 of every PEQ is now 2.5 kHz to 20 kHz** (strips,
  speaker, headphones; bands 1 and 2 keep 20 Hz to 20 kHz). `dsp_peq` also raises a float32 band
  set lower to 2.5 kHz, so a caller that bypasses the registry cannot reach the noisy corners.
- **Not changed:** the tone control (its treble shelf, 3 to 16 kHz, would also qualify at
  48 kHz: about 78 cycles per frame more, not done), and the high-pass and bands 1 and 2.

## What it costs and saves

Two sections per PEQ channel, six channels, 56.4 - 17 = about 39 cycles each: about **470 cycles
per frame** at 48 kHz in the worst case, estimated from the section costs. The `peq_f32` self-test
case measures one whole PEQ on the board; the estimate is about 3 x 56.4 + 2 x 17 + overhead =
about 205 cycles per sample against 282 before [measure with `target_test`].

The cost to the user: bands 3 and 4 can no longer go below 2.5 kHz, so two bells below 2.5 kHz
need bands 1 and 2 (band 1 is a low shelf, so in practice one bell below 2.5 kHz). Two peaks
stacked at 2.5 kHz, Q 10, +15 dB each, would give 109.7 dB, but the registry's fixed band types
(band 4 is always a shelf) cannot ask for that. If band types ever become selectable, the
corner needs to rise to 3 kHz.

## Proposed: a 100 dB criterion (awaiting the owner's go)

The owner thinks 100 dB is enough (2026-11-18); Claude agrees. Measured 2026-11-19 with
`pair_snr` from `tools/studies/peq_f32_noise.py` (the registry's band 3 peak at Q 10, +15 dB
and band 4 shelf at the same corner, worst over the shelf settings), at each input level
separately:

| Corner (48 kHz) | Pair SNR at -1 dBFS | Pair SNR at -60 dBFS |
|---|---|---|
| 800 Hz | 96.5 dB | 96.7 dB |
| 1.0 kHz | 99.2 dB | 99.9 dB |
| 1.2 kHz | 102.1 dB | 102.2 dB |
| 1.5 kHz | 105.8 dB | 105.7 dB |
| 2.0 kHz | 110.4 dB | 110.7 dB |

- **Why 110 dB was too strict:** it was set against the DAC's 112 dB dynamic range, a fixed
  noise floor measured with a -60 dBFS signal. Float32 rounding error is relative to the
  signal: the table shows the same SNR at both levels. At -60 dBFS the error sits near
  -160 dBFS, far under the floor; the dynamic range is untouched.
- **The right comparison is the converter's THD+N at full scale:** -94 dB for the DAC, -93 dB
  for the ADC (SBAS452A, Electrical Characteristics). An error 102 dB down adds to -94 dB as
  about -93.4 dB: at most 0.6 dB worse, and only at the worst setting at full scale.
- **What 100 dB gives:** the lowest passing corner is **1.2 kHz**, not the "about 1 kHz" first
  quoted (1 kHz gives 99.2 dB, 0.8 dB short). Bands 3 and 4 would reach 1.2 to 2.5 kHz, the
  presence region they cannot reach today. No cycle cost: the float32 saving is unchanged.
- **On the owner's go:** set `DSP_PEQ_F32_MIN_HZ` and the registry's lower limit for bands 3 and
  4 to 1.2 kHz; add the 1.0 to 2.0 kHz pair rows to the study and `docs/results/peq_f32_noise.md`;
  update this note and the SPEC decision log; rerun the host tests and the board's `peq_f32`
  case (bit identity).

## From the transcripts

Read: #172 (Biquad Filters), #89 (Audio EQ Software Implementation), #32 (IIR Filters, Theory
and Implementation).

- **#172:** Phil says that whatever the form, at very low frequencies and at high sample rates it
  can pay to use double instead of single precision, because poles near the unit circle make
  the filter sensitive to rounding, and that single precision is often enough otherwise. Taken:
  exactly that split, with the boundary measured instead of guessed, and set relative to the
  sample rate (float32 only at 48 kHz and below). He also warns against sudden coefficient
  changes; the double ramp is kept and only its result is rounded.
- **#89:** builds the peaking EQ and contrasts peaking with shelving bands, the two types the
  float32 bands use here. Taken: the worst case is tested for both types, the peak at its
  highest Q being the one that sets the corner.
- **#32:** a first-order IIR with its coefficient and output in float. Nothing taken beyond the
  feedback structure; its low-pass at low corners is the case where float32 was found wanting
  in `biquad.md`.
