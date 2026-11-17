# Design note: the reverb

Batch 8b. `dsp_reverb`.

## Purpose

A room for the monitor mix, on the mixer's send and return (not in the effect slot), so a singer
or player hears themselves in a space without the PC in the loop.

## The maths

An 8-line feedback delay network (Jot and Chaigne). Per sample:

- s_i: line i read at its length L_i (lines 2 and 6 at L_i +/- 0.3 ms, at 0.31 and 0.43 Hz);
- f_i = b0_i s_i + a1_i f_i[n - 1]: the absorbent filter, a one-pole low-pass per line;
- v = H f / sqrt(8), H the 8 x 8 Hadamard matrix (fast transform: 24 additions);
- line_i <- v_i plus the pre-delayed input, left into the even lines and right into the odd,
  with alternating signs;
- outputs: two orthogonal sign patterns over the s_i, times 0.35.

The absorbent filter makes each line lose 60 dB in T_lo at DC and in T_hi at 8 kHz (owner's
decision 2026-11-17; it was Nyquist), with g = 10^(-3 L / (fs T)) for each. For
H = b0 / (1 - a1 z^-1) with b0 = g_lo (1 - a1), the ratio r = g_hi / g_lo at w = 2 pi 8000 / fs
fixes a1 through A a1^2 + B a1 + A = 0, A = r^2 - 1, B = 2 (1 - r^2 cos w); the roots are
reciprocal, and the one used, a1 = -2A / (B + sqrt(B^2 - 4A^2)), lies in [0, 1) for every
0 < r <= 1 (the discriminant is 4 r^2 (1 - cos w)(2 - r^2 (1 + cos w)) >= 0). The filter's
peak is its DC gain g_lo < 1, so the loop gain stays below 1. Above 0.45 fs the anchor moves
down to 0.45 fs (a 16 kHz self-test rate). Because each line's loss is proportional to its
length, all eight decay at the same rate at every frequency.
b0 is computed from the float32 value of a1, not the double: with a1 near 1 (20 s low, 0.05 s
high, 96 kHz) rounding a1 alone moved the DC gain, and T_lo by 0.35 % (found by
`test_high_decay_is_anchored_at_8_khz`); now the DC gain is exact.

## Structure, and what was rejected

- **Hadamard, not Householder.** Both are orthogonal (the loop is lossless before the filters)
  and cheap. A Householder matrix of order 8 keeps 0.75 of each line in itself on every pass;
  every Hadamard entry is +/-1/sqrt(8), so each pass spreads every line into all eight. With the
  Nyquist-anchored filters the float64 model showed Hadamard clearly ahead (echo density 0.9 at
  405 ms; Householder not within 0.5 s). **That evidence did not survive the 8 kHz anchor:**
  with it (2.0 / 1.0 s, no modulation) the density at 50, 100, 150, 200 and 300 ms is
  0.08, 0.27, 0.54, 0.78, 0.83 for Hadamard and 0.08, 0.30, 0.52, 0.62, 0.84 for Householder,
  and Householder first reaches 0.9 sooner (315 against 335 ms). The claim that Hadamard builds
  density faster is withdrawn; Hadamard stays for its even mixing at the same cost, and the
  matrix is an open question for listening (`test_matrix_choice` prints the comparison).
- **Lengths:** 19.3 to 47.9 ms, each rounded up to a prime number of samples, so they are
  mutually prime at every rate (`test_lengths_are_distinct_primes` at 44.1, 48 and 96 kHz).
- **Modulation of two lines,** through Lagrange reads, against the metallic ringing of fixed
  lengths. It also helps density (190 ms to 0.9 with it, measured in C at 2.0 / 1.0 s).
- **Rejected for now: input diffusers** (a chain of all-passes before the network, as #162
  suggests for reverbs), which would raise the early density further. A cycle cost with no
  requirement behind it yet; an open question.

## Numerical behaviour and test evidence

| Measurement | Value | Test |
|---|---|---|
| T60, octaves at 500 Hz / 4 kHz / 8 kHz, set 2.0 / 0.8 s | designed 1.982 / 1.400 / 0.886 s, measured 1.924 / 1.444 / 0.888 s | `test_decay_time_by_schroeder_integration` |
| Same, set 1.0 / 1.0 s | designed 1.000, measured 0.972 / 1.001 / 0.951 s | same |
| Same, set 4.0 / 1.5 s | designed 3.963 / 2.768 / 1.705 s, measured 3.979 / 2.696 / 1.646 s | same |
| Decay at DC and at 8 kHz from the coefficients, 44.1, 48, 96 kHz, three settings | within 0.2 % of T_lo and T_hi | `test_high_decay_is_anchored_at_8_khz` |
| 60 s at 20 s / 20 s | each second 2.86 to 3.2 dB below the last, mean 3.07 dB (3.0 expected); never grows | `test_no_growth_over_a_minute_at_the_longest_decay` |
| Echo density 0.9 | 190 ms (0.40 at 100 ms, 0.94 at 200 ms, 1.04 at 400 ms) | `test_echo_density` |
| Left/right correlation of the impulse response | 0.011 | `test_left_and_right_are_decorrelated` |
| Against the float64 model, modulation off | within -100 dB | `test_matches_the_model_without_modulation` |
| Pre-delay | 0 to 50 ms, exact to the sample; 80 ms clamps to 50 | `test_predelay` |
| Memory at 96 kHz | 35 718 floats (140 KB), of which the 50 ms stereo pre-delay is 38 KB | `docs/results/b8b_memory.md` |

Schroeder: the impulse response is filtered to an octave band, integrated backwards, and the
slope between -5 and -25 dB extrapolated to -60 dB. The design value it is compared with is
computed the same way: each frequency in the band decays at its designed rate, weighted by the
band filter, then integrated and fitted. Comparing a band with the design at its centre was
wrong where the decay changes fast across the band: the 8 kHz octave (5.7 to 11.3 kHz)
measured 11 % long against its centre value, because the slower lower half dominates the late
energy. The plan's tolerance is 10 %; the worst measured against the band design is 3.5 %.

## Cycles on the M7

Not measured. Self-test case `reverb_f32` (at 16 kHz, so its lines fit the shared self-test
pool).

## From the transcripts

None of the batch 8b transcripts implements a reverb. Read in full on 2026-11-17: #124, #140,
Tremolo; #162 re-read.

**Agrees**
- #140 shows the multiple-input multiple-output delay network with matrix feedback (its DAFX
  figure) and says it "forms the basis of many reverbs": this structure.
- #124: a comb's peaks sit at multiples of 1 / Td. With eight mutually prime lengths the combs'
  peaks do not line up, which is why the lengths are primes.
- #162: all-pass filters are building blocks of reverbs. Not used here (above).

**Differs, and why**
- #124 and #140 build combs from integer delay lines at fixed lengths. Ours modulates two lines
  with fractional reads, which the measurement shows doubles the early echo density.

**Suggested and not done**
- All-pass diffusers before the network (#162's hint).

## Open questions

1. Input diffusers, if the early density sounds grainy on the owner's speakers (open until he
   listens).
2. Hadamard or Householder: the measured density difference is now small and mixed (above).
Decided 2026-11-17: pre-delay up to 50 ms, stereo; T_hi anchored at 8 kHz.
