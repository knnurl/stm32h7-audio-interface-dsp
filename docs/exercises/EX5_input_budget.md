# Exercise 5: the line input's level and noise budget

Batch 5, before reading stage 2's input numbers. Yours to do, by hand. Claude reviews it when you
ask and does not do it. There is no test file: you compare with `docs/notes/rev_a_input_budget.md`
afterwards (do not open it first).

## Why this one

The 0 dBFS level of the input is the one analogue choice that every recording on this device
inherits. Working its noise from the datasheets shows where the floor comes from (the ADC or the
front end), what headroom costs, and why "low-impedance design" is a number, not a slogan.

## The circuit (each channel, each leg the same)

```
TRS tip (hot) --100R--+--||-- C (large) --Rin--+--------+
                     470p to chassis, TVS      |        |
                                               +--|-\   |
                                    VCOMAD ------|+  >--+--47R--+-- VIN-  (hot leg drives VIN-)
                                                 OPA1678        |
                                               (Rf from out to -in, small Cf across it)
TRS ring (cold): the same circuit into VIN+.            ADC differential input, centred on VCOMAD
```

Each leg is an inverting stage with gain -Rf/Rin, its + input on the PCM3168A's VCOMAD (2.5 V,
10 uF to ground), its input AC-coupled, so its output sits at 2.5 V.

## Givens

- 0 dBFS at the input: **+20 dBu**, balanced (stage 2 proposal). Nominal level +4 dBu. 0 dBu =
  0.7746 V rms.
- PCM3168A (SBAS452A 8.5), VCCAD = 5.0 V: full-scale input 0.4 x VCCAD V rms differential;
  dynamic range 107 dB typical, A-weighted, differential, 48 kHz; CMRR 80 dB.
- OPA1678 (SBOS855E): 4.5 nV/rtHz at 1 kHz, 3 fA/rtHz; output swing to within 0.8 V of the
  rails into 2 k; rails +/-12 V.
- Resistor noise sqrt(4kTR), T = 298 K. A-weighted noise bandwidth for white noise, 20 Hz to
  20 kHz: 12.47 kHz.
- Constraint: input impedance at least 10 kohm per leg; E96 resistor values.
- Assume a source impedance of 100 ohm per leg or less.

## The task

1. Choose Rin and Rf. Give the differential gain and the exact dBu of 0 dBFS you end up with.
2. Headroom over +4 dBu, and how far above 0 dBFS the op-amps clip.
3. Noise at the ADC pins, per source and total, in uV(A); the same referred to the input in
   dBu(A).
4. The chain's dynamic range, and how much the front end costs against the ADC alone.
5. Signal-to-noise at nominal level.
6. Redo 1, 3 to 5 for 0 dBFS at +18 dBu and +24 dBu. Say which you would pick and why.
7. Common-mode rejection of the stage with 1 % resistors and with 0.1 %, worst case.

## Hand in

One page (in `docs/exercises/EX5_answers.md` or on paper): a table per question with the
arithmetic. Done when your numbers agree with `rev_a_input_budget.md` within 0.5 dB, or you can
say why they differ.

## Things to think about

- Which resistor dominates, and what happens if you double both Rin and Rf?
- Why does the input's dynamic range barely move with the 0 dBFS choice, while SNR at nominal
  does?
- An unbalanced source (TS plug, ring shorted to sleeve): what level reaches 0 dBFS, and what
  happens to the noise?
- Where would you put the 0.1 % resistors if you could afford only four per channel?
