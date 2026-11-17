# Design note: delay lines, interpolation and the LFO

Batch 8b. `dsp_delayline`, `dsp_lfo`.

## Purpose

The two building blocks of every time-based effect: a delay line that can be read at a
fractional, moving position (echo glide, chorus, flanger, reverb modulation), and a
deterministic LFO that can be locked to a tempo.

## The maths

- Delay line: after pushing x[n], a read at delay d returns x[n - d]. Fractional reads, with
  i = floor(d) and f = d - i:
  - linear: x[n - i] + f (x[n - i - 1] - x[n - i]);
  - third-order Lagrange on the four samples at offsets i - 1 .. i + 2, evaluated at f;
  - first-order all-pass: y = eta (s[n] - y[n - 1]) + s[n - 1], s the integer-delayed signal,
    eta = (1 - f) / (1 + f), with f kept in [0.5, 1.5) so eta stays away from the pole at -1.
- A read before a write delays by one more sample: the effects read at d - 1 for a delay of d.
- LFO: a 32-bit phase accumulator, one cycle = 2^32; increment round(f / fs x 2^32). The sine
  is an odd degree-7 polynomial on a quarter cycle, fitted with its value at the peak forced to 1.

## Structure, and what was rejected

- **Any length, not a power of two** (the plan said power of two). A mask would round the 0.75 s
  echo line at 96 kHz (72 000 samples) up to 131 072, nearly doubling the largest buffer in the
  device when the memory budget is already over (`docs/results/b8b_memory.md`). The wrap is one
  compare and add per read [Verify the cycle difference on the M7].
- **Caller-provided memory.** Every buffer is a pointer and a length at init, so the 8b.6 memory
  decision (16-bit echo, 48 kHz echo, SRAM1) changes the caller, not the blocks. The effect slot
  shares one pool between the echo, chorus and flanger, since only one runs.
- **Lagrange for every modulated read.** The study decides it (below): 20 to 50 dB better than
  linear on a swept delay for about 10 multiplies instead of 1. The all-pass is flat in
  magnitude but its state makes a moving read worse than linear at low frequencies.
- **LFO by phase accumulator, not a counter.** The tremolo video builds its triangle from a counter
  limited to fs / (4 f), an integer, so the rate is quantised and the phase cannot be set to a
  beat. The accumulator's rate resolution is fs / 2^32 and its phase can be set exactly.
- **Rejected: a recursive sine oscillator** (two multiplies per sample): it cannot be re-phased
  cheaply and its amplitude drifts in float32.

## Numerical behaviour

From `python tools/studies/b8b_interp.py` (`docs/results/b8b_interp.md`), through the C code:

| Swept delay, 20 ms +/- 5 ms at 2 Hz | Linear | Lagrange 3 | All-pass 1 |
|---|---|---|---|
| 100 Hz | -96.2 dB | -145.4 dB | -81.4 dB |
| 1 kHz | -56.3 dB | -106.3 dB | -61.2 dB |
| 5 kHz | -28.3 dB | -50.6 dB | -36.0 dB |
| 10 kHz | -16.5 dB | -27.4 dB | -19.5 dB |

At a fixed half-sample fraction the responses are exactly the textbook ones: linear
cos(w / 2) (-3.01 dB at fs / 4), Lagrange (9 cos(w / 2) - cos(3 w / 2)) / 8 (-1.07 dB at
fs / 4), all-pass flat (`test_interpolator_magnitude_at_half_a_sample`).

- **Read position resolution.** A float32 delay of about 1000 samples resolves 6.1e-5 samples, so
  a modulated read near 20 ms differs from a float64 model by about -90 dBFS on full-scale noise.
  The effect tests state that limit (-85 dB) rather than -100.
- **LFO.** Sine error 7.9e-7 (-122 dB) against `sin`; peaks exactly 1. Rate exact to the integer
  increment; phase after N samples is N x inc mod 2^32 exactly (`test_rate_is_exact_and_deterministic`).
  Drift from rounding the increment is at most 0.5 / 2^32 cycles per sample, 0.04 cycles in an
  hour at 96 kHz: a synced LFO is re-phased from the tempo's beat position, not left running.
- **NaN delays** cannot reach memory: every fractional read clamps first, and NaN goes to the
  lower bound (`test_bad_delays_stay_in_bounds`).

## Cycles on the M7

Not measured. Self-test case `delay_lagrange_f32`.

## From the transcripts

Read in full on 2026-11-17: Comb Filters and Delay Lines (#124), Delay-Based Audio FX (#140),
Tremolo Effect (#3). They are automatic captions of videos made on an STM32H7 guitar pedal at
32 to 192 kHz; numbers and formulas below were checked; where they differ from ours, ours win.

**Agrees**
- #124: a delay line is a circular buffer; K = Td fs samples; read the oldest sample, then
  overwrite it with the input, then advance and wrap. Ours is the same, with the read-before-write
  costing one sample of delay, which the effects compensate.
- #124: the feed-forward comb y = a x[n] + b x[n - K] has |H| = sqrt(a^2 + b^2 + 2 a b cos(2 pi f Td)),
  peaks at n / Td and notches at (2n + 1) / (2 Td). Checked algebraically (|a + b e^(-jwK)|^2);
  it is the flanger's and chorus's response at any instant.
- #140: a 1 s mono line at 48 kHz in float is 48 000 x 4 bytes, "190 kilobytes" in the
  captions: 187.5 KiB exactly. Its remedies (external memory, a lower rate, 16-bit storage,
  decimating before the delay) are the 8b.6 options.

**Differs, and why**
- #124 and #140 compute the length by casting ms x fs / 1000 to an unsigned integer, which
  truncates rather than rounds, and allocate every line at a fixed maximum. Ours takes caller
  memory of any length and reads fractionally.
- #124's captions call the comb's delayed term "a previous output sample"; the equation shown
  is in input samples (it is the FIR comb). Noted so nobody copies the wording.
- #140 changes the delay time by moving the wrap point, which jumps the read position; ours
  glides the read position (the echo) or moves it continuously (the modulation effects).
- The tremolo video's LFO comes from a counter, rate-quantised and not phase-settable (above).

**Suggested and not done**
- #124's integer delays are enough for a static comb. Not done: every read here may be
  fractional, at Lagrange cost; an integer fast path for the echo's resting time is a possible
  optimisation once the cycles are measured.

## Open questions

- Decided 2026-11-17: the echo's lines are 16-bit (`DspDelaylineS16`), with its core at
  48 kHz at most; noise and the rounding rule are in `docs/notes/effects.md`. The float line
  stays for the chorus, flanger and reverb, whose modulated reads and short lengths do not need
  the saving.
