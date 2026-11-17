# Design note: biquad structures and number formats

Batch 3. Which structure each number format uses, and the measurement that settled which one the
equalisers use.

## Purpose

Every equaliser in the device (input strips, speaker and headphone stages, tone control) is a
cascade of second-order sections. The structure and the number format decide how much noise the
filter adds, whether it can overflow, and what it costs.

## The maths

H(z) = (b0 + b1 z^-1 + b2 z^-2) / (1 + a1 z^-1 + a2 z^-2). Every structure computes the same H in
exact arithmetic. They differ in where rounding happens and what the rounding noise passes
through on its way to the output.

## Structures, and why each format uses the one it does

| Kernel | Structure | Why |
|---|---|---|
| `dsp_biquad_f32_section` | Transposed direct form II, float32 | Two state words; the usual float choice |
| `dsp_biquad_f64_section` | Transposed direct form II, float in and out, double inside | The measured answer to float32's low-frequency noise (below) |
| `dsp_biquad_q31_process` | Direct form I, 64-bit accumulator, optional error feedback | The state is the input and output samples, which cannot overflow; one rounding per section |

**Q31 accumulator bound.** Coefficients are scaled by 2^(30 - shift). `dsp_coef_to_q31` picks the
smallest shift for which every coefficient fits in 32 bits and the sum of their magnitudes is at
most 2^32 - 1. Then |acc| <= (2^32 - 1) x 2^31 + 2^30 < 2^63, so the accumulator cannot overflow
for any input. A 20 Hz high-pass has |b0| + |b1| + |b2| + |a1| + |a2| close to 7, so it needs
shift 1 even though each coefficient alone would fit at shift 0. A first version required a
margin of 2^30 in that sum; that cost a whole bit for no reason and was corrected.

**Error feedback.** The bits shifted out of the accumulator are kept and added to the next
sample's accumulator. That gives the rounding error a zero at DC, and DC is where the noise gain
of a low-frequency section is largest.

## Numerical behaviour: the measurement

`docs/results/b3_filter_noise.md`, from `python tools/studies/b3_filter_noise.py`: signal-to-noise
of one section on a 1 kHz sine, arithmetic noise only.

| Filter (48 kHz, -1 dBFS) | f32 TDF-II | f32 DF-I | f64 TDF-II | q31 DF-I | q31 DF-I EF |
|---|---|---|---|---|---|
| High-pass 20 Hz | 67.8 | 74.4 | 153.0 | 128.3 | 185.3 |
| Peak 40 Hz, Q 10 | 74.4 | 68.0 | 153.0 | 115.2 | 159.9 |
| Tone bass shelf 100 Hz, +12 dB | 110.9 | 86.8 | 151.4 | 142.5 | 183.1 |
| Peak 1 kHz (for comparison) | 120.2 | 117.5 | 153.5 | clips | clips |

At 96 kHz float32 gets worse (the poles move closer to z = 1): 59 to 80 dB on the same filters.

**Why float32 is so poor here.** Rounding in a TDF-II state word reaches the output through
1 / A(z), which has a gain of 1 / (1 + a1 + a2) at DC. For a 20 Hz high-pass at 48 kHz that is
about 1.4 x 10^5 (+103 dB). Float32's relative precision is 2^-24 (-144 dB). Integrated over the
narrow band around the pole the noise gain is lower, and the arithmetic predicts about 70 dB of
signal-to-noise, which is what was measured. Direct form I in float32 is no better: its rounding
also passes through 1 / A(z).

**Why Q31 at -60 dBFS is poor without error feedback.** Fixed point has a fixed noise floor. A
-60 dBFS signal is 60 dB nearer to it, and the same 1 / A(z) gain lifts that floor. Error
feedback puts a zero where the gain is, and wins by about 60 dB.

**Why "clips".** Q31 has no headroom: a -1 dBFS sine through a +6 dB peak exceeds full scale.
Fixed-point gain stages need headroom planned in; float has about 750 dB of it.

## Decision (provisional)

The PEQ and the tone control run their sections in double (`dsp_biquad_f64_section`): about
152 dB everywhere, which is the float32 output's own rounding. Fixed point with error feedback
would do as well but would need conversions and headroom planning around it. The float32 kernel
stays for mid- and high-frequency uses and as the benchmark baseline.

This is provisional until the M7 cycle counts exist (batch 3, target part). Double multiply and
add on the Cortex-M7 take more cycles than single precision [Verify on the board]. If the cost
is too high, the fallbacks are: double only for sections with a corner below about fs/200, or
Q31 with error feedback for those.

## Test evidence

| Test | Result |
|---|---|
| Q31 bit-exact against the Python integer model, both rounding modes, including saturation and the extreme accumulator case | `tests/unit/test_biquad.py` |
| Float32 cascade with a 30 Hz high-pass against float64 | -79 dBFS measured; held to -75 dBFS |
| Float32 mid-frequency sections | within -110 dBFS |
| Double-state cascade | within -135 dBFS (the float output rounding) |
| 60 random designs at -30 dBFS: finite, no saturation | pass |

## Cycles on the M7

Not measured: no board yet. The self-test cases `biquad_f32`, `biquad_q31_round`,
`biquad_q31_ef`, `biquad_f64` (the same cascade in double) and `tone_f32` give them with
`python tools/target_test.py`; `biquad_f32` against `biquad_f64` is the cost of double.

## Open questions

- The cost of double on the M7, which decides whether the provisional decision stands.
- Whether the noise of the float32 kernel matters for the speaker stage's PEQ, whose corners are
  usually above 50 Hz. The study's 1 kHz row (120 dB) says probably not.
