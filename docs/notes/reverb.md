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

The absorbent filter makes each line lose 60 dB in T_lo at DC and T_hi at Nyquist:
g = 10^(-3 L / (fs T)) for each, a1 = (g_lo - g_hi) / (g_lo + g_hi), b0 = g_lo (1 - a1).
Because each line's loss is proportional to its length, all eight decay at the same rate, and
the decay time moves smoothly between T_lo and T_hi in between.

## Structure, and what was rejected

- **Hadamard, not Householder.** Both are orthogonal (the loop is lossless before the filters)
  and cheap. A Householder matrix of order 8 keeps 0.75 of each line in itself on every pass;
  every Hadamard entry is +/-1/sqrt(8), so each pass spreads every line into all eight. Measured
  on the float64 model with the same lengths and filters, no modulation: normalised echo density
  reaches 0.9 at 405 ms with Hadamard, and not within 0.5 s with Householder
  (`test_matrix_choice`).
- **Lengths:** 19.3 to 47.9 ms, each rounded up to a prime number of samples, so they are
  mutually prime at every rate (`test_lengths_are_distinct_primes` at 44.1, 48 and 96 kHz).
- **Modulation of two lines,** through Lagrange reads, against the metallic ringing of fixed
  lengths. It also helps density: 195 ms to 0.9 with it, 405 ms without (both measured).
- **Rejected for now: input diffusers** (a chain of all-passes before the network, as #162
  suggests for reverbs), which would raise the early density further. A cycle cost with no
  requirement behind it yet; an open question.

## Numerical behaviour and test evidence

| Measurement | Value | Test |
|---|---|---|
| T60 at 500 Hz, set 2.0 / 0.8 s | designed 1.996 s, measured 1.937 s (-3.0 %) | `test_decay_time_by_schroeder_integration` |
| T60 at 4 kHz, set 2.0 / 0.8 s | designed 1.788 s, measured 1.787 s | same |
| T60 at 500 Hz and 4 kHz, set 1.0 / 1.0 s | 0.972 s, 1.001 s | same |
| T60 at 500 Hz and 4 kHz, set 4.0 / 1.5 s | 4.001 s (designed 3.992), 3.433 s (designed 3.564, -3.7 %) | same |
| 60 s at 20 s / 20 s | each second 2.86 to 3.2 dB below the last, mean 3.07 dB (3.0 expected); never grows | `test_no_growth_over_a_minute_at_the_longest_decay` |
| Echo density 0.9 | 195 ms (0.37 at 100 ms, 0.89 at 200 ms, 0.99 at 400 ms) | `test_echo_density` |
| Left/right correlation of the impulse response | 0.011 | `test_left_and_right_are_decorrelated` |
| Against the float64 model, modulation off | within -100 dB | `test_matches_the_model_without_modulation` |
| Memory at 96 kHz | 45 318 floats (177 KB), of which the 100 ms stereo pre-delay is 75 KB | `docs/results/b8b_memory.md` |

Schroeder: the impulse response is filtered to an octave band, integrated backwards, and the
slope between -5 and -25 dB extrapolated to -60 dB. The plan's tolerance is 10 %; the worst
measured is 3.7 %.

**T_hi is the decay at Nyquist,** not at 4 kHz. With the one-pole absorbent filter the decay at
4 kHz stays close to T_lo (1.79 s for 2.0 / 0.8): a "high-frequency decay" knob would feel weak.
Anchoring T_hi at 8 kHz instead, or a second-order absorbent filter, is an open question.

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

1. The pre-delay's maximum: 100 ms costs 75 KB at 96 kHz; 50 ms, or one mono pre-delay, halves it.
2. T_hi anchored at Nyquist or at 8 kHz (above).
3. Input diffusers, if the early density sounds grainy on the owner's speakers.
