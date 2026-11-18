# Design note: the headphone crossfeed

Batch 8c.1. `dsp_crossfeed`.

## Purpose

On headphones each ear hears only its own channel, so a source panned hard left sits inside the
left ear. From speakers both ears hear both speakers, the far ear a little later and with less
treble (the head shadows it). A crossfeed imitates that, so long sessions on headphones tire less
and pans sound closer to the monitors. It sits in the headphone stage between the PEQ and the
limiter, controlled by `hp_crossfeed_on` (712) and `hp_crossfeed_amount` (713).

## The maths

    lp = LP(x)                                      one-pole low-pass, corner fc = 700 Hz
    y  = ((1 + g) x - g lp + g lp_opposite[n - D]) / (1 + g)

that is, the near ear's own signal with its highs lifted, x + g (x - lp), plus the other
channel's low-passed signal, D samples late, all scaled by 1 / (1 + g). The code computes the same
thing rearranged, with h = g / (1 + g):

    y  = x + h (lp_opposite[n - D] - lp)

g = amount × 0.596 (a level difference of -4.5 dB between the ears at low frequencies at full
amount: bs2b's default [Verify]).

| Source | Near ear | Far ear |
|---|---|---|
| Hard left, low frequencies | 1 / (1 + g): -4.1 dB at full amount | g / (1 + g): -8.5 dB |
| Hard left, high frequencies | about unity (-0.16 dB at 10 kHz) | below -25 dB at 10 kHz |
| Centred (mono), D = 0 | the input itself, to float rounding | |

**The delay is 0 by default.** The plan said "low-passed and delayed". The low-pass already
delays the far ear's low frequencies by its group delay, a / (1 - a) samples at DC with
a = exp(-2π fc / fs): 0.22 ms at 700 Hz, about the difference in arrival time between the ears
for a speaker 30° off centre [Verify]. An explicit delay on top breaks the property that makes
this structure attractive: with D = 0 and a centred source, lp_opposite - lp is exactly 0, so
the source passes unchanged. Measured with D > 0 at 48 kHz and full amount:

| Explicit delay | Centred source |
|---|---|
| 0 | unchanged |
| 100 µs (5 samples) | dips 1.41 dB at 1.69 kHz |
| 300 µs (14 samples) | dips 3.53 dB at 886 Hz |

A 3.5 dB dip near 900 Hz colours every centred vocal and bass line, so the default is 0. The
setter (`dsp_crossfeed_f32_set_delay_us`, up to 255 samples) stays, so the owner can listen to
both. **Confirmed by the owner on 2026-11-18: no explicit delay.**

## Structure, and what was rejected

- **One low-pass per channel serves both paths.** The low-pass of the delayed signal is the
  delayed low-pass (both linear and time-invariant), so the delay line stores lp, not x.
- **A one-pole, not a biquad.** The head's shadow is gentle; a second-order low-pass would cut
  the far ear's highs harder and remove the exact mono cancellation unless the near ear's lift
  used the same filter. Kept simple; measured by listening when the boards play audio.
- **Off is bit-exact.** At amount 0, once the ramp has finished, the output is the input. The
  filters and the delay line keep running, so turning it on starts from a filled state with no
  burst.
- **Only h ramps** (linearly, 10 ms), so a centred source stays exact during a ramp too, and each
  ear costs one multiply-add. **Found while writing this note:** the first version ramped g and
  1 / (1 + g) separately, which are not reciprocal half-way through a ramp: switching on bumped a
  centred source by 0.47 dB for 10 ms. Fixed in the commit after the first; a test holds it.

## Numerical behaviour

| Measurement | Value | Test |
|---|---|---|
| Against the float64 model at 44.1, 48 and 96 kHz, amounts 0.3 and 1, D 0 and 300 µs | within 2e-6 | `test_matches_reference` |
| Amount 0 | bit-exact | `test_amount_zero_is_bit_exact_pass_through` |
| Hard-panned source at 50 Hz and 10 kHz | the table above, within 0.01 dB of the model | `test_hard_panned_source` |
| Centred source, D = 0 | the input within 1e-6 | `test_centred_source_passes_unchanged` |
| Centred source, D = 100 and 300 µs | the dips above, C output within 0.02 dB | `test_explicit_delay_dips_a_centred_source` |
| Far ear with D = 300 µs | silent for 14 samples at 48 kHz, 29 at 96 kHz | `test_far_ear_delay` |
| Back to amount 0 | bit-exact again after the ramp's block | `test_amount_changes_ramp_and_return_to_exact_bypass` |
| Centred source while the amount ramps from 0 to 1 | the input within 1e-6 | `test_centred_source_stays_exact_while_the_amount_ramps` |
| Block size 16 against 5 | bit-identical | `test_block_size_does_not_change_the_output` |

## Cycles on the M7

Not measured yet. Self-test case `crossfeed_f32`: stereo, full amount, then a ramp to 0.5.

## From the transcripts

None of the batch 8 transcripts covers crossfeed or headphones; searched all 29 for "crossfeed",
"headphone" and "pan". The only hit is the I2S video (#55), which mentions a codec's headphone
output and nothing about processing for it. The one-pole low-pass is the one the effects already
use (`dsp_fx_common.h`), from batch 3's reading of The Simplest Digital Filter (#92).
