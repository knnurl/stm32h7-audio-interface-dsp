# Design note: the true-peak limiter

Batch 6. `dsp_limiter`.

## Purpose

The last block before the monitor outputs: protects speakers and the DAC from overs, from any
source (strips, makeup gain, oversampled clipping, the effect slot).

## The maths

Required gain per sample r = min(1, ceiling / true peak), the true peak taken from a 4x
oversampled copy of both channels. The applied gain is a moving average over L samples of a
held minimum of r over L + 3 samples, with a one-pole release when the minimum rises; the audio
is delayed by L + 24 samples so each drop has finished before the loud sample arrives.

## Structure, and what was rejected

- **Sliding minimum, then moving average.** Every value in the average is no larger than the
  gain the sample needs, so the average is not either: the ceiling holds per sample by
  construction, with a linear ramp of L samples into every reduction. Rejected: a one-pole
  attack, which can never be guaranteed to reach the gain in time.
- **A monotonic queue for the sliding minimum:** O(1) per sample on average.
- **The moving average in double:** exact for gains above about 2^-20, so a released limiter's
  average of ones is exactly 1.0 and the output is the delayed input bit for bit.
- **Stereo-linked:** the larger channel decides, so the image does not shift.

## Numerical behaviour

| Measurement | Value | Test |
|---|---|---|
| No output sample above the ceiling: square, inter-sample-peak sine, noise bursts, spikes; look-ahead 32 to 480 samples | holds | `test_no_sample_exceeds_the_ceiling` |
| Latency | L + 24, exact | `test_latency_is_lookahead_plus_24` |
| Below the ceiling | bit-exact, delayed | `test_below_the_ceiling_is_bit_exact` |
| After a release | bit-exact again | `test_release_returns_to_bit_exact` |
| NaN and infinity in | finite out, under the ceiling | `test_bad_input_cannot_get_through` |
| Sample counter wrapping at 2^32 | holds | `test_sample_counter_wrap` |
| True peak of the output over the detection threshold, worst of the hostile set | 0.198 to 0.199 dB at 32, 48, 96 and 240 samples of look-ahead | `test_true_peak_stays_under_the_set_ceiling` |
| True peak of the output against the set ceiling (threshold 0.5 dB lower) | about -0.30 dB, under at every look-ahead | `test_true_peak_stays_under_the_set_ceiling` |

**The true-peak overshoot, and its cause.** The overshoot does not change with the look-ahead,
and band-limiting the test bursts to 18 kHz leaves 0.16 dB of it, so it is neither the gain's
own sidebands nor content above 20 kHz. It is the 4x detection: the largest of four samples per
input sample can sit below the true peak between them, by up to cos(π f / 4 fs): 0.47 dB for a
20 kHz component at 48 kHz, less at 96 kHz. That is the known weakness of 4x true-peak meters.

**Bug found by the tests:** the release one-pole stalled at a gain of 0.99997 (float32, the same
stall as the gain block in batch 1), so the output never returned to bit-exact. It now finishes
the move when it stalls or is within 1e-6.

## Cycles on the M7

Not measured. Self-test case `limiter_f32`. The detector is the expensive part: two 4x
upsamplers, about 108 multiply-adds per stereo sample before folding the symmetric taps.

## From the transcripts

None of the six batch 6 transcripts covers a limiter. The compressor video's suggestion of a
forward-path delay "to compensate for the delay introduced by the side chain" is the same idea
as the look-ahead here. The batch 6 review checked the alignment argument (the detector's
delay is 23.25 samples; the 24 and the window of L + 3 leave a sample of slack) and found it
correct; its explanation of the true-peak overshoot as gain sidebands was not borne out by the
measurement above, and ours stands.

## Decision (owner, 2026-11-17)

Option 1, the 0.5 dB margin: the detector works against a threshold 0.5 dB under the set
ceiling (`DSP_LIMITER_TRUE_PEAK_MARGIN_DB`). Option 3 stays the measured improvement for later.
The options were, to close the 0.2 to 0.5 dB true-peak gap, given this block protects the
speakers:
1. **A margin:** run the detector against a ceiling 0.5 dB lower than the one the owner sets.
   Free; costs 0.5 dB of loudness at the limit.
2. **8x detection:** halves the worst case (cos(π f / 8 fs)); costs another upsampling stage per
   channel.
3. **Interpolate between the four:** a parabola through the largest sample and its neighbours
   estimates the true peak; cheap, but its accuracy needs measuring.
Recommendation: 1 now, 3 as a measured improvement later.
