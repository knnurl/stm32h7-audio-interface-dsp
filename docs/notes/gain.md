# Design note: smoothed gain (`dsp_gain_f32`)

Batch 1. The simplest block, and the first one to show a float32 effect worth knowing.

## Purpose

Apply a gain that can change without a click. Every level control in the device (trim, volume,
mute, dim, blend) is this block.

## The maths

A step in gain is a step in the signal's envelope, which is heard as a click. Passing the gain
through a one-pole low-pass turns the step into an exponential approach:

```
g[n] = g[n-1] + k * (target - g[n-1])        k = 1 - exp(-1 / (tau * fs))
y[n] = x[n] * g[n]
```

`tau` is the time constant: after `tau` seconds the gain has covered 63 % of the distance. The
block smooths the linear gain. A fade to silence is then exponential in level, which sounds like
a natural decay.

## Structure, and what was rejected

- **One-pole on the linear gain, per sample.** Two multiplies and two adds per sample.
- Rejected: a linear ramp over a fixed number of samples. It reaches the target exactly and
  costs one add per sample, but it needs a counter and a restart rule when the target changes
  mid-ramp. Worth revisiting if the cycle count matters.
- Rejected: smoothing in decibels. It gives a constant rate in dB, but needs `powf` per sample
  or per block.
- Rejected: updating the gain once per block. With a 16-sample block at 96 kHz the steps are
  6 kHz apart and audible as zipper noise on low-frequency signals.

## Numerical behaviour

Two effects, both found by the tests rather than predicted.

**1. The recursion stalls short of its target.** The update adds `k * (target - g)` to `g`. Once
that product is smaller than half a unit in the last place of `g`, the addition rounds back to
`g` and the gain stops moving. The remaining distance is about `ulp(g) / (2 k)`.

| Case | Value |
|---|---|
| Target 0.25, 5 ms at 48 kHz (`k` = 0.00416) | stalls at 0.250003576 |
| Distance | 3.6e-6, which is -109 dBFS of error on a full-scale signal |
| As a gain error | 0.00012 dB: inaudible |

It matters for two reasons: a longer time constant or a higher sample rate makes it larger in
proportion (`k` shrinks), and a gain that never equals its target makes tests and "is it
settled" logic awkward. The block therefore checks once per block whether another step would
change the gain; if not, it sets the gain to the target. The step this makes is the stall
distance, at most.

Consequence: the output depends on the block size, but only at that one step and only by the
stall distance.

**2. The coefficient needs `expm1`.** For long time constants `exp(-1/(tau fs))` is close to 1.
Computing `1 - expf(x)` in float32 keeps only the digits that differ from 1, about five of them
at 5 ms and 48 kHz. `-expm1f(x)` keeps full precision (measured: relative error 5e-9 against the
float64 value). This is in init code, so its cost does not matter.

Overflow: none possible; the gain stays between its start and its target.

## Measured

| Item | Value | How |
|---|---|---|
| Error against the float64 reference, ramp in progress | under -120 dBFS | `test_ramp_matches_reference` |
| Error over a whole ramp | under -100 dBFS (the stall distance is -109) | `test_ramp_to_its_end_stays_within_the_stall_distance` |
| Settled gain | exactly the target | `test_settled_gain_is_exactly_the_target` |
| Cycles per sample on the M7 | not measured: no board attached | `bench` console command |

## Open questions

- At 96 kHz with a 50 ms time constant the stall distance is about 20 times larger (-83 dBFS).
  If a slow fade needs better, switch that use to a linear ramp or keep the gain in double
  precision.
- Whether the snap's step is ever audible on a pure low-frequency tone. By the numbers it is
  not; nobody has listened.
