# Design note: envelope, compressor and gate

Batch 6. `dsp_fastmath`, `dsp_env`, `dsp_comp`, `dsp_gate`.

## Purpose

The input strips' gate and compressor (SPEC 2), and the building blocks the limiter and the
meters share: level detection and fast dB conversion.

## The maths

- **Envelope.** Peak: a branching one-pole on |x| (attack coefficient when rising, release when
  falling). RMS: a one-pole on x², square root on the way out. Coefficients exp(-1 / (τ fs)):
  times are time constants.
- **Compressor** (Giannoulis, Massberg and Reiss, JAES 2012, "log domain, smooth branching"):
  instantaneous level in dB; a static curve with threshold, ratio and a soft knee; the wanted
  gain reduction smoothed in dB by a branching one-pole; makeup; back to linear.
- **Gate.** A peak detector with instant attack; opens at the threshold, closes only after the
  level has stayed below threshold minus hysteresis for the hold time; the gain moves between 1
  and the range through a one-pole.
- **Fast log2 and exp2.** The float's exponent plus a cubic-constrained polynomial on the
  mantissa, continuous across octaves (`tools/design/b6_coefficients.py`).

## Structure, and what was rejected

- **Smoothing the gain reduction in dB, not the level.** Attack and release then do not depend
  on threshold and ratio, and the release is smooth. Rejected: smoothing the detected level
  (Phil's Lab's RMS detector), which couples the times to the curve.
- **Fast log and exp per sample.** One `log10` and one `pow` per sample would be the most
  expensive part of the compressor; the polynomials are good to 1.4e-4 dB in float32. Their
  cycle cost against the C library's is measured on the board.
- **Gate thresholds compared in the linear domain.** Exact, and no logarithm at all (a change
  made in the transcript pass; the first version compared in dB).

## Numerical behaviour

| Measurement | Value | Test |
|---|---|---|
| Fast log2 error (float32) | 2.25e-5 (1.4e-4 dB) | `test_log2_accuracy` |
| Fast exp2 relative error | under 3e-7 | `test_exp2_accuracy` |
| Envelope time constants | within 5 % | `test_peak_attack_and_release_time_constants` |
| RMS of sine, triangle, square | A/√2, A/√3, A within 0.5 %; ripple under 1 % at τ = 50 ms, 1 kHz | `test_rms_of_standard_waveforms` |
| Compressor static curve, 20 levels | within 0.1 dB | `test_static_curve_at_20_levels` |
| Compressor attack and release | within 5 % | `test_attack_and_release_time_constants` |
| Compressor against a float64 model with exact maths | within -90 dBFS | `test_matches_the_float64_reference` |
| 40 Hz tone 12 dB over threshold, THD at release 10, 50, 200 ms | -24.0, -33.0, -42.6 dB | `test_bass_distortion_against_release` |
| Gate: a tone wandering between -41 and -38 dB around a -40 dB threshold | opens once, never chatters | `test_no_chatter_at_the_threshold` |
| Gate hold, from DC to silence | within 3 samples of detector fall plus hold | `test_hold_time` |

**Bass distortion.** The instantaneous detector lets the gain move within each cycle of a low
note when the release is short. Measured above: -24 dB of THD at a 10 ms release. The strips'
default release should be 50 ms or more, and the side-chain high-pass (tested: it cuts the gain
reduction on a 40 Hz tone by more than 6 dB at 150 Hz) is the second defence. An RMS detector
option is the third, not built.

## Cycles on the M7

Not measured. Self-test cases `comp_f32` and `gate_f32` time them.

## From the transcripts

Read in full on 2026-11-17 (by a review agent in this session, findings checked here): Audio
Compressor Software Implementation, Noise Gate (#58), Recursive RMS (#103).

**Agrees**
- The compressor's block diagram: detector, gain computer in dB, attack and release, makeup,
  then linear. The soft knee's three regions; a knee of 0 is a hard knee. The log of zero
  guarded (he adds an epsilon; our fast log has a floor).
- RMS kept as a mean square, with the square root last (#103: store "the square of the RMS at
  all times").
- Gate: gain smoothed so it does not switch hard ("nasty distortion"); hold on the closing side
  only.

**Differs, and why**
- #103's RMS is a boxcar (a running sum over a window). Ours is a one-pole: no buffer, and no
  running sum that drifts and can go negative under a square root, at the price of a small
  ripple (measured under 1 %). A one-pole of τ matches a boxcar of about 2τ: his 50 ms window is
  our 25 ms.
- His compressor detects with a 50 ms RMS; ours is instantaneous with the smoothing on the gain
  reduction (the Giannoulis recommendation). A sine therefore reads at its peak, 3 dB above its
  RMS. The cost is the bass distortion measured above.
- **Time conventions.** His coefficients are exp(-2.2 / (t fs)): 10 to 90 % rise times. Ours are
  time constants. A setting copied from his video, or from MATLAB, means a time 2.2 times longer
  here. Written into `dsp_comp.h`.
- **Gate naming.** He calls the gain falling "attack" and rising "release". We follow MATLAB and
  most hardware: attack opens. Labels in the user interface must not copy his.
- His gate switches on raw |x|; ours has a peak detector and hysteresis, which is the fix for the
  failure he describes, a signal that "keeps going above and under". Ours also closes to a range
  rather than to silence.
- He caps the compressor's gain at 1; ours lets makeup go above 1, and the limiter downstream
  catches overs.

**Suggested and not done**
- Automatic makeup (from threshold, knee and ratio for a 0 dBFS input).
- An RMS detector option for the compressor (`dsp_env_rms` exists; wiring it is small).
- Per-band gating with longer windows for low frequencies (#58's "multi-band noise gate").

**Fixed in the pass:** NaN input no longer leaves the side-chain filter poisoned (it stopped the
compressor for good); `dsp_fast_exp2f(NaN)` was undefined behaviour; the gate's range is clamped
to 0 dB or below; the effective hold (hold plus detector fall time) is now documented.

## Open questions

- The strips' default release (50 ms or more, from the distortion figures) and whether to offer
  the RMS detector.
