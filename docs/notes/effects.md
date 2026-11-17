# Design note: the effect slot and its eight effects

Batch 8b. `dsp_fxslot`, `dsp_fx_echo`, `dsp_fx_mod` (chorus, flanger, phaser),
`dsp_fx_tremolo` (the owner's exercise), `dsp_fx_colour` (sweep filter, overdrive, bit crusher).

## Purpose

One creative effect at a time on the monitor mix (SPEC 2), after the mixer and before the record
tap, chosen with FX SELECT, switched with FX ON, driven by the FX AMOUNT knob, with no clicks.

## The FX AMOUNT macro (8b.0, the owner's table; built as proposed)

| Effect | FX AMOUNT does | Dry gain | Other parameters |
|---|---|---|---|
| Echo | wet level 0 to 1 | 1 | time (ms, from a note value and the tempo), feedback 0 to 0.95, tone, ping-pong |
| Chorus | depth 0 to 7 ms and wet 0 to 0.7, together | 1 | rate, stereo spread |
| Flanger | sweep span, 0.5 ms to 0.5 + 9.5 ms | 0.7 | rate or tempo, feedback -0.9 to 0.9 |
| Phaser | sweep span, 0 to 5 octaves above 200 Hz | 0.5 | rate or tempo, 4 or 8 stages, feedback -0.9 to 0.9 |
| Tremolo | depth 0 to 1 | 0 | rate or tempo, shape, edge, stereo phase |
| Sweep filter | position: low-pass below the middle, high-pass above, off in a +/-3 % dead zone | 0 | resonance |
| Overdrive | drive 0 to 36 dB, level-compensated | 0 | tone, symmetric or asymmetric, output level |
| Bit crusher | moves bits and rate from transparent to their settings | 0 | bits, rate, dither |

Every macro is ramped over 10 ms (`DSP_FX_RAMP_MS`), so a knob read at block rate does not
zipper.

## The slot

out = g_dry x + g_wet E(g_in x), the three gains moving linearly over 30 ms.

- **One effect runs, never two.** A change is a fade out, then a clear, then a fade in, not a
  cross-fade: the cycle budget (SPEC 3.4) counts the dearest single effect, and a cross-fade
  would need two. The cost is a gap of about 60 ms plus the clear in which only the dry plays.
- **Trails.** Off with trails on (the default) fades the input out of the effect and lets its
  tail ring for effects with a dry path; the slot stops the effect once the tail has been under
  -100 dBFS for 0.5 s. Effects with no dry path have no tail to keep and fade out.
- **Clearing.** An effect never starts with stale memory: the pool region it last used is zeroed
  before the next start, 2048 floats per 16-frame chunk, so the full echo pool at 96 kHz takes
  about 12 ms and no block ever does unbounded work.
- **Bug found by the click test:** starting a delay effect with its input at full gain made the
  cleared line deliver the onset of the delayed signal as a step 10 to 500 ms later, in the
  middle of the wet fade: a second difference 9.5 times the steady value. The input now fades in
  with the wet. After the fix the worst transition is 1.13 times the steady value
  (`test_switching_makes_no_click`).
- **Trails decay at the set feedback:** echo at 100 ms, feedback 0.5, bright tone: successive
  repeats fall by 0.4951 to 0.4961 against 0.4953 expected from the feedback and the loop
  filters' gain at 1 kHz (`test_echo_trails_decay_at_the_set_feedback`).

## The effects

### Echo
Feedback comb with a tone filter in the loop: r = line[d], line <- x + fb hp(lp(r)), wet = a r.
Ping-pong sums the input into the left line and cross-feeds. The time glides over 50 ms when it
changes, bending the pitch of what is in the line as a tape echo does; the proposed choice, with a
cross-fade (no bend) as the owner's alternative. **Bug found by the glide test:** accumulating
the glide step in float32 drifted 0.42 samples over 2400 steps and then jumped to the target; the
delay is now computed from the target back. Matches its model to -110 dB.

### Chorus
Two voices per channel, half a cycle apart, at 20 ms +/- 7 ms x amount; the right channel's
voices offset by spread / 4 cycles. Matches its model to -85 dB, the limit set by float32 read
positions near 1000 samples (`docs/notes/delay_lines.md`).

### Flanger
One delay per channel swept by a triangle between 0.5 ms and 0.5 + 9.5 x amount ms, feedback
-0.9 to 0.9; dry and wet both 0.7, so the notches are complete. The loop gain is at most 0.9, so
the wet is bounded by 0.7 / (1 - 0.9) (`test_flanger_feedback_stays_bounded`).

### Phaser
4 or 8 first-order all-passes, swept exponentially from 200 Hz; feedback from the chain's output.
Dry 0.5 and wet 0.5 give notches where the chain reaches -180 degrees: under -40 dB measured
with the sweep stopped (`test_phaser_makes_notches`).

### Tremolo
The owner's exercise (`docs/exercises/EX8b_tremolo.md`). The header uses a unipolar LFO so the
gain stays in [1 - depth, 1]; see "From the transcripts".

### Sweep filter
The SVF of `docs/notes/modulated_filters.md`. Low-pass from 20 kHz at the dead zone's edge down
to 50 Hz, high-pass from 20 Hz up to 10 kHz, both exponential in the position. Over the 0.07 of
travel next to the dead zone the output fades from the input to the filter, so entering and
leaving the dead zone is continuous. Turned end to end in 2 s on a 1 kHz sine, the largest
sample-to-sample step is 0.071, against 0.065 for the sine itself (`test_sweep_moves_without_steps`).

### Overdrive
High-pass at 100 Hz, optional bias for asymmetry, tanh at 4x (batch 6), a 10 Hz DC blocker, a
tone low-pass, level compensation. Harmonics of a -12 dBFS 1 kHz sine match a continuous-time
model of the chain within 0.2 dB (`test_overdrive_harmonics_match_the_model`); symmetric: H2
below -138 dB; asymmetric: H2 at -19 dB. Level compensation keeps a -18 dBFS sine within
0.13 dB from 0 to 36 dB of drive. Latency 46.5 samples; the dry path has none, so the slot's
30 ms fade comb-filters briefly when it switches the overdrive in or out.

### Bit crusher
Sample-and-hold driven by a float32 phase accumulator, then rounding to 2^-(bits - 1) steps,
optional TPDF dither. At amount 0 it is a 16-bit quantiser, within half an LSB of the input.
Matches its model bit for bit when the model is given the C code's step and increment.
NaN is clamped before the integer conversion, which would otherwise be undefined.

## Numerical behaviour and test evidence

`tests/unit/test_fx.py` (33 tests) and `tests/unit/test_fxslot.py` (8). Models in
`tests/ref/fx.py`. When a test failed, the cause was found before anything changed:
- **Code, twice:** the glide drift and the slot's click (above).
- **Models:** the overdrive model used an analogue one-pole magnitude for a digital filter
  (0.06 dB of drive); the chorus and flanger models used an exact sine where the header
  specifies the polynomial LFO (its 8e-7 error times a 336-sample depth is -71 dB); the crusher
  model computed the step and rate exactly where the header specifies the fast exp2.
- **Test expectations:** a guessed Lagrange bound (replaced by the exact formula); a phaser
  check that left the LFO running and read the bin above DC; a dead-zone boundary sampled exactly
  where float32 and float64 round apart; the slot's repeat ratios measured by sample peaks
  (jitter of 1 %, now RMS); an impossible "echo unavailable" case; an off-by-one in the clearing
  count.

## Cycles on the M7

Not measured. `docs/results/b8b_cycles.md` lists the self-test case for each effect. The
overdrive (two 4x oversamplers, 8 tanhf per stereo sample) is expected to be the dearest by far.

## From the transcripts

Read in full on 2026-11-17: Comb Filters and Delay Lines (#124), Delay-Based Audio FX (#140),
Tremolo Effect (#3). Read in full for batches 3 and 6 and re-read where they bear on the phaser
and the overdrive: All-Pass Filter (#162), DSP Overdrive (#117), Asymmetrical Clipping (#153).
Recursive RMS (#103) is listed for batch 8 but concerns metering (batch 8c).

**Agrees**
- #140: the echo is a feedback (IIR) comb; stable for |g| < 1; a filter in the feedback path
  makes repeats darker ("analogue"); feedback near 1 never decays. Ours clamps at 0.95.
- #140: abrupt changes of mix, feedback or length click; smooth them or change them only when
  safe. Ours ramps every macro, glides the time, and fades the slot.
- #140: the matrix feedback network (its DAFX figure) is the basis of reverbs: our reverb.
- Tremolo: the effect is amplitude modulation, and its spectrum shows sidebands at f +/- f_LFO
  (and more for a triangle). Depth is the strength.
- #153: a high-pass before the clipper keeps the low end from muddying it; asymmetry adds even
  harmonics. Ours does both; measured H2 at -19 dB with the bias.

**Differs, and why**
- #140 mixes as (1 - m) x + m wet. For monitoring, turning the echo up should not turn the music
  down, so ours keeps the dry at 1 and the macro sets the wet level.
- #140 clamps the output to +/-1 inside the effect. Ours does not: the limiter after the tone
  stage protects the outputs, and a clamp here would distort the tails.
- Tremolo: the video's gain is (1 - depth) + depth g with g a bipolar triangle in [-1, 1], so at
  depth above 0.5 the gain goes negative: the polarity flips each half-cycle (the
  "over-modulation" seen on its scope). Ours uses u = (1 + g) / 2, keeping the gain in
  [1 - depth, 1]. The captions also put the LFO "on the order of 100 Hz"; the video then uses 1
  to 20 Hz, which is the tremolo range; ours follows the latter.
- #117 does not oversample; ours runs the overdrive at 4x (batch 6's aliasing study).
- #153 does not mention that an asymmetric curve's output carries DC; ours removes it with a
  10 Hz high-pass.

**Suggested and not done**
- #140: band-splitting the input into several delays (its DAFX figure). Not in the effect list.
- #140: external SDRAM for long delays. No; the 8b.6 options are internal.
- #117's piecewise quadratic curve, cheaper than tanh: kept as the first saving if the
  overdrive's cycles are over budget.

## Open questions (for the owner)

1. The macro table above (8b.0): built as proposed; change any row.
2. Synced echo time changes: glide (built) or cross-fade.
3. The echo's maximum time and storage, from the memory table (8b.6).
4. A change of effect leaves about 60 ms of dry only (fade out, clear, fade in). Acceptable, or
   should the budget allow two effects during a cross-fade?
