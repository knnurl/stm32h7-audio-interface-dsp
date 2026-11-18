# Design note: the monitor mixer

Batch 8c.1. `dsp_mixer`.

## Purpose

Sums the sources the monitor path hears into one stereo bus, and feeds the reverb's stereo send:
the two input strips, USB playback, S/PDIF in (batch 10) and the reverb's return. One instance,
eight mono channels: in 1, in 2, USB L and R, S/PDIF L and R, reverb return L and R. The registry
parameters it serves are ids 300 to 310 (levels, pans, sends, return); the blend knob (8c.4) is an
equal-power crossfade the assembly applies to the channel levels, not a part of this block.

## The maths

Per channel, with t = (p + 1) π / 4 for the pan position p in [-1, 1]:

| Gain | Value |
|---|---|
| main L | level cos t |
| main R | level sin t |
| send L | level send cos t |
| send R | level send sin t |

cos² t + sin² t = 1, so the power a channel puts into the pair is the same at every pan position:
a constant-power pan law, -3.01 dB to each side at the centre and unity on the hard side.
Muted, all four gains are 0. A stereo source is two channels panned -1 and +1: it passes at unity,
bit for bit (each output is 1.0 × x + 0).

Every gain moves linearly to its new value over the ramp time (20 ms, the registry's smoothing
time for these parameters), starting from wherever it is when the change arrives. The gains are
computed at the control level with `cosf` and `sinf`; the ends and the centre are written as
constants so they do not depend on the C library's last bit.

## Structure, and what was rejected

- **Constant power, -3 dB centre.** Rejected: the linear law (gains 1 - u and u), which is what a
  wet and dry mix control does (#140, below): -6 dB at the centre, so a source sounds quieter
  panned centre than panned hard. Also rejected: -4.5 dB compromise laws; the plan asked for -3.
- **The send is post-pan and post-level** (owner, 2026-11-18; first written pre-level). Turning a
  channel down turns its reverb down with it, so the wet and dry balance of a ridden channel
  stays as set; that is the usual convention for an effect send. Rejected: pre-level, where a
  channel pulled down leaves its reverb behind at full level. Its pan follows the channel's, so a
  source panned left has its reverb start from the left. Tested in `test_send_follows_the_level`.
- **Mono channels only.** A stereo source is a pair of mono channels at ±1. Rejected: a stereo
  channel type with a balance control; it would double the code for one less parameter.
- **Silent channels cost nothing.** A channel whose four gains are 0 and still is skipped, and an
  unconnected input (a NULL pointer) is read as silence while its ramps still advance. With
  S/PDIF unconnected until batch 10, two of the eight channels are free.
- **Outputs overwritten, then summed into.** Each output is cleared once, then each channel adds
  its share: the order of the sums is fixed, so the output does not depend on the block size
  (tested).

## Numerical behaviour

| Measurement | Value | Test |
|---|---|---|
| Pan law: L² + R² at 41 positions | 1 within 1e-6 | `test_pan_law` |
| Centre | -3.0103 dB each side | `test_pan_law` |
| Settled mix against the float64 model, six channels | within 2e-6 | `test_settled_mix_matches_reference` |
| Mix with three changes mid-run | within 1e-5 (the float ramp drifts up to 4e-6 over 960 steps before it lands) | `test_changes_ramp_linearly_and_match_reference` |
| Ramp from 1 to muted | 960 equal steps at 48 kHz, each at most 1.01 / 960 (the last absorbs the drift), then exactly 0 | `test_ramp_has_no_step_and_reaches_target` |
| Stereo source at ±1 | bit-exact | `test_stereo_source_passes_at_unity_bit_for_bit` |
| Block size 16 against 7 | bit-identical | `test_block_size_does_not_change_the_output` |

## Cycles on the M7

Not measured yet. Self-test case `mixer_f32`: the eight channels as the device will use them
(two strips and USB sent to the reverb, S/PDIF muted, the reverb return), 128 frames, two
channels ramping throughout. The bench reports it with channels = 8, so its cycles per frame are
the whole mixer's.

## From the transcripts

None of the batch 8 transcripts covers a mixer or a pan law. Searched all 29 for "pan", "mix" and
"headphone"; the one relevant passage is in Delay-Based Audio FX (#140), read in full for batch 8b.

**Differs, and why**
- #140's mix control is linear: output = M × wet + (1 - M) × dry. That is right for a wet and dry
  blend of correlated signals (the dry signal and its own delayed copy), where amplitudes add. A
  pan places one signal in two speakers, whose outputs add in power at the listener, so the law
  here keeps power constant instead. The blend knob of 8c.4 is equal-power for the same reason:
  the inputs and USB playback are uncorrelated sources.
