# Exercise 1: a DC blocker

Batch 1. Yours to write. Claude reviews it when you ask and does not write it.

## Why this one

Converters and some effects leave a small constant offset on the signal. It wastes headroom and
makes a click when a gain changes. The fix is the smallest useful recursive filter, and it takes
you through the whole route once: header, kernel, reference, host test, target benchmark.

## The task

Implement the three functions in `dsp/src/dsp_dcblock.c` (they are stubs now). The header
`dsp/include/dsp/dsp_dcblock.h` is fixed.

```
y[n] = x[n] - x[n-1] + r * y[n-1]        r = 1 - 2 * pi * cutoff_hz / sample_rate_hz
```

Rules: no allocation, no library calls in `process`, state only in the struct, `in` and `out`
may be the same buffer.

## Done when

```
cmake --build --preset host-release
python -m pytest tests/exercises/test_ex1_dcblock.py
```

passes all six tests:

| Test | What it checks |
|---|---|
| `test_pole_radius` | `init` computes `r` to within 1e-6 |
| `test_matches_reference_on_noise` | Within -110 dBFS of `tests/ref/dcblock.py` over 8192 samples |
| `test_removes_dc` | A constant 0.5 is below -60 dBFS after one second |
| `test_passes_1_khz` | Gain at 1 kHz within 0.01 dB of unity |
| `test_reset_clears_the_state` | `reset` clears the history and keeps `r` |
| `test_in_place_and_block_size` | In-place, 16 samples at a time, equals one call |

## Then, on the board

1. Add a self-test case for it in `dsp/src/dsp_selftest.c`, next to `gain_f32`: noise at half
   scale plus an offset of 0.25, cutoff 10 Hz at 48 kHz.
2. Add a check of that case to `tests/unit/test_selftest.py`.
3. Rebuild both sides, flash, and run `python tools/target_test.py --port COMx`.
4. Write the cycles per sample into the header comment.

## Things to think about while you do it

- Where is the zero, where is the pole, and what is the -3 dB frequency as a function of `r`?
- The formula for `r` is an approximation. How far off is the cutoff at 10 Hz, and at 1 kHz?
- The tolerance is -110 dBFS, not -120. Why does this filter lose more precision in float32
  than the gain did? What happens to that as the cutoff goes down or the sample rate goes up?
- What would a Q31 version need that the float one does not?
