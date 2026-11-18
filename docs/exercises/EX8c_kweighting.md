# Exercise 8c: the K-weighting filter

Batch 8c. Yours to do. Claude reviews it when you ask and does not do it.

## Why this one

Every loudness number the device shows goes through this filter, and the standard only gives its
coefficients at 48 kHz. The device runs at 44.1, 48, 88.2 and 96 kHz. Getting from "a table of
numbers at one rate" back to "a filter I can design at any rate" is a routine job in audio DSP,
and the place where bilinear-transform warping stops being theory.

## The task

Replace the stub in `dsp/src/dsp_kweight.c` with the function that
`dsp/include/dsp/dsp_kweight.h` specifies:

- `dsp_kweight_design(sample_rate_hz, sections)` fills two normalised biquad sections: the
  pre-filter (a high shelf of about +4 dB) and the RLB high-pass (about 38 Hz), in that order;
- at 48 kHz, the coefficients ITU-R BS.1770-4 publishes (its tables 1 and 2), within 1e-8;
- at any rate from 32 to 192 kHz, a re-derived design whose response is within 0.05 dB of the
  48 kHz filter's from 20 Hz to 20 kHz (below 0.45 of the rate);
- returns 0, or -1 for a rate outside 32 to 192 kHz with the sections left untouched.

It runs at the control level, so the C library's maths (`tan`, `pow`, `sqrt`) is fine. Double
precision throughout; the meter rounds the result to float.

Once it passes, `dsp_meter` uses it on its own (`dsp_meter_f32_init` calls it), and the meter's
reading says `kweighted=1`.

## Run

```
cmake --build --preset host-release
python -m pytest tests/exercises/test_ex8c_kweight.py
```

The tests check the 48 kHz coefficients against the published ones; the response at 32, 44.1,
88.2, 96 and 192 kHz against the 48 kHz response; the refused rates; and EBU Tech 3341 case 1
(a 1 kHz sine at -23 dBFS in both channels reads -23.0 LUFS within 0.1 LU) through the meter at
44.1, 48 and 96 kHz.

## Done when

All twelve tests pass, the full suite still passes (`python -m pytest`), and you can say:

- what analogue filters the published 48 kHz sections came from, and how you found out;
- why reusing the 48 kHz coefficients at 96 kHz is wrong by about 10 dB somewhere, and where;
- how close your 96 kHz design gets, and what limits it.

## Things to think about

- The pre-filter is a shelf. A shelf has a corner, a gain and a Q, but the published numbers fix
  more than three things. What is the fourth, and does it matter at other rates?
- Bilinear transform with prewarping matches the response exactly at one frequency. Which
  frequency should that be for each section, and what happens near Nyquist at 32 kHz?
- The RLB high-pass sits at 38 Hz. At 96 kHz its poles are very close to z = 1. The meter runs it
  in float32 (`dsp_biquad_f32_section`). Does that matter for a meter, given
  `docs/results/b3_filter_noise.md`?
- The video Recursive RMS (#103) keeps a running sum of squares and subtracts the sample leaving
  the window. The meter does not: it sums each 100 ms block afresh in double. Why is that the
  better choice for a 3 s window at 96 kHz in float32?
