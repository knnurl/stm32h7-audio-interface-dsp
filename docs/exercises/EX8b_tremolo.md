# Exercise 8b: the tremolo

Batch 8b. Yours to do. Claude reviews it when you ask and does not do it.

## Why this one

It is the smallest complete effect: an LFO, a gain law, a ramped parameter, stereo, and tempo
sync, all on the audio path with no allocation and no `math.h` per sample. Getting the phase
of a tempo-synced LFO exactly on the beat is the part that separates "works" from "works with a
drum machine".

## The task

Replace the pass-through stub in `dsp/src/dsp_fx_tremolo.c` with the effect that
`dsp/include/dsp/dsp_fx_tremolo.h` specifies:

- gain per channel g = 1 - depth (1 - u), u = (1 + lfo) / 2, applied as wet = g x (dry 0);
- the right channel reads the LFO `stereo_phase` cycles later (0.5 is an auto-pan);
- shapes sine, triangle and rounded square, from `dsp_lfo` (`dsp/include/dsp/dsp_lfo.h`);
- `sync(beats, beats_per_cycle, bpm)` sets the rate from the tempo and puts the loudest point
  (lfo = +1, phase 0.25) on every multiple of `beats_per_cycle` beats;
- depth changes ramp linearly over `DSP_FX_RAMP_MS` (`dsp_fx_common.h` has the ramp).

The reference model is `tremolo` and `tremolo_gain` in `tests/ref/fx.py`.

Then add a self-test case `fx_tremolo_f32` to `dsp/src/dsp_selftest.c`, as the other batch 8b
cases do, so the board run times it.

## Run

```
cmake --build --preset host-release
python -m pytest tests/exercises/test_ex8b_tremolo.py
```

The tests check the output against the reference for the three shapes, the depth range, the
auto-pan, the beat alignment, the rounded square's edges (no gain step faster than
depth pi / (2 edge P) per sample), and the depth ramp.

## Done when

All eight tests pass, the full suite still passes (`python -m pytest`), and you can say:

- how many cycles per stereo sample your version should take on the M7, before measuring it;
- why the gain law keeps 1 as its maximum rather than centring on 1 - depth / 2.

## Things to think about

- The video's (Tremolo Effect, #3) gain law is y = x (1 - depth + depth g) with a bipolar
  triangle g in [-1, 1]. At full depth that makes the gain go negative: what does that do to the
  sound, and why does this header use a unipolar u instead?
- Its triangle comes from a counter limited to fs / (4 f_LFO), an integer. How far off is a
  4.7 Hz rate at 48 kHz, and why does a 32-bit phase accumulator not have that problem?
- The LFO is evaluated twice per sample (left and right). Is it cheaper to evaluate it once and
  delay the right channel? What does that cost in memory at an auto-pan of 1/16 Hz?
