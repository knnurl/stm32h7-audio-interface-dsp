# Design note: oversampling and saturation

Batch 6. `dsp_oversample`, `dsp_saturate`.

## Purpose

The saturation stage of the input strips, and later the overdrive of the effect slot (batch 8b),
without the inharmonic aliases a waveshaper makes at the base rate. The same oversampler is the
limiter's true-peak detector.

## The maths

- **Saturation:** y = tanh(d x) / tanh(d), d from the drive in dB. Full scale maps to full scale;
  small signals get a gain of d / tanh(d).
- **Why it aliases:** tanh makes odd harmonics without end; those above fs/2 fold back into the
  audible band as tones unrelated to the input.
- **Half-band oversampling:** a half-band low-pass has every other tap zero except the centre,
  so a 2x stage splits into an FIR on the even taps and a pure delay. 4x is two 2x stages.
- **ADAA (first order):** y[n] = (F(x[n]) - F(x[n-1])) / (x[n] - x[n-1]) with F the antiderivative
  of the curve: the exact average of the curve over the straight line between two samples.

## Structure, and what was rejected

- **Polyphase half-band, equiripple:** 83 taps (113 dB) for the first 2x stage, 23 taps (125 dB)
  for the second; 42 and 12 multiply-adds per base-rate sample each way. Rejected: computing
  every high-rate output and discarding half (#42's teaching version).
- **Stopband from 28 kHz, not 24 kHz:** content between 24 and 28 kHz at the high rate folds into
  20 to 24 kHz. Inaudible, and the price of half the taps.
- **tanh from the C library per high-rate sample:** its cost on the M7 is measured on the board;
  a cheaper curve (Phil's piecewise quadratic, below) is the fallback.

## Numerical behaviour

`docs/results/b6_aliasing.md` (`python tools/studies/b6_aliasing.py`): strongest inharmonic
component below 20 kHz, -0.9 dBFS sine, 12 dB of drive, 48 kHz.

| Input | Plain | ADAA | 2x | 4x |
|---|---|---|---|---|
| 1 kHz | -108.8 | -115.0 | -170.1 | -169.1 |
| 5 kHz | -27.4 | -38.5 | -64.4 | -130.9 |
| 10 kHz | -11.7 | -19.9 | -34.8 | -71.8 |
| 15 kHz | -11.7 | -22.5 | -27.4 | -49.6 |

Other measurements:
- The polyphase stages equal direct convolution with the zero-stuffed signal to -129 dBFS
  (float32 accumulation over 42 taps). Round-trip latency 41 samples (2x) and 46.5 (4x),
  confirmed with a sine. Image of a 15 kHz tone at 2x: more than 110 dB down.
- A symmetric curve makes no even harmonics: all below -110 dB.
- ADAA's small-signal response is a two-sample average, |cos(ω/2)|, within 0.05 dB: -3 dB at
  12 kHz and -11.7 dB at 20 kHz at 48 kHz. So ADAA trades treble for aliasing at 1x.
- Oversampled clipping of full-band noise peaks at 1.45 (2x) and 1.55 (4x): band-limiting a
  clipped signal raises its peaks. Inherent to removing the aliases; the limiter catches it.

**Latency is the cost.** 46.5 samples at 4x is 0.97 ms at 48 kHz, 0.48 ms at 96 kHz, in the
input strips and therefore in the monitor path. It eats a third of the 1.5 ms monitoring target
(SPEC 3.2) at 48 kHz. The fractional half sample also means a dry path cannot be time-matched
exactly, so a parallel dry and wet blend would comb-filter (-2 dB at 20 kHz).

## Cycles on the M7

Not measured. Self-test cases `sat_os4_f32` and `sat_adaa_f32` time them.

## From the transcripts

Read in full on 2026-11-17 (by a review agent in this session, findings checked here): DSP
Overdrive (#117), DSP Overdrive Asymmetrical Clipping (#153), Decimation Filters (#42).

**Agrees**
- Aliasing is the central problem of a waveshaper: band-limit, "or you get aliasing
  distortion" (#117).
- Gain into a static curve sets the amount; a symmetric curve gives odd harmonics only (#117's
  FFT; our test).
- Decimation: low-pass first, then discard, "very important that we do this before down
  sampling" (#42). FIR for its linear phase.

**Differs, and why**
- #117 does not oversample: it low-passes at fs/4 before a quadratic curve, which only doubles
  the bandwidth. That cannot work for tanh, whose harmonics never stop; oversampling and ADAA
  are the general answers. The table above is the evidence.
- #117's curve is a piecewise quadratic (linear below 1/3, quadratic to 2/3, flat above). It is
  cheaper than tanh and has a closed-form antiderivative, so it suits ADAA. A candidate if tanh's
  cycle count is too high.
- #42 computes every output and discards; ours is polyphase. Its stopband starts at the new
  Nyquist; ours at 28 kHz, as explained above.

**Suggested and not done**
- **Asymmetric clipping** (#153): a curve that treats the two halves differently gives even
  harmonics too, which is the "warmer" sound. Its output has a DC offset (not mentioned in the
  video), so a DC blocker must follow it. Planned for the overdrive in batch 8b, not in the
  strips' saturation.
- A high-pass before the shaper (#153's cure for "muddy") and a tone low-pass after it: the
  overdrive's job in batch 8b.
- Output level compensation beyond the full-scale normalisation.

**Fixed in the pass:** ADAA produced a spike when the drive changed (the stored antiderivative
belonged to the old curve) (`test_adaa_survives_a_drive_change`); the 4x wrapper overflowed its
scratch above 64 frames (now chunked); the header miscounted the taps (2K + 2, not K + 1).

## Open questions

- Which mode the strips' saturation uses by default: 4x (best, 0.97 ms at 48 kHz) or 2x (0.85
  ms, 30 dB worse at 5 kHz), once the cycle counts exist.
- Whether drive changes need smoothing inside the block (they are not smoothed; batch 8a's
  parameter smoothing will ramp them).
