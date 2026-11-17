# Progress

The handoff log, newest entry first. Each entry: what was done, the transcripts read (or
"none listed"), measured numbers, exact commands, what the owner decides or does next. A batch
entry with no transcripts line is unfinished.

## 2026-11-17: budget round 2 on the board (owner: "keep on")

**Transcripts read:** none (no new block).

Done and measured on the M7 (`docs/results/budget_target.md`), every case still matching the PC:
- saturation at 2x in the strips (default) and the overdrive: overdrive 2479 to 1284 cycles;
- a sample-peak mode for the limiter, for the headphones: 214 cycles against 665 true-peak;
- the budget rule in the control core: the overdrive and strip saturation never together
  (`err 10`; tried on the board);
- a true-peak detector built for the job (63-tap Nyquist interpolator, three 16-tap phases,
  `tools/design/tp_detector.py`): limiter 998 to 665, latency L + 24 to L + 9, true peak still
  0.24 dB under the set ceiling.
Not done: float32 PEQ sections (the worst case lets every band below 1 kHz; about 300 cycles).

Found on the way: the tests' true-peak measurement read the cut edges of its slice (up to 0.77 dB
of ringing); fixed, and the batch 6 worst case did not change. My figure of "about 3 dB" for the
sample-peak overshoot was right only after that fix (3.03 measured, 3.01 in theory).

**Correction of my last report:** I said options 1, 3 and 6 "should fit". I had not added them
up; they do not. Worst case now about 7400 cycles per frame at 48 kHz against a ceiling of 5833.
Unit tests: 522 pass.

**For the owner: what closes the last 1600 cycles**
1. Run the reverb on the M4 (my recommendation). It is a send effect, so a block of latency is
   inaudible; it is float32 throughout, which suits the M4's single-precision FPU; it frees 898
   cycles on the M7. It brings part of batch 11 (the dual-core work) forward.
2. Also the headphone stage on the M4 (828): with the reverb, about 5700 on the M7, under the
   ceiling; the M4 would then carry about 1700 M7-equivalent cycles [Verify the M4's cycles].
3. Or accept a higher ceiling (85 %: 7083) for a worst case that has every option on at once.
4. Your exercise EX6 (a shorter half-band filter) still cuts the strip saturators and the
   echo's 96 kHz path.

## 2026-11-17: budget round 1 on the board (owner's go on five steps)

**Transcripts read:** none (no new block).

Measured before and after each step, all on the Nucleo; every case still matches the PC (the
`tanhf` cases now bit-identical too). Details: `docs/results/budget_target.md`.

1. **48 kHz for rev A:** recorded (SPEC decision log). Ceiling 5833 cycles per frame.
2. **tanh:** decomposed first. The C library's `tanhf` is 178 cycles, the 4x oversampler's filters
   952 per sample: the filters were the larger part, contrary to my guess. `dsp_fast_tanhf` (121
   cycles, error 1.9e-7) replaces `tanhf` anyway; the half-band kernel now folds its symmetric taps
   into four partial sums: 4x saturator 1678 to 1204, limiter 1241 to 993, overdrive 3661 to 2479.
3. **ITCM:** the whole DSP library (27.6 KB) runs from ITCM. No measurable gain: the I-cache
   already held the loops. Kept. The first linker pattern also caught the start-up code (ld's `*`
   matches `/`); caught in the size and symbol check before flashing.
4. **Float32 PEQ sections:** not done. By the noise study, only sections at 1 kHz and above can
   change (110 to 120 dB in float32); at the measured kernel costs that saves about 400 cycles in
   all, under 4 %.
5. **Cheaper true-peak detector:** not done. The detector is about half of the limiter's 993; the
   saving is a similar few per cent.
   Steps 4 and 5 were the owner's go, held back because the measurements show they cannot close
   the gap; the decision below comes first.

**Found and fixed:** every flash wrote a HardFault into the fault record (pc in ST's flash loader).
Reproduced (resets: none; each flash: one), fixed by flashing in one programmer session.

**Now:** about 11 700 cycles per frame at 48 kHz, 2.0 times the ceiling; with saturation at 2x
(measured 570 against 1204) about 9200, 1.6 times. Unit tests 510 pass.

**For the owner: the batch 8c gate, round 2.** No single block closes it; options, with what each
buys (cycles per frame at 48 kHz):
- saturation at 2x in the strips and the overdrive (SPEC's first fallback): about 2500;
- exercise EX6, a shorter half-band filter: it sits under the saturators, the overdrive and both
  limiters, so a 90 dB design instead of 113 dB would take a share of about 5000 cycles;
- a sample-peak limiter on the headphones, keeping the true-peak one for the speakers: about 600;
- float32 PEQ sections above 1 kHz and a cheaper detector: about 400 each;
- giving the M4 (200 MHz, idle) a stage of its own, the headphone path for one, in batch 11;
- a rule that the most expensive options cannot all be on at once (strip saturation and the
  overdrive, for one).

## 2026-11-17: first board run (Nucleo-H755ZI-Q)

**Transcripts read:** none (no new block).

The owner connected the board. Read first, without writing: ST-LINK V3 (V3J16M9), 3.27 V,
device 0x450 revision V, 2 MB; option bytes at factory defaults (both cores boot, M7 at
0x08000000, M4 at 0x08100000, RDP 0, no bank swap). Then `tools/flash.ps1`: both images written
and verified. Console on COM22.

**Batch 1 on the board:** 400 MHz confirmed against the HSE (399 999 cycles per ms); direct SMPS;
the M4 parks; no fault recorded; USART3 (domain 2) runs with the M4 parked (SPEC V10, in part).

**Every self-test case against the PC** (`python tools/target_test.py --port COM22 --results
docs/results/bench_target.md`): 24 of 24 pass; 22 bit-identical between MSVC x64 and GCC on the
M7, including the double-state biquads, the limiter and the reverb; the two that call `tanhf`
(4x saturator, overdrive) within -132.5 and -152.3 dBFS.

**The bench now times processing only.** The first run timed each case's set-up as well, which
inflated the delay effects up to 10 times (the slot: 2573 against 237 cycles per frame). Cases now
call a mark hook when set-up ends; the bench reports cycles per frame with the channel count.

**The budget does not fit** (`docs/results/budget_target.md`): about 14 300 cycles per frame with
two strips and the dearest effect, against a 70 % ceiling of 2916 at 96 kHz (4.9 times over) and
5833 at 48 kHz (2.4 times). The four largest: two 4x saturators 3356, the overdrive 3661, two
limiters 2482, five double-state PEQ sets about 1700. How much of the saturators is `tanhf`, and
what ITCM placement gains, is not measured yet.

**Batch 8a on the board:** the protocol answers (`tools/ctl.py --port COM22`: hello, set,
knob-wins refusal, mode, the 169-line list over the UART); the first store write including the
sector erase 960 ms, a 1.3 KB record 4.5 ms; the power-on record and a preset survive a hardware
reset, and mute comes back on. Not done: the supply cut during a write (SPEC V18).

**Left on the board:** `tone_bass_db` in PC-wins mode at 3 dB, and preset 1 "Board test" (test
values; `preset save` over it or erase as wanted).

**For the owner: the batch 8c budget gate, now with numbers.** Options, in the order I would take
them (each measured before and after):
1. Run rev A at 48 kHz (its USB duplex is 48 kHz anyway): doubles the cycles per frame.
2. Measure, then replace, `tanhf` in the saturator and overdrive with a bounded polynomial or
   rational approximation (the largest single cost).
3. Hot kernels into ITCM (planned in SPEC 6.2, not done).
4. Float32 state for PEQ sections above a few hundred hertz; double only where the noise study
   needs it.
5. A cheaper true-peak detector for the two limiters.

## 2026-11-17: batch 8b follow-up (owner's decisions: 16-bit echo, reverb pre-delay and T_hi)

**Transcripts read:** none new.

**Decisions:** the owner chose a 16-bit echo at 48 kHz and "the rest as you recommend": FX
AMOUNT macros, glide, the 60 ms dry gap, two preset sectors, mute never restored and a four-beat
tempo window accepted as built; reverb pre-delay to 50 ms; T_hi anchored at 8 kHz; diffusers
and the reverb matrix left for listening. SPEC decision log has the rows.

**Done**
- Echo: 16-bit lines (2^13 per 1.0, saturating, no dither), core at fs up to 48 kHz and at fs / 2
  at 88.2 and 96 kHz between the 83-tap half-bands, the resampling latency taken off the delay;
  the pool stays float, int16 accessed by memcpy (no aliasing rule broken). Self-test case
  fx_echo96_f32.
- Reverb: pre-delay up to 50 ms; T_hi anchored at 8 kHz (0.45 fs if lower).
- `ctl/`: `rev_predelay_ms` 0 to 50 ms; `rev_hf_ratio` labelled for 8 kHz.

**Fixed, each with a test:** pure round-to-nearest trapped echo tails in a -59 dBFS limit cycle
(now toward zero below 16 LSB; kept on the main session's recommendation); a resting fractional
read dulled the repeats (-5.3 dB at 18 kHz, also in the first float echo; now whole samples at
rest); reverb DC gain rounding at extreme settings. Four test expectations were wrong and the
code right (impulse-based passband, window scalloping, a single-tone fit leaking, an 8 kHz band
compared with a centre-frequency value). One note claim (Hadamard builds density faster) was
withdrawn rather than the test loosened.

**Measured (PC)**

| Item | Value | Command |
|---|---|---|
| Unit tests | 507 pass | `python -m pytest` |
| Echo error, no feedback / feedback 0.95 | -88.4 / -74.2 dBFS RMS; tails end in exact zero | `python -m pytest tests/unit/test_fx_echo16.py -s` |
| Echo at 96 kHz: repeat time, passband to 18 kHz, image | within 1 sample; 0.001 dB; -113 dB | same |
| Reverb T60 by octave, 500 Hz / 4 kHz / 8 kHz | within 3.5 % of design | `python -m pytest tests/unit/test_reverb.py -s` |
| AXI SRAM at 96 kHz: echo + reverb + room FIR estimate | 420 KB of 512 | `python tools/studies/b8b_memory.py` |
| M7 image | 90.8 KB flash, 80.5 KB DTCM, 30 KB AXI | `cmake --build --preset fw` |

**For the owner:** by ear, once audio runs: the reverb matrix (Hadamard or Householder) and
input diffusers; the echo's rounding rule if the tails ever sound wrong. Exercises open: EX1,
EX3, EX6, EX8a, EX8b.

## 2026-11-17: batch 8b, host part (delay line, LFO, SVF, effects, slot, reverb)

Written by a second agent on branch `b8b` in a worktree, in parallel with 8a, and merged.

**Transcripts read in full:** Comb Filters & Delay Lines (#124), Delay-Based Audio FX (#140),
Tremolo Effect (#3); re-read where relevant: All-Pass Filter (#162), DSP Overdrive (#117),
Asymmetrical Clipping (#153). Findings in each design note's "From the transcripts".

**Done**
- `dsp_delayline`, `dsp_lfo`, `dsp_svf`, `dsp_fx_echo`, `dsp_fx_mod` (chorus, flanger, phaser),
  `dsp_fx_colour` (sweep filter, overdrive, bit crusher), `dsp_fx_tremolo` (stub: exercise),
  `dsp_fxslot`, `dsp_reverb`; float64 models in `tests/ref/modulation.py` and `tests/ref/fx.py`.
- Self-test cases: delay_lagrange_f32, svf_f32, fx_echo_f32, fx_chorus_f32, fx_flanger_f32,
  fx_phaser_f32, fx_sweep_f32, fx_overdrive_f32, fx_crusher_f32, fxslot_f32, reverb_f32.
- Studies: `tools/studies/b8b_interp.py`, `tools/studies/b8b_memory.py`; results in
  `docs/results/b8b_interp.md`, `b8b_memory.md`, `b8b_cycles.md`.
- Notes: `delay_lines.md`, `modulated_filters.md`, `effects.md`, `reverb.md`.
  Exercise: `docs/exercises/EX8b_tremolo.md` (its 8 tests fail on the stub, as intended; checked
  against a throw-away model that was then deleted).

**Fixed, each with a test:** the echo glide drifted 0.42 samples and jumped at its end; the slot
clicked when a delay effect started (input now fades in with the wet); NaN could reach an integer
cast in the delay reads and the crusher.

**At the merge:** the firmware build (GCC) caught an unused static function in the self-test
that MSVC at /W4 did not; removed. The 30 KB self-test pool moved to AXI SRAM (`.axi_bss`),
where the real delay lines will be, so the board's cycle counts are the real ones: DTCM 107 KB
to 76 KB of 128.

**Measured (PC)**

| Item | Value | Command |
|---|---|---|
| Unit tests, everything | 479 pass | `python -m pytest` |
| Swept-delay error at 1 kHz, linear / Lagrange / all-pass | -56 / -106 / -61 dB | `python tools/studies/b8b_interp.py` |
| SVF vs biquad, cutoff jumping every 16 samples | SVF 1.64 (bound 3.19); biquad diverges | `test_svf_against_biquad_under_modulation` |
| Overdrive harmonics against a continuous-time model | within 0.2 dB | `test_overdrive_harmonics_match_the_model` |
| Overdrive level, 0 to 36 dB drive | within 0.13 dB | `test_overdrive_level_compensation` |
| Echo trail repeat ratio at feedback 0.5 | 0.4951 to 0.4961 (0.4953 expected) | `test_echo_trails_decay_at_the_set_feedback` |
| Reverb T60 at 500 Hz and 4 kHz | within 3.7 % of design (plan: 10 %) | `test_decay_time_by_schroeder_integration` |
| Reverb, 60 s at 20 s decay | never rises | `test_no_growth_over_a_minute_at_the_longest_decay` |
| Reverb echo density 0.9 | 195 ms | `test_echo_density` |
| Memory at 96 kHz: float echo 0.75 s / reverb | 563 KB / 177 KB | `python tools/studies/b8b_memory.py` |
| M7 image | 88.6 KB flash, 76.3 KB DTCM, 30 KB AXI SRAM | `cmake --build --preset fw` |

**Not done, needs the board:** cycles of every block (`docs/results/b8b_cycles.md`); the
listening check of each effect on the breakouts (batch 2).

**For the owner**
1. The FX AMOUNT macro table (`docs/notes/effects.md`), built as proposed.
2. The memory decision (8b.6, `docs/results/b8b_memory.md`): a float echo at 96 kHz does not fit
   AXI SRAM; 16-bit storage with the echo at 48 kHz does (458 KB with the room FIR estimate).
   16-bit storage is not built yet.
3. Glide (built) or cross-fade for synced echo time changes; the 60 ms of dry signal when the
   effect changes; reverb pre-delay maximum (100 ms costs 75 KB); the reverb's high-frequency
   decay anchor (Nyquist, built, or 8 kHz); input diffusers.
4. Exercise 8b: `docs/exercises/EX8b_tremolo.md`.

## 2026-11-17: batch 8b.5, the tempo follower (in ctl/)

**Transcripts read:** the batch 8 list is the effects' (the 8b agent reads it); all 29 searched
for tempo, tap and MIDI clock: one passage in #140 (note values and tap tempo on a commercial
delay), recorded in `docs/notes/tempo.md`.

- `ctl_tempo`: MIDI clock follower, tap tempo, transport and beat phase; wired to the MIDI
  parser's real-time hook, the protocol's `tempo`, and the firmware's main loop (taps and the
  stored tempo work on the board now; MIDI clock arrives with batch 4).
- Measured: 0.032 to 0.041 BPM worst under +/-1 ms jitter (target 0.1); a 20 BPM step followed
  within one beat; a 0.75 BPM-per-beat ramp lags by 1.35 BPM (`python -m pytest -s
  tests/unit/test_ctl_tempo.py`).
- Found by the tests: after a restart the fit over a few jittered ticks was noisy (1.57 BPM
  worst on the ramp), now settled by reporting the one-beat fit for 16 ticks; a phase query a
  microsecond early wrapped to a whole tick, now guarded.
- Unit tests: 378 pass (`python -m pytest`). M7 image 67.9 KB flash, 65.4 KB DTCM.

**For the owner:** glide or cross-fade on synced delay changes (glide is in); whether a
three-beat window suits DJ tempo rides better (`docs/notes/tempo.md`).

## 2026-11-17: batch 8a, control core (host part and firmware build)

**Transcripts read:** none listed for 8a in `transcripts_index.md`. All 29 searched for how the
videos handle potentiometers; the passages in #117, #153 and #58 read and used (#58's 1 % change
threshold agrees with the pick-up hysteresis here).

**Done**
- `ctl/`, a hardware-free C11 library beside `dsp/`, built into the M7 image and, on the PC, into
  `ctl_host.dll` and the sanitised `ctl_fuzz.exe`:
  - `ctl_params`, `ctl_param_table.c`: 169 parameters in one const table (capacity 192), ids by
    group, curves linear, log, volume and step.
  - `ctl_queue`: the hand-off to the audio interrupt; each parameter queued at most once, so it
    cannot overflow.
  - `ctl_core`: values, sources, knob ownership with pick-up, change notification, CC out.
  - `ctl_proto`: protocol version 1 (`docs/notes/control_protocol.md`).
  - `ctl_midi`: parser and the fixed map on the 40 undefined CC numbers.
  - `ctl_preset`: 8 presets and a power-on record as a log on two flash sectors, by id.
- Firmware: `fw/cm7/src/flash_store.c` (bank 2 sectors 6 and 7, ECC-safe reads, cache
  invalidation); `main.c` answers the protocol on the console, writes the power-on record, sends
  meters at 30 Hz when asked; new `ptime` command. The bench `list` command is now `cases`. The
  M4's flash region is 768 KB.
- `tools/ctl.py`: client over a serial port or `--sim` (the C library on the PC).
- Notes: `ctl_registry.md`, `knob_pickup.md`, `control_protocol.md`, `midi_map.md`,
  `preset_store.md`. Exercise: `docs/exercises/EX8a_cc14.md` (checked solvable with a solution
  that was then removed; 3 of its 9 tests fail with the stub, as intended).

**Found by the tests:** a power-on restore applied the volume before its knob mode (the mode
ids are higher), so a PC-wins volume was refused and lost; loads now apply the modes first. Two
test expectations were wrong and the code right: a power cut in a record's padding leaves a good
record (the padding is erased flash), and a preset load refuses the five knob parameters while
they are in knob-wins mode.

**Measured (PC)**

| Item | Value | Command |
|---|---|---|
| Unit tests | 365 pass | `python -m pytest` |
| Fuzz under the address sanitiser | 200 000 iterations, 12 MB, clean, 3.4 s | `build\host\ctl\Release\ctl_fuzz.exe 200000 7` |
| Power cut at every byte of a 928-byte record | old or new preset, never anything else | `test_power_cut_at_every_byte_of_a_write` |
| Power cut during compaction (every 97th byte, and mid-erase) | every slot kept | `test_power_cut_during_compaction` |
| Knob re-attach, largest step | 0.288 dB on the +/-12 dB tone range | `test_no_jump_on_re_attach_from_either_side` |
| M7 image | 67.2 KB flash, 64.9 KB DTCM (was 42.8 and 57) | `cmake --build --preset fw` |

**Not done, needs the board:** `tools/ctl.py --port COMx` get, set, presets, power cycle;
`ptime`; the read path's ECC masking with a supply cut during a write (SPEC V18); erase time and
the M7's fetches during it (V17, V19). The audio-undisturbed check needs batch 2.

**For the owner (the plan's stop for 8a)**
1. Review the parameter table (`python tools/ctl.py --sim list`, or `ctl/src/ctl_param_table.c`)
   and the MIDI map (`docs/notes/midi_map.md`): names, ranges, defaults, curves, which 40
   parameters get a CC.
2. Decision-log rows to confirm: two flash sectors instead of one; mute never restored; the room
   and headphone corrections, knob modes and tone corners as settings rather than preset
   contents.
3. Exercise 8a: `docs/exercises/EX8a_cc14.md`.

## 2026-11-17: owner decisions after batch 6; repository pushed

**Transcripts read:** none (no new block).

- Pushed to `https://github.com/knnurl/stm32h7-audio-interface-dsp` (remote `origin`).
- Limiter: the owner chose the 0.5 dB margin. `DSP_LIMITER_TRUE_PEAK_MARGIN_DB`; the detector's
  threshold is the set ceiling less 0.5 dB. Measured: the true peak stays 0.30 dB under the set
  ceiling at every look-ahead (`python -m pytest tests/unit/test_limiter.py -s`). The bit-exact
  test's noise went from 0.5 to 0.4 peak, because white noise's inter-sample peaks reached the
  lower threshold.
- Defaults recorded in the SPEC decision log: compressor release 50 ms, saturation 4x, tone
  corners 100 Hz, 1 kHz, 10 kHz (provisional until the owner listens).
- Unit tests: 222 pass (`python -m pytest`).

## 2026-11-17: batch 6, host part (dynamics, oversampling, saturation, limiter)

**Transcripts read in full:** Audio Compressor Software Implementation, Noise Gate (#58),
Recursive RMS (#103), DSP Overdrive (#117), DSP Overdrive Asymmetrical Clipping (#153),
Decimation Filters (#42). Read by a review agent in this session before any batch 6 test was
written; its findings were checked here, and one (the cause of the limiter's true-peak
overshoot) was contradicted by measurement.

**Done**
- `dsp_fastmath`, `dsp_env`, `dsp_comp`, `dsp_gate`, `dsp_oversample`, `dsp_saturate`,
  `dsp_limiter`; `dsp_abi.c` checks every ctypes mirror's size against the compiler's.
- Self-test cases `comp_f32`, `gate_f32`, `limiter_f32`, `sat_os4_f32`, `sat_adaa_f32`.
- Studies: `tools/design/b6_coefficients.py`, `tools/studies/b6_aliasing.py`.
- Notes: `dynamics.md`, `oversampling_saturation.md`, `limiter.md`, each with its "From the
  transcripts" section. Exercise: `docs/exercises/EX6_halfband.md` (its tests checked against the
  built-in filter, then left failing for the owner).

**Fixed, each with a test:** ADAA spike when the drive changes; `dsp_fast_exp2f(NaN)` undefined
behaviour; the 4x oversampler's scratch overflow above 64 frames; NaN leaving the compressor's
side chain poisoned; the limiter's release stalling at 0.99997 so it never became transparent
again; the limiter now replaces NaN and infinity with 0 and has a 32-sample minimum look-ahead.

**Measured (PC)**

| Item | Value | Command |
|---|---|---|
| Unit tests | 222 pass | `python -m pytest` |
| Aliasing at 5 kHz, plain / ADAA / 2x / 4x | -27.4 / -38.5 / -64.4 / -130.9 dB | `python tools/studies/b6_aliasing.py` |
| 40 Hz, 12 dB over threshold, THD at release 10 / 50 / 200 ms | -24.0 / -33.0 / -42.6 dB | `test_bass_distortion_against_release` |
| Limiter, no sample over the ceiling, hostile signals | holds | `test_no_sample_exceeds_the_ceiling` |
| Limiter, true peak over the ceiling | 0.198 dB at every look-ahead from 32 to 240 samples | `test_true_peak_overshoot_against_lookahead` |
| Oversampled clipping of full-band noise, peak | 1.45 (2x), 1.55 (4x) | `test_latency_and_bounds` |
| Oversampler latency | 41 (2x), 46.5 (4x) samples | `test_round_trip_latency_and_flatness` |
| M7 image | 42.8 KB flash, 57 KB DTCM (the self-test's static limiter is 30 KB of it) | `cmake --build --preset fw` |

**Not done, needs the board:** cycles of every block, fast log and exp against the C library.

**For the owner**
1. **The limiter's true-peak gap** (`docs/notes/limiter.md`): 4x detection under-reads peaks
   between samples, by up to 0.47 dB for content near 20 kHz at 48 kHz. Options: a 0.5 dB
   margin (recommended now), 8x detection, or interpolation between the four.
2. The strips' default compressor release: 50 ms or more, from the distortion figures.
3. The strips' saturation mode: 4x (0.97 ms of latency at 48 kHz) or 2x.
4. Exercise 6: `docs/exercises/EX6_halfband.md`.
5. Pushing: the repository has no remote yet. Say which: a private GitHub repository created
   with `gh`, or a URL of one you create.

## 2026-11-17: transcript pass for batch 3

**Transcripts read in full:** Biquad Filters (#172), Audio EQ Software Implementation (#89), IIR
Filters (#32), Bilinear Transform IIR Filter Design, Real-Time Software Implementation of Analog
Filters (#20), Z-Transform (#27), The Simplest Digital Filter (#92), Notch Filters (#49),
All-Pass Filter (#162). Read by a review agent in this session against the batch 3 code; the
findings were checked here before acting on them.

**Agreed with what was built:** TDF-II equations and conventions, double precision for
low-frequency sections, cascades, coefficients recomputed per block and not per sample.

**Fixed, each with a test:**
- Shelf slope above about 1.9 to 5 gave NaN coefficients (square root of a negative); the PEQ
  passed its band Q through unchecked. The slope is now clamped to [0.05, 1].
- f0 at or above Nyquist, or Q at or below 0, gave unstable or infinite coefficients. Every
  design now clamps f0 to (0, 0.49 fs) and Q to at least 0.01.
- `dsp_coef_to_q31` refuses non-finite and unstable results; `dsp_coef_f32_is_stable` added.
  Measured: a 2 Hz high-pass at 96 kHz becomes unstable when rounded to float32.
- Tone control: the right channel was not written when only the left was processed in place.

**Open question for the owner:** the PEQ ramps coefficients linearly, the tone control redesigns
per block; proposal in `docs/notes/tone.md` (cross-fade on band type changes).

| Item | Value | Command |
|---|---|---|
| Unit tests | 161 pass | `python -m pytest` |

## 2026-11-17: batch 3, host part (filters, Q31, tone control)

**Done**

- `dsp_biquad`: float32 TDF-II, a double-state TDF-II with float input and output, and Q31
  direct form I with a 64-bit accumulator, per-section shift and optional error feedback.
- `dsp_coef`: cookbook peak, shelves, low-pass, high-pass, first-order sections, Butterworth to
  order 8, magnitude, quantisation to float32 and to Q31 with an overflow-proof shift rule.
  Notch and all-pass are stubs for exercise 3.
- `dsp_peq`: high-pass plus four bands, coefficient ramps over a set number of blocks.
- `dsp_tone`: bass, mid, treble, -12 to +12 dB, smoothed in dB, exact at centre.
- Self-test cases `biquad_f32`, `biquad_f64`, `biquad_q31_round`, `biquad_q31_ef`, `tone_f32`.
- Studies: `tools/studies/b3_filter_noise.py`, `tools/studies/b3_cramping.py`.
- Notes: `biquad.md`, `coefficient_design.md`, `tone.md`. Exercise:
  `docs/exercises/EX3_notch_allpass.md`.

**Measured (on the PC)**

| Item | Value | Command |
|---|---|---|
| Unit tests | 116 pass | `python -m pytest` |
| Float32 TDF-II, low-frequency sections, signal-to-noise | 59 to 111 dB (20 Hz high-pass at 48 kHz: 68 dB at -1 dBFS) | `python tools/studies/b3_filter_noise.py` |
| Double-state TDF-II, same sections | 151 to 156 dB (the float output's own rounding) | same |
| Q31 DF-I with error feedback, same sections | 98 to 190 dB; without it at -60 dBFS: 55 to 79 dB | same |
| Cramping, +12 dB peak Q 1 at 15 kHz, 1.2 f0 | -4.25 dB at 48 kHz, -0.64 dB at 96 kHz | `python tools/studies/b3_cramping.py` |
| Tone: zipper sidebands of a full sweep in 100 ms | -106 dBFS | `test_zipper_noise_of_a_full_sweep` |
| Tone: flat at centre | bit-exact | `test_flat_at_centre_is_bit_exact` |
| M7 image | 34 KB flash | `cmake --build --preset fw` |

**Decided (provisional): the PEQ and the tone control run in double** (`dsp_biquad_f64_section`),
because float32 state loses 40 to 90 dB on low-frequency sections. It stands or falls on the
M7 cycle cost, which only the board can give.

**Not done, needs the board:** cycles per sample of every kernel (float32 against double is the
deciding number), the fused multiply-add and denormal studies, the PEQ and tone control in the
pass-through.

**For the owner**

1. Confirm the tone corner frequencies (100 Hz, 1 kHz with Q 0.7, 10 kHz) or give others.
2. Exercise 3: `docs/exercises/EX3_notch_allpass.md` (12 tests waiting).
3. With the board: `python tools/target_test.py --port COMx` now also times the filters.

## 2026-11-17: batch plan rewritten with the feature review

`docs/PLAN_BATCHES.md` now carries the owner's additions inside the batches instead of in a
side table:

- Batch 3: the tone control `dsp_tone_f32` (corner frequencies 100 Hz, 1 kHz, 10 kHz proposed;
  the owner confirms), bit-exact when flat.
- Batch 4: a composite USB device (UAC2, USB MIDI, CDC) with an endpoint budget checked first,
  the record-source switch, and Ableton tests with written procedures.
- Batch 5: a main board (160 by 100 mm, Nucleo underneath, rear connectors, USB-C) and a control
  panel board, in two KiCad projects; a mechanical interface table for the later enclosure.
- Batch 8 split into four parts, each specified in full: 8a control core (registry, knob
  ownership, text protocol, MIDI mapping, presets in flash bank 2), 8b effect slot (8 effects
  with a proposed FX AMOUNT macro table), reverb and tempo, 8c the full signal path, 8d the
  control panel firmware.

SPEC (sections 3.4, 4, 6.7, 7, 9 and the decision log), `docs/PLAN.md` and the README follow it.
New dependency named for test tools only: `mido` with `python-rtmidi`, from batch 4.

For the owner:
1. The proposals to confirm when their batch starts: tone corner frequencies (3); the FX AMOUNT
   macro per effect and the echo's glide on tempo change (8b); mute and dim on the monitors only,
   the volume law, and the button mapping (8c, 8d).
2. The memory budget in 8b.6 is over the M7's 512 KB of AXI SRAM by the estimates: a decision
   comes when 8b starts, from measured sizes.
3. Without hardware, the next batches that can run are the host parts of 3, 6 and 8b, and 8a.

## 2026-11-17: batch 1, foundation (built; not yet run on the board)

**Done**

- `dsp/`: the library route with its first block. `dsp_gain_f32` (smoothed gain),
  `dsp_testsig` (bit-exact noise, impulse, step; a sine), `dsp_crc32`, `dsp_selftest` (the cases
  the PC and the target both run), and `dsp_dcblock` as a stub for exercise 1.
- `tests/`: reference models, 28 unit tests, and 6 exercise tests that fail until the exercise
  is done. `tests/dsplib.py` loads the DLL through ctypes.
- `fw/`: firmware for both cores. M7: 400 MHz, direct SMPS, both caches, the MPU region for DMA
  buffers, console, fault capture, the `bench` and `vec` commands, the three execution levels.
  M4: parked in stop mode. Both linker scripts are our own (SPEC 6.2).
- `tools/`: `flash.ps1` (checks the device identity before writing), `console.py`,
  `target_test.py`, and `target_protocol.py` (the comparison logic, unit-tested without a board).
- `.github/workflows/ci.yml`: written; it runs once a GitHub repository exists.
- Design notes: `build_and_test_route.md`, `gain.md`, `memory_and_cache_plan.md`.
  Exercise: `docs/exercises/EX1_dcblock.md`.

**Measured**

| Item | Value | Command |
|---|---|---|
| Host tests | 28 pass | `python -m pytest` |
| Exercise tests | 6 fail, as intended | `python -m pytest tests/exercises` |
| M7 image | 20 152 B flash, 33 608 B DTCM | `cmake --build --preset fw` |
| M4 image | 1 268 B flash | same |
| Supply setting in both images | direct SMPS (start-up clears LDOEN, waits for ACTVOSRDY) | `arm-none-eabi-objdump -d --disassemble=ExitRun0Mode build/fw/fw/dsp_cm7.elf` |
| Gain: float32 one-pole stalls short of its target | 3.6e-6 away for 5 ms at 48 kHz (-109 dBFS); now snaps to the target | `docs/notes/gain.md` |

**Not done, and why**

- Nothing was flashed or run on the board: no ST-LINK was attached. So the 400 MHz clock, the
  parked M4, the console and the cycle table (`docs/results/bench_b1.md`) are unverified. The
  firmware has only been compiled and inspected.
- pytest 9.2.0 crashes on this Python 3.10 with an internal error; `tests/requirements.txt` pins
  8.3.5.

**Recovery if a wrong supply setting ever locks the board**

This build cannot produce such an image (`fw/CMakeLists.txt` has no option for the supply), so
this is for an image from elsewhere, such as a CubeMX project left on LDO. From knowledge of the
part and ST community threads, not checked against the board manual or tried [Verify: SPEC V5]:

1. Unplug the board.
2. Tie the BOOT0 pin to VDD (both are on the CN11 morpho row; check the pin numbers in the
   board manual), so the MCU starts in its system bootloader instead of the bad image.
3. Plug in. In STM32CubeProgrammer, connect over ST-LINK and do a full chip erase.
4. Unplug, remove the BOOT0 link, plug in, and flash a correct image.

If the ST-LINK cannot connect at step 3, try connect mode "Power down" with "Hardware reset".

**For the owner**

1. Connect the Nucleo by its ST-LINK USB port and say so. Then:
   ```
   powershell -ExecutionPolicy Bypass -File tools/flash.ps1
   python tools/target_test.py --port COMx --results docs/results/bench_b1_table.md
   ```
   Expect `measured_cycles_per_ms=400000`, `cm4_parked=1`, and both cases `ok`.
2. Exercise 1: `docs/exercises/EX1_dcblock.md`.
3. Deferred DSP level: PendSV at priority 14 (SPEC decision log). Say if you would rather have a
   spare peripheral interrupt.

## 2026-11-17: batch 0, project documents

Done: `README.md`, `LICENSE`, `.gitignore`, `CLAUDE.md`, `docs/SPEC.md`, `docs/PLAN.md`, this
file, and a local git repository on `main`. Nothing built.

The interview plan, the assessment and the batch specification were already in `docs/`.

Numbers: none measured. The SPEC's cycle budget (3.4) is all estimates, and its total (3630
cycles per sample) is over the 70 % ceiling (2916). Nothing is cut on estimates; batches 3 and 6
replace the largest rows with measurements.

For the owner to confirm or change (SPEC 3.2 and 3.3, marked "proposed"):

| Target | Proposed |
|---|---|
| Analogue in to monitor out latency at 96 kHz, without the room FIR | under 1.5 ms |
| USB round trip at 48 kHz | under 10 ms |
| M7 worst-case load at 96 kHz | under 70 % |
| Input level at 0 dBFS | +20 dBu |
| Monitor output level at 0 dBFS | +18 dBu |
