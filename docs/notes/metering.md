# Design note: metering

Batch 8c.1. `dsp_meter`, `dsp_kweight` (the owner's exercise EX8c), `dsp_truepeak`.

## Purpose

The numbers the panel LEDs, the PC meters and the protocol's `meters` lines show: per input, per
mix channel and per output, how loud it is and how close to clipping. One block, one or two
channels per instance, with the expensive parts switched on only where they mean something:

| Where | Peak and RMS | True peak | Loudness |
|---|---|---|---|
| Inputs 1 and 2 (one stereo instance), and the LEDs | yes | no | no |
| Monitor mix | yes | yes | yes |
| Speaker and headphone outputs | yes | yes | no |

That split is a proposal for the 8c assembly; the cost of each part is in the two self-test cases.

## The maths

- **Peak with hold and decay**, per sample: the held value jumps to any new |x| at or above it,
  holds for 1 s, then falls by a constant factor per sample, so the fall is linear in dB: 11.8 dB/s
  (20 dB in 1.7 s, the return time IEC 60268-18 gives for peak meters [Verify]).
- **Largest peak since the last read.** The protocol reads at about 30 Hz; this makes sure no
  sample between two reads is missed. The LEDs' holds (8d.3: signal at -40 dBFS for 100 ms, clip
  at -0.5 dBFS for 300 ms) are applied by the reader to this value.
- **RMS:** a one-pole on x², time constant 300 ms [Verify against what the owner wants to see;
  no single standard fixes it]. One multiply-add per sample, no window to store.
- **True peak:** the 4x interpolator the limiter uses (moved into `dsp_truepeak.h` for both: the
  limiter's output is unchanged, byte for byte). Largest value since the last read.
- **Loudness, ITU-R BS.1770-4:** K-weighting (two biquads per channel), the squares summed over
  the channels (weight 1 for left and right), accumulated in double over 100 ms blocks.
  Momentary = mean of the newest 4 blocks (400 ms), short-term = newest 30 (3 s), each reported
  as -0.691 + 10 log10(power) LUFS.

**Why 100 ms blocks.** BS.1770's gated integrated loudness uses 400 ms blocks overlapping by 75 %,
that is, a new one every 100 ms. Keeping 100 ms partial sums gives the momentary value exactly at
every one of those steps, so a PC that reads the momentary value once per new block
(`loudness_blocks` counts them) can compute the gated integrated loudness itself. The device
does not keep the whole programme's history.

**Start-up.** The block history starts as silence at reset, so the momentary value reads low for
the first 0.4 s and the short-term for 3 s, as if the window had run over silence before the
start.

**Reading** converts to dB (the floor is -120 dB, the registry's minimum) and clears the
since-last-read maxima. It must run in the same context as the processing: the 8c assembly reads
at the meter rate inside the audio path and publishes the reading to the control level.

## Structure, and what was rejected

- **Block sums in double, not a running sum.** Recursive RMS (#103) keeps a sum and subtracts the
  sample leaving the window. In float32, what is subtracted is not exactly what was added, and
  over a 3 s window at 96 kHz (288 000 samples) the error does not die away; a quiet passage after
  a loud one can even read a negative mean square. Summing each 100 ms block afresh in double and
  averaging the stored block powers has no drift, needs 30 values instead of 288 000 samples,
  and is what BS.1770's block structure suggests anyway.
- **The RMS as a one-pole, not a window:** a meter's RMS is a ballistic; the one-pole costs one
  multiply-add and no memory.
- **K-weighting in float32 sections.** The RLB high-pass at 38 Hz has poles close to z = 1, which
  batch 3 found noisy in float32 for EQ (`docs/results/b3_filter_noise.md`). For a meter the noise
  floor that matters is the reading's, far below what a monitoring level can show; the EBU cases
  read 0.007 LU low at 48 kHz with the published coefficients (below). Double sections remain an option if the integrated loudness of
  very quiet material disagrees with a reference meter.
- **The K-weighting design is the owner's exercise.** Until `dsp_kweight_design` is written, the
  meter runs unweighted and says so (`kweighted = 0` in every reading). `dsp_meter_f32_set_kweight`
  takes other coefficients; the tests inject the published 48 kHz ones.
- **True peak as an option per instance.** It is the dearest part (two 16-tap phases and one
  8-tap phase per channel per sample), and only the outputs and the mix need it.

## Numerical behaviour

| Measurement | Value | Test |
|---|---|---|
| Held peak against the float64 model | within 1e-4 relative | `test_peak_hold_and_decay_match_reference` |
| Decay rate as set | exact to 1e-4 | the same |
| RMS of a full-scale sine, 3 s | -3.01 dB within 0.05 | `test_rms` |
| True peak of a quarter-rate sine at 45° | sample peak 3.01 dB low; true peak within 0.1 dB, never over | `test_true_peak_catches_the_peak_between_samples` |
| True peak against the model with the taps from `tp_detector.py` | within 1e-5 relative | `test_true_peak_matches_reference` |
| EBU Tech 3341 cases 1 and 2 at 48 kHz (1 kHz sine, -23 and -33 dBFS, both channels) | -22.993 and -32.993 LUFS (limit in the test: 0.1 LU [Verify the tolerance]) | `test_ebu_3341_stereo_sine_at_48k` |
| Block powers against the model | within 1e-4 relative | `test_block_powers_match_reference` |
| Windows at 44.1, 48, 88.2, 96 kHz against the model | within 0.001 LU | `test_windows_at_every_rate` |
| Mono instance | one channel counted (3.01 dB below the stereo reading) | `test_mono_meter_counts_one_channel` |
| Block size 16 against 5 | the whole state bit-identical | `test_block_size_does_not_change_the_state` |

**Found while testing:** a sine switched on abruptly overshoots in the true-peak interpolator
(0.1 dB at 12 kHz), as any band-limited interpolator rings at a step. Real audio has no such step
at the converters; the test drops the onset.

## Cycles on the M7

Not measured yet. Self-test cases `meter_f32` (peak, RMS, true peak and loudness, stereo) and
`meter_peak_f32` (peak and RMS only, stereo). Both run at a nominal 4800 Hz so a loudness block
completes inside the case; the per-sample work does not depend on the rate.

## From the transcripts

Read in full on 2026-11-18: Recursive RMS (#103). Searched all 29 for "loudness", "LUFS",
"meter", "true peak" and "VU": no other passage.

**Agrees**
- #103: the RMS of a sine is its peak over √2 (and over √3 for a triangle); the meter's RMS test
  checks the first.
- #103: the window must be long compared with the lowest frequency of interest, or the reading
  ripples (its 2048-sample window failing below about 100 Hz at 48 kHz). With the 300 ms time
  constant here, a 20 Hz tone's reading ripples by 0.12 dB peak to peak (measured on the PC at 48
  and 96 kHz; the mean is -3.01 dB).
- #103 keeps the mean square and takes the square root only when the value is read; so does this
  meter (the `ms` state, square root and log at read time).

**Differs, and why**
- #103 computes a moving RMS with a running sum: add the newest square, subtract the one leaving
  the window. In float32 the subtraction does not cancel the addition exactly, and the error
  accumulates; for the 3 s short-term window at 96 kHz that is 288 000 samples of history. The
  meter uses block sums in double instead (above).

## Decisions for the owner

1. The crossfeed's explicit delay: 0 by default (`crossfeed.md`), not the plan's "delayed".
2. Meter ballistics: hold 1 s, fall 11.8 dB/s, RMS 300 ms. Easy to change; say if the PC meters
   should look different.
3. Which meters get true peak and loudness (the table at the top), once their cycles are measured.
