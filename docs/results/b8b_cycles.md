# Batch 8b: cycles per sample

**Not measured on the M7.** The board has not been run yet (no ST-LINK attached). Each block
has a self-test case; `tools/target_test.py --port COMx` (the `bench` console command) times
every case on the target and checks its output against the PC. This table is filled from that
run; the SPEC 3.4 rows for the effect slot and the reverb are replaced by it (8b.7).

Each case processes 1024 words: stereo cases are 512 frames per channel, in blocks of 16.
Cycles per sample = case cycles / 1024 for mono cases, / 512 for stereo frames.

| Block | Self-test case | Rate in the case | Cycles per stereo sample (M7, 400 MHz) | Estimate before measuring |
|---|---|---|---|---|
| Delay line, Lagrange read | `delay_lagrange_f32` | 48 kHz, mono | not measured | about 20 per read |
| State-variable filter | `svf_f32` | 48 kHz, mono | not measured | about 12 |
| Echo, 16-bit lines | `fx_echo_f32` | 48 kHz | not measured | about 70 |
| Echo at 96 kHz (core at 48 kHz, two half-bands each way) | `fx_echo96_f32` | 96 kHz | not measured | about 120 per 96 kHz frame |
| Chorus | `fx_chorus_f32` | 16 kHz | not measured | about 110 (4 Lagrange reads, 4 LFO values) |
| Flanger | `fx_flanger_f32` | 48 kHz | not measured | about 60 |
| Phaser, 8 stages | `fx_phaser_f32` | 48 kHz | not measured | about 45 |
| Tremolo | none until exercise 8b is done | | not measured | about 30 |
| Sweep filter | `fx_sweep_f32` | 48 kHz | not measured | about 30 |
| Overdrive, 4x | `fx_overdrive_f32` | 48 kHz | not measured | about 400 (two 4x oversamplers, 8 tanhf) |
| Bit crusher, dither on | `fx_crusher_f32` | 48 kHz | not measured | about 25 |
| Effect slot, phaser then flanger | `fxslot_f32` | 48 kHz | not measured | the effect plus about 10 |
| Reverb | `reverb_f32` | 16 kHz | not measured | about 150 |

The estimates are operation counts, not measurements [Verify]. The overdrive is the dearest
effect by a wide margin, so it sets the slot's budget row; tanhf per oversampled sample is the
first thing to replace if it is over (the piecewise curve of #117 has a closed form).
