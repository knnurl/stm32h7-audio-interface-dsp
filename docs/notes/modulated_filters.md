# Design note: modulated filters (why the state-variable filter)

Batch 8b. `dsp_svf`, used by the sweep filter; the first-order all-pass of the phaser.

## Purpose

Filters whose cutoff moves while audio runs through them: the sweep filter under a knob, the
phaser's all-pass chain under an LFO. A filter that is good when still can misbehave when its
coefficients change.

## The maths

Topology-preserving state-variable filter (Zavalishin's trapezoidal integrators, in Simper's
formulation):

- g = tan(pi fc / fs), k = 1 / Q, a1 = 1 / (1 + g (g + k)), a2 = g a1, a3 = g a2;
- v3 = v0 - ic2, v1 = a1 ic1 + a2 v3, v2 = ic2 + a2 ic1 + a3 v3, ic1 = 2 v1 - ic1,
  ic2 = 2 v2 - ic2;
- low = v2, band = v1, high = v0 - k v1 - v2, notch = v0 - k v1.

It is the bilinear transform of the analogue state-variable filter with exact prewarping, so at
fc the low-pass and high-pass are at 20 log10(Q) and the band output peaks at Q
(`test_svf_textbook_response`: -3.010 dB at Q 0.7071, within 0.002 dB).

For per-block modulation, tan is replaced by the Pade approximant x (15 - x^2) / (15 - 6 x^2):
g error 2.1e-4 below fs / 4 and 3.2 % at the 0.45 fs clamp, which is a cutoff error of only
0.37 % there (`test_fast_g_error`).

## Structure, and what was rejected

- **The SVF, not a direct-form biquad**, for anything that moves. The SVF's two states are its
  integrators' outputs, physical quantities that stay meaningful when g or k changes. A
  direct-form biquad's states are mixtures of past inputs and outputs that are valid only for
  the coefficients that produced them.
- Measured on a low-pass, Q 5, half-scale noise, coefficients updated every 16 samples
  (`test_svf_against_biquad_under_modulation`):

  | Cutoff motion | Static bound | SVF peak | Transposed direct form II biquad |
  |---|---|---|---|
  | Jumping 200 Hz to 8 kHz every 16 samples | 3.19 | 1.64 | overflows to 1.7e38, then NaN after 2345 samples |
  | Sweeping 200 Hz to 8 kHz at 5 Hz, smoothly | 3.19 | 1.48 | 1.48 |

  So a smooth sweep is fine either way. A fast jump, which a knob snapped quickly or a sync'd
  LFO with a square shape can produce, destroys the biquad. The SVF costs about the same.
- **Coefficients every 16 samples** (`kDspFxSubBlock`), not every sample: one Pade tan and one
  fast exp2 per 16 samples per channel instead of per sample. 16 samples at 48 kHz is a 3 kHz
  update rate, far above any knob or LFO.
- **Phaser: first-order all-pass sections** (#162's coefficient), in the transposed form
  y = c x + s, s = x - c y, one state per section. Rejected: second-order all-pass sections,
  which give sharper notches but twice the cost per notch.

## Numerical behaviour

- The SVF matches its float64 model to -110 dB in all four modes.
- At the 0.45 fs clamp the fast g is 3.2 % low; nothing in the effects goes above 20 kHz.

## Cycles on the M7

Not measured. Self-test cases `svf_f32`, `fx_sweep_f32`, `fx_phaser_f32`.

## From the transcripts

Read in full for batch 3 on 2026-11-17 and re-read for this batch where they bear on it:
All-Pass Filter Software Implementation (#162). The batch 8b transcripts (#124, #140, Tremolo)
do not cover modulated filters.

**Agrees**
- #162: the first-order all-pass H(z) = (c + z^-1) / (1 + c z^-1) with
  c = (tan(pi fc / fs) - 1) / (tan(pi fc / fs) + 1) has unit magnitude and -90 degrees at fc,
  tending to -180 at Nyquist; its pole -c is inside the unit circle for fc < fs / 2. Checked
  through the phaser's own coefficient function (`test_phaser_coefficient_puts_minus_90_degrees_at_fc`:
  within 0.05 degrees, using the Pade tan).
- #162: recompute c only when the cutoff changes, because of the tan. Ours recomputes once per
  16 samples, with a Pade tan.

**Differs, and why**
- #162 implements the all-pass as a difference equation storing the previous input and output
  (two state words); ours uses the transposed form with one. Same response.
- None of the transcripts addresses coefficient changes under signal. The measurement above is
  ours.

**Suggested and not done**
- #162 says all-pass filters are building blocks of reverbs (diffusers). Not used: see
  `docs/notes/reverb.md`, open questions.
