# Design note: the tone control (`dsp_tone_f32`)

Batch 3. The DSP behind the BASS, MID and TREBLE knobs.

## Purpose

Shape the listening, not the recording: monitors and headphones only, after the effect slot and
the record tap (SPEC 2). Three bands, -12 to +12 dB each, flat at centre.

## The maths

A low shelf at 100 Hz, a peak at 1 kHz with Q 0.7, and a high shelf at 10 kHz, shelf slope 1
(cookbook designs). The corner frequencies are proposals for the owner to confirm by ear.

## Structure, and what was rejected

- **Smoothing in dB, per block.** Each band's gain follows its target through a one-pole with a
  20 ms time constant, updated once per block, and snaps to the target within 0.001 dB.
  Rejected: smoothing per sample, which would mean a redesign per sample.
- **Redesign per block from the smoothed gain.** Rejected: interpolating coefficients between
  designs. A knob turned slowly would give a path through coefficient space that is not a tone
  control at all between the endpoints.
- **Skipping a band at exactly 0 dB, once its state is silent.** This makes the centre exact:
  with all three knobs at centre the output is the input, bit for bit. A band arriving at 0 dB
  keeps running on its 0 dB design (the identity response) until its state has decayed below
  1e-9, so its last transient is not cut off. A band leaving 0 dB starts from cleared state,
  which is exact because a skipped band holds no signal.
- **Double-precision state** (`dsp_biquad_f64_section`): float32 state gives only 80 to 110 dB
  of signal-to-noise on the 100 Hz shelf (`docs/notes/biquad.md`).

## Numerical behaviour

| Measurement | Value | Test |
|---|---|---|
| Flat at centre | bit-exact | `test_flat_at_centre_is_bit_exact` |
| Static response, 11 gain combinations at 48 and 96 kHz | within 0.05 dB of the design at 31 frequencies | `test_static_response` |
| Moving gains against a float64 blockwise model | within -120 dBFS | `test_moving_gains_match_a_blockwise_reference` |
| Zipper: a full -12 to +12 dB bass sweep in 100 ms, sidebands against a per-sample redesign | -106 dBFS on a 50 Hz tone, -107 dBFS on a 5 kHz tone | `test_zipper_noise_of_a_full_sweep` (limit -100) |
| Time constant | 63 % of a step after 20 ms, within 2 % | `test_smoothing_arrives_exactly_and_on_time` |
| Leaving 0 dB | under 1 % change in the first block on a half-scale 60 Hz tone | `test_leaving_centre_has_no_step` |

## Cycles on the M7

Not measured. The estimate in SPEC 3.4 is 60 cycles per sample for the stereo bus. While a knob
moves, each moving band adds one design per block (a `pow`, a `sin`, a `cos`, in double).

## Open questions

- The corner frequencies and the mid Q: the owner's ears decide.
- Whether a knob's own reading noise (batch 8d) keeps the bands redesigning when nobody touches
  them. The panel pipeline's hysteresis is meant to stop that; the tone block itself only
  redesigns when its target changes.

## From the transcripts

Read in full on 2026-11-17: Biquad Filters (#172), Audio EQ Software Implementation (#89),
Notch Filters (#49), The Simplest Digital Filter (#92).

**Agrees**
- #172 recomputes coefficients "once per block" from the knob values: the same cadence as here.
- #172 moves towards a new setting only "if there is a significant difference": our 0.001 dB
  snap is the same idea at the other end.
- #172 warns that sudden coefficient jumps "can cause large transients ... instability".
- #89: a peak at unity gain is the identity, and unity away from f0 lets bands cascade. That is
  what makes the exact skip at 0 dB possible.

**Differs, and why**
- #172 smooths each coefficient directly with a one-pole, per sample. We smooth the gain in dB
  and redesign per block: every intermediate filter is a real tone setting, and the measured
  zipper is -106 dBFS. Our choice stands on that measurement.
- #92's one-pole smoother uses a hand-picked alpha; ours derives it from the time constant.

**Suggested and not done**
- A dead band on the knobs before recomputing (#49 uses about 10 % of travel). Kept for batch
  8d, where the panel pipeline's hysteresis does it.
- Cross-fading two filter instances (#172's alternative to smoothing).

**Open question raised by the pass:** `dsp_peq` interpolates coefficients linearly over its ramp,
which is close to #172's approach and the one this note rejects for the tone control. It is
stable (the stability triangle is convex), so it is not a bug, but the two blocks now follow
opposite rules, and a PEQ band changed from a peak to a shelf passes through curves that are
neither. Proposal for batch 8a: changes of band type cross-fade two instances; changes of
frequency, gain or Q redesign per block as the tone control does. Owner to decide.

**Fixed in the pass:** with every band skipped, the right channel's output was only written when
the left channel was not processed in place. The header allows them to alias independently.
Now each channel is copied on its own (`test_flat_with_one_channel_in_place`).
