# Implementation spec: the DSP audio interface, in batches

Written 2026-11-15 for the agent that implements it (Claude Opus, working in
`C:\Users\ses634\Desktop\Projects\DSP`). Read first, in this order:

1. `docs/PLAN_ASSESSMENT.md`: the corrections. It wins over the interview plan.
2. `docs/PLAN_INTERVIEW.md`: the decisions from the scoping interview.
3. From batch 1 on: `CLAUDE.md`, `docs/SPEC.md`, and the last entry of `docs/PROGRESS.md`.

This file does not repeat their reasoning.

## 0. What this is for

The owner (Kaan Ural: robotics and embedded engineer, C/C++, STM32, KiCad; treat him as an
expert) is preparing for an embedded DSP role on hardware audio products. The project is a USB
audio interface with DSP on board, built on an STM32H755. It is a portfolio piece first and his
home studio interface second. Claude writes the code and documents; the owner reviews, runs the
measurements and does one exercise per batch.

The device (concept A):

```
LINE IN 1-2 -> ADC -> [ Input strip x2: trim, HPF, 4-band PEQ, gate, compressor, saturation ]
                              |-> USB record 1-2
                              '-> MONITOR MIXER <- USB play 1-2, S/PDIF in, reverb return
                                        |-> [ Speaker stage: room FIR, PEQ, delay, limiter ] -> OUT 1-2
                                        '-> [ Headphone stage: PEQ, crossfeed, limiter ]    -> OUT 3-4
```

One batch is one reviewable unit and one session. It ends with the build clean, the tests
passing, its numbers and commands in `docs/PROGRESS.md`, its review pack written, and a stop for
the owner. Do not start the next batch in the same session unless the owner said so.

| Batch | Content | Needs hardware | Depends on |
|---|---|---|---|
| 0 | Project documents | No | Nothing |
| 1 | Foundation: host library, test harness, firmware skeleton | Nucleo | 0 |
| 2 | Audio pass-through on breakouts | Nucleo, two breakouts, scope | 1 |
| 3 | Filters, float and Q31 | Nucleo (breakouts for listening) | 1 (2 for the live demo) |
| 4 | USB audio, full speed. **Portfolio checkpoint P1** | Nucleo, breakouts | 2, 3 |
| 5 | Shield rev A design, five stages | No | 0 (2 helps the pin plan) |
| 6 | Dynamics and saturation | Nucleo | 3 |
| 7 | Shield bring-up and lab session | Shield, lab analyser | 5, 4 |
| 8 | Strips, monitor mixer, reverb, metering, host control | Shield | 6, 7 |
| 9 | Room correction | Shield, lab microphone | 8 |
| 10 | S/PDIF and ASRC (stretch) | Shield | 8 |
| 11 | Dual-core split and front panel (stretch) | Shield | 8 |
| 12 | Rev B integrated board (stretch) | New board | 7, 8 |
| 13 | Portfolio write-up | No | 9 |

Batches 0 to 6 are specified in full below. Batches 7 to 13 are outlined with their constraints
and gates; each gets its own detailed spec once the measurements it depends on exist. Batch 5 can
run at any point after batch 0, alongside the firmware batches.

## 1. Ground rules

- **Git:** local repository from batch 0, branch `main`, small commits, one concern per commit.
  Never create a remote, a GitHub repository or a push without the owner's word.
- **Never without the owner's explicit go:** placing an order or anything that costs money;
  writing option bytes; reworking the Nucleo; adding a dependency not named in this file;
  changing a decision in the interview plan or the assessment.
- **Supply configuration:** the Nucleo-H755ZI-Q is wired for direct SMPS. Firmware always selects
  direct SMPS supply and voltage scale 1, and runs the M7 at 400 MHz at most. An image that
  selects LDO supply leaves the board unable to start. Batch 1 writes the recovery procedure
  into `docs/PROGRESS.md` before the first flash.
- **Flashing:** only when the owner has said the board is connected. Read the device identity
  first and stop if it is not an H745/H755.
- **Audio out of real outputs:** assume speakers or headphones may be connected. Outputs start
  muted. A test signal that reaches an analogue output is at most -20 dBFS, ramps in, and the
  owner is told before it plays. Automated tests use a loopback cable or a digital loopback.
- **Measure, do not guess.** Every latency, CPU, noise or accuracy figure in a document has the
  command or the bench procedure that reproduces it. Say what was measured and what is
  estimated. Unchecked claims carry `[Verify]` and are listed in SPEC section 9.
- **When a result disagrees with this spec,** the result wins: write it into PROGRESS, add a
  decision-log row to the SPEC, and stop if it changes a later batch.
- **Licences:** the repository is MIT. Allowed in it: MIT, BSD, Apache-2.0, zlib, ISC, public
  domain. Known dependencies: ST HAL and CMSIS device (BSD-3), CMSIS core and CMSIS-DSP
  (Apache-2.0), TinyUSB (MIT), FreeRTOS (MIT, batch 11 only). Third-party sources are fetched at
  pinned commits into a gitignored folder, never committed.
- **Private data:** no copyrighted audio in the repository. Test signals are synthetic.
- **Writing:** British English, no em dashes, sentence case for labels, units in names (`_hz`,
  `_ms`, `_samples`, `_db`, `_cycles`), `[Verify]` on unmeasured claims.
- **Docs in the same commit:** the SPEC section a change touches, a decision-log row for every
  decision, `docs/PROGRESS.md`, and the commands in `CLAUDE.md` and `README.md`.

### 1.1 The review pack every batch ends with

- **A design note per DSP block or subsystem,** in `docs/notes/<name>.md`, on this template:
  purpose; the maths; the structure chosen and the alternatives rejected, with the reason; the
  numerical behaviour (noise, overflow, limits of validity); measured cycles per sample on the
  target; the test evidence; open questions.
- **One exercise for the owner,** in `docs/exercises/EX<batch>_<name>.md`: the task, a header or
  stub, tests that fail until it is done, and the acceptance numbers. Do not write the solution.
  Review the owner's solution when he asks.
- **A PROGRESS entry:** what was done, the measured numbers, the exact commands, what the owner
  must do or decide next.

### 1.2 Code rules (batch 0 copies these into `CLAUDE.md`)

- `dsp/` is hardware-free C11: no HAL, no allocation, no stdio, no global mutable state. It
  builds unchanged for the PC and the target.
- Block API: `dsp_<block>_<fmt>_init`, `_reset`, `_process(state, in, out, n_frames)`, with
  `<fmt>` one of `f32`, `q31`, `q15`. Each header states its assumptions, its latency in samples
  and its measured cycles per sample.
- `math.h` calls are allowed in init and coefficient code. In a `process` function they need a
  measurement that justifies them.
- Types `PascalCase`, functions and variables `snake_case`, constants `kPascalCase`.
- Own code compiles with warnings as errors; vendor code compiles as shipped.
- On the audio path: no allocation, no locks, no printing, no unbounded loops.

### 1.3 Test rules

- Every block has a Python reference model in `tests/ref/` and a pytest that calls the C library
  through ctypes.
- Fixed-point blocks match a Python integer model **bit-exactly**. The model states its rounding
  and saturation rules in words.
- Float blocks match within a stated tolerance, in dB relative to full scale.
- Every block runs on the target against the same vectors. Fixed point: CRC32 of the output
  equals the host's. Float: the output is dumped over the console and compared with the host
  within the tolerance.
- Runs are deterministic: the same input and parameters give the same output, enforced by a test.

## 2. Batch 0: project documents

Nothing is built. The batch writes the documents every later session starts from.

**Files.**

- `README.md`: what the device is, the concept A diagram, a status table by batch, how to build
  (filled in as commands come to exist), links to the documents.
- `LICENSE`: MIT, in the owner's name.
- `.gitignore`: build folders, `fw/third_party/`, Python caches, KiCad backups and lock files,
  captures.
- `CLAUDE.md`: what the project is; the priorities (1 measured correctness, 2 real-time
  robustness, 3 monitoring latency, 4 audio quality, 5 cost, 6 feature count); the work split and
  the review pack (1.1); the code and test rules (1.2, 1.3); the ground rules of section 1; the
  repository layout; a commands section that says "none yet".
- `docs/SPEC.md`, sections:
  1. Purpose, audience, non-goals (mic preamps, Hi-Z input, a custom ASIO driver, network audio).
  2. Priorities and the signal flow.
  3. Requirements. Rev A and rev B in separate columns: channels, sample rates, USB modes
     (assessment, correction 1), analogue levels, latency targets, CPU budget (under 70 % of the
     M7 at 96 kHz and 400 MHz), robustness (no dropouts over 8 h), analogue targets (mid-grade).
     Every number is marked as target, estimate or measured.
  4. Hardware rev A (the shield): blocks and open choices only. Batch 5 fills it in.
  5. Hardware rev B: the delta, including the supply scheme question.
  6. Firmware architecture: the three execution levels and their priorities; the memory plan
     (assessment, correction 6); the clock plan (PLL3 on breakouts, oscillators through I2S_CKIN
     on the shield); USB to audio buffering and feedback; sample-rate switching with mute; the
     M7 and M4 split; the parameter registry and the control protocol.
  7. DSP blocks: one subsection per block with algorithm, formats, latency, test method and the
     batch that delivers it.
  8. Verification: host tests, target tests, benchmarks, latency procedures, the lab protocol.
  9. Assumptions to verify: every `[Verify]` in the project, each with the batch that settles it.
     Seed it from section 6 of the assessment.
  10. Decision log: one row per interview decision and one per assessment correction, dated.
- `docs/PLAN.md`: the batch table of this file with a status column, the portfolio checkpoint,
  and the core and stretch split. It points here for detail.
- `docs/PROGRESS.md`: the handoff log, newest entry first. First entry: this batch.

**Cycle budget table (SPEC 3).** Start it with estimates, one row per block of concept A, in
cycles per sample at 96 kHz against the 4166 available. Mark every row "estimate". Later batches
replace rows with measurements.

**Acceptance.**

- Every row of the interview plan's decision table is in the SPEC decision log, with the
  assessment's corrections applied (48 kHz duplex on rev A, 400 MHz, the convolution design).
- The four documents agree with each other on every number.
- Searching the folder for an em dash finds none. Spelling is British.
- Only Markdown, `LICENSE` and `.gitignore` exist. `git log` shows the commits.

**Stop for the owner with:** the list of SPEC targets that are his to set (latency, analogue
level alignment, the 70 % CPU ceiling), each with the proposed value.

## 3. Batch 1: foundation

Goal: one trivial DSP block travels the whole route (C library, Python reference, host test,
target test, cycle count), so every later block only fills in the pattern.

**Reuse.** `C:\Users\ses634\Desktop\Projects\Psyight\firmware\node-f767` is the pattern for the
firmware build: `cmake/arm-none-eabi.cmake` (finds the GCC 13.3 inside STM32CubeIDE 1.19),
`fetch_deps.ps1` (ST repositories at pinned commits), strict warnings on own sources only,
`src/board/fault.c` (fault report), `src/board/syscalls.c`, the console that never blocks, and
flashing with `STM32_Programmer_CLI`. Copy and adapt; do not link across projects. Start-up code
and linker scripts for both cores come from the dual-core templates in
`C:\Users\ses634\STM32Cube\Repository\STM32Cube_FW_H7_V1.12.1`.

**Layout.**

```
dsp/      CMakeLists.txt  include/dsp/  src/        hardware-free C11 library
tests/    pytest suites, ref/ (Python models), conftest.py, requirements.txt
fw/       CMakeLists.txt  cmake/  fetch_deps.ps1  cm7/  cm4/  third_party/ (gitignored)
tools/    flash.ps1, console.py, target_test.py
docs/     notes/  exercises/  results/
```

**1.1 Host library and harness.**
- CMake presets: `host` configures with MSVC; `host-release` builds `dsp` as a static library
  and as a DLL for ctypes. `/std:c11 /W4 /WX /fp:precise`.
- First block: `dsp_gain_f32`, a gain with one-pole smoothing of the linear gain, time constant
  in ms. It exists to prove the route, so keep it small.
- `dsp_testsig`: deterministic test signals in C (a linear congruential noise source, sine,
  impulse, step), so the target can generate the same input as the host without a file.
- `tests/conftest.py`: loads the DLL, maps numpy arrays to the C calls, and offers
  `assert_within_db(actual, expected, limit_db)`.
- `tests/requirements.txt`: numpy, scipy, pytest, pyserial, pinned. Python 3.10 is installed.

**1.2 Firmware skeleton (M7).**
- Clock: HSE [Verify source and frequency on the Nucleo], PLL1 to 400 MHz, direct SMPS supply,
  voltage scale 1. Caches and FPU on.
- Memory plan in the linker script, per the assessment: code in flash bank 1 with an ITCM section
  for hot kernels; DTCM for stack and hot state; AXI SRAM for large buffers; SRAM3 reserved for
  DMA buffers with an MPU region that makes it non-cacheable; SRAM4 reserved for the mailbox.
- Console on the ST-LINK virtual COM port [Verify pins], non-blocking, as in the Psyight node.
- DWT cycle counter. `bench` console command: runs every registered block on `dsp_testsig`
  input, prints cycles per sample (minimum, median, maximum over repeated runs) and the CRC32 of
  the output. `vec <block>` dumps a short output vector as hex for float comparison.
- Fault handler that prints the stacked registers and the fault status registers.
- The three execution levels exist as empty hooks: audio interrupt, deferred DSP (PendSV or a
  spare interrupt at lower priority; decide and record), main loop.

**1.3 M4 parked.** A minimal M4 image that enters stop mode at once, as ST's templates do. No
option bytes are changed. Both images flash with one command.

**1.4 Target test.** `tools/target_test.py` opens the console, runs `bench` and `vec`, and
compares with the host library: CRC equality for fixed point, tolerance for float. It prints one
line per block and returns non-zero on a mismatch.

**1.5 CI file.** `.github/workflows/ci.yml`: host build and pytest on Windows; firmware build on
Linux with Arm GNU Toolchain 13.3. It runs once the owner creates the repository; do not create
it.

**Acceptance.**
- `cmake --preset host`, `cmake --build --preset host-release` and `pytest tests` pass.
- The firmware builds with no warnings in own code and prints its banner at 400 MHz (state how
  the frequency was confirmed).
- `python tools/target_test.py` passes for `dsp_gain_f32`.
- `docs/results/bench_b1.md` holds the first cycle table. The commands are in `CLAUDE.md` and
  `README.md`.
- The recovery procedure for a wrong supply setting is in PROGRESS, with its source.

**Design notes:** the build and test route; the memory and cache plan.
**Exercise:** `dsp_dcblock_f32`, a one-pole DC blocker. Header, reference model and tests are
given; the owner writes the kernel and reports its cycles per sample.
**Stop for the owner with:** the cycle table, and the choice made for the deferred level.

## 4. Batch 2: audio pass-through on breakouts

Goal: analogue in to analogue out through the M7 at 48 and 96 kHz, with latency and CPU load
measured, on a PCM1808 ADC module and a PCM5102A DAC module.

**Owner supplies:** the two modules, the wiring from the pin table this batch produces, a scope,
a signal source, a loopback cable.

**2.1 Pin plan.** One SAI with two sub-blocks: transmit as master, receive synchronous to it.
Check every pin against the Nucleo board manual's tables for Ethernet, the ST-LINK serial port,
USB, the LEDs and the solder bridges [Verify]. Write the table to `docs/notes/pin_plan.md` with
the manual's page for each row. Reserve, without using them yet: the I2S_CKIN pin, an SPDIFRX
input, an I2C bus and the USB pins.

**2.2 Clocks.** PLL3 feeds the SAI; MCLK out at 256 fs. Record the actual sample rate and its
error in ppm for 48 and 96 kHz. The PCM5102A can run without MCLK; the PCM1808 needs it.

**2.3 The audio interrupt.**
- DMA in circular mode with half and full callbacks. Block size is a build parameter: 16, 32 or
  64 frames. Buffers in SRAM3, aligned to the cache line.
- Per block: convert the 24-bit samples to float, call one `audio_process(in, out, n)`, convert
  back with saturation. Pass-through with `dsp_gain_f32`.
- Outputs muted at start, ramped up on the first good block.

**2.4 Instrumentation.**
- A GPIO that is high for the length of the audio interrupt.
- Cycles per block: minimum, mean, maximum, and the load as a share of the block period.
- An overrun counter: a block that had not finished when the next one arrived.
- `stat` console command prints all of it.

**2.5 Measurements, with written procedures in `docs/notes/latency.md`.**
- Analogue in to out latency on the scope, at block sizes 16, 32 and 64, at 48 and 96 kHz.
  Before measuring, write the expected value: converter group delays from the datasheets plus
  the buffering formula. Report expected against measured.
- Interrupt time and jitter from the GPIO.
- A one-hour run: zero overruns.

**Acceptance.** Clean pass-through at both rates (the owner listens or checks on the scope);
the latency table with expected and measured values; zero overruns over an hour; the pin plan
checked against the manual.

**Design notes:** the audio interrupt and its buffering; the latency model.
**Exercise:** `dsp_convert`: 24-bit integer to float and back with saturation is provided. The
owner adds TPDF dither on the way out, with a test that checks the error spectrum is flat and
free of signal-dependent components for a low-level sine.
**Stop for the owner with:** the latency table and the recommended block size.

## 5. Batch 3: filters, float and Q31

Goal: the equaliser building blocks in both number formats, with the first real fixed-point
study and the float policy decided by measurement.

**3.1 Blocks.**
- `dsp_biquad_f32`: transposed direct form II, single section and cascade.
- `dsp_biquad_q31`: direct form I, coefficients in Q2.30, 64-bit accumulator, with first-order
  error feedback as a build-time or init-time option. State the rounding and saturation rules.
- `dsp_coef`: design functions in double precision for peaking, low and high shelf, low-pass and
  high-pass (second order, and Butterworth to fourth order as cascades), from frequency, gain
  and Q. Quantisation to Q2.30 is a separate function with a reported error.
- `dsp_peq`: four bands plus a high-pass, built from the above.
- Coefficient changes without clicks: ramp the coefficients across a set number of blocks.
  Measure the zipper noise for a fast sweep and state the limit. If ramping is not clean enough
  at low frequencies, crossfade two filters instead and record why.

**3.2 Studies, each a short table and a plot in `docs/results/`.**
- **Noise at low frequency.** A 20 Hz high-pass and a 40 Hz peak with Q 0.7 to 10, at 48 and
  96 kHz, with a -60 dBFS 1 kHz sine and with a full-scale sine. Compare float32 TDF-II, Q31
  DF-I without error feedback, Q31 DF-I with it, and a float64 reference. Report signal to noise
  for each.
- **Speed.** Cycles per sample per section on the target for each variant, against CMSIS-DSP's
  `arm_biquad_cascade_df2T_f32` and its Q31 direct form I functions.
- **Fused multiply-add.** Cycles and host-to-target error with contraction on and off. Decide,
  set the compiler flags on both sides, and set the float tolerance from the result.
- **Denormals.** Cycles on an input that decays into silence, with flush-to-zero off and on.
  Decide. If flush-to-zero is chosen, the host harness sets the matching mode.
- **Cramping.** The response of a peak at 10 to 20 kHz at 48 kHz against the analogue
  prototype. Report the error. A matched design is a stretch item, not required.

**3.3 Tests.**
- Float: against `scipy.signal.sosfilt` in float64, within the tolerance set above.
- Q31: bit-exact against the Python integer model, with and without error feedback.
- Design functions: magnitude at 31 log-spaced frequencies within 0.01 dB of the analytic
  response.
- Stability: random coefficient sweeps within the legal ranges never produce a non-finite or
  saturated output from a bounded input.

**3.4 On the target.** The PEQ runs in the pass-through. Bands are set from the console.
`bench` reports every variant.

**Acceptance.** All tests pass on host and target; the five studies are in `docs/results/` with
their commands; the SPEC's budget rows for filters are replaced by measurements; the float
policy is in the decision log.

**Design notes:** biquad structures and why each format uses the one it does; coefficient design
and quantisation; the float policy.
**Exercise:** add a notch and an all-pass to `dsp_coef` with tests; then write a variant of the
float kernel that processes two channels in one loop and beat the measured baseline.
**Stop for the owner with:** the noise and speed tables, and the two policy decisions.

## 6. Batch 4: USB audio, full speed (portfolio checkpoint P1)

Goal: the Nucleo and the breakouts appear on Windows as a sound card with the in-box driver,
play and record without dropouts, and carry the PEQ.

**4.1 First, the risk.** Before any other work: bring up TinyUSB (pinned commit, the Synopsys
device driver) on the Nucleo's user USB connector [Verify the instance and pins] with the
smallest UAC2 device that has an asynchronous playback endpoint and an explicit feedback
endpoint. Confirm that Windows 11 enumerates it and plays without glitches. Developers report
that Windows wants a 4-byte feedback value at full speed; find out and record what works. If
Windows cannot be made to accept it, stop and report.

**4.2 The device.**
- Composite: UAC2 with 2 playback and 2 record channels, plus a CDC serial port reserved for the
  control link.
- Formats: 24 bits in 4-byte subslots. Rates: 44.1 and 48 kHz full duplex. 88.2 and 96 kHz are
  offered so that one direction can run alone; say in the README that duplex at those rates
  needs rev B. If offering them confuses Windows, drop them and record it.
- Both endpoints asynchronous. The device clock is the master; the host follows the feedback.

**4.3 Buffering.**
- A ring between the USB side and the audio interrupt in each direction, aimed at half full.
- Track minimum and maximum fill. On underrun play silence and count; on overrun drop and count.
- The USB interrupt sits below the audio interrupt. The TinyUSB task runs in the main loop.
- A sample-rate change mutes, reprograms PLL3 and the SAI, flushes the rings and unmutes.

**4.4 Signal flow for this batch.** USB playback through the PEQ to the DAC; ADC to USB record;
a direct monitor path from ADC to DAC with its own gain. A digital loopback mode returns USB
playback to USB record untouched, for transport tests.

**4.5 Tests, as scripts in `tools/`.** Use WASAPI exclusive mode; shared mode goes through the
Windows mixer and is not bit-exact.
- Transport: 24-bit noise through the digital loopback comes back bit-exact, at 44.1 and 48 kHz.
- Soak: one hour of duplex streaming with the fill levels logged. No underrun, no overrun, fill
  within a stated band.
- Round trip: a pulse through a loopback cable from DAC to ADC; report the latency in samples
  and ms with its parts (USB buffers, block, converters).
- Rate changes: 20 switches between 44.1 and 48 kHz without a hang or a click above a stated
  level.

**Acceptance.** The four tests pass with their numbers in PROGRESS; Windows needs no driver
file; the README shows the measured tables.

**Checkpoint P1.** The project is now showable. Update the README as a portfolio page: what it
is, a photo placeholder for the owner, the latency, CPU and noise tables with their commands.
**Stop for the owner with:** the question of whether to create the public GitHub repository now.

**Design notes:** asynchronous USB audio and the feedback loop; buffer sizing.
**Exercise:** `dsp_nco_q31`, a test-tone oscillator from a phase accumulator and a sine table
with linear interpolation. The owner measures its distortion in Python for three table sizes
and picks one.

## 7. Batch 5: shield rev A design

Goal: order files for a 4-layer shield that plugs onto the Nucleo-H755ZI-Q and carries
everything analogue. Five stages; stop for the owner after each. No orders are placed by Claude.

**Scope of rev A.** 2 balanced line inputs; 4 outputs (balanced monitor pair, headphone pair with
amplifier); converters on one TDM bus; two audio oscillators (22.5792 and 24.576 MHz) selected
by GPIO, feeding the converters and the MCU's I2S_CKIN; S/PDIF in and out (optical first, because
it adds no ground connection); a header for an OLED and two encoders; 12 V DC input; the Nucleo
powered from the shield. Mid-grade analogue. SMT on the top side only; through-hole parts fitted
by hand. USB stays on the Nucleo.

**Stage 1: part selection.** `docs/notes/converter_trade_study.md`.
- Candidates: AK4619VN, CS42448, PCM3168A, and a separate ADC with DACs. For each: dynamic range
  and distortion from the datasheet, TDM and 96 kHz support, clocking needs, supply rails,
  package, live LCSC or JLC stock and price with the date checked, and whether JLC lists it as
  basic, preferred or extended.
- The same table, shorter, for op-amps, regulators, the split-rail converter, the oscillators,
  the headphone amplifier, the optical modules and the jacks.
- A recommendation with the reason, and the runner-up.

**Stage 2: architecture.** `docs/notes/shield_architecture.md`.
- Block diagram and level diagram: nominal +4 dBu, the dBu value of 0 dBFS at input and output
  (propose one and say what it costs in noise and headroom), gain of each stage.
- Noise budget for the input and output chains against the converter's floor.
- Power tree: 12 V in, protection against reverse polarity and over-voltage, the analogue rails
  and how they are made, the digital rails, a current budget, and how the Nucleo is fed
  [Verify the allowed input and the jumper setting in the board manual].
- Grounding: one ground plane, placement by zones, where the 12 V return, the USB shield and the
  jack sleeves connect, and what that means for a ground loop through the PC.
- Mute and sequencing: relays or mute transistors on the outputs, held muted until the rails and
  clocks are good, and during rate changes and power-down.
- Protection: ESD and over-voltage on the jacks, DC blocking.
- The pin map onto the Nucleo headers, extending `docs/notes/pin_plan.md`.
- Test points, and the bring-up order batch 7 will follow.
- Board size against JLC's price steps: the shield must span both Nucleo headers and hold the
  jacks; say what the size costs.

**Stage 3: schematic.** KiCad 10 project in `hw/shield-a/`, hierarchical sheets by block.
- Before editing KiCad files from a script, check that KiCad does not have them open; tell the
  owner to reload afterwards.
- ERC clean. A review against a written checklist (decoupling per pin, reference pins, clock
  termination, unused inputs, power sequencing, every net to a header pin checked against the
  pin plan) goes into `docs/notes/shield_schematic_review.md`.

**Stage 4: layout.** First ask the owner who routes: he does, with Claude's rules and review; or
Claude proposes a routed board for his review. Either way Claude writes
`docs/notes/shield_layout_rules.md`: stack-up, placement by zone, the clock and TDM routes, the
analogue input and output routes, the switching converter's loop, keep-outs. DRC clean.

**Stage 5: order package.** Gerbers, BOM and placement file for JLC Economic assembly; a list of
the parts JLC will fit and the parts fitted by hand; a count of extended parts; the cost read
from a live quote by the owner. The owner orders.

**Acceptance.** Each stage's document exists and the owner has signed it off in PROGRESS; ERC
and DRC are clean; the SPEC's rev A hardware section is complete.

**Design notes:** the stage documents are the notes.
**Exercise:** before reading stage 2, the owner works out the noise and level budget of the
input stage by hand from the chosen parts' datasheets, then compares with Claude's.

## 8. Batch 6: dynamics and saturation

Goal: the compressor, gate, limiter and saturation, tested on the host and timed on the target.
It needs no shield.

**6.1 Blocks.**
- `dsp_env`: peak and RMS detectors with attack and release.
- `dsp_comp`: feed-forward, gain computed in the log domain, soft knee, make-up gain, optional
  side-chain high-pass. Follow the structure analysed in Giannoulis, Massberg and Reiss, "Digital
  dynamic range compressor design" (JAES 2012); say which of its detector placements is used.
- `dsp_gate`: threshold with hysteresis, hold and release.
- `dsp_limiter`: look-ahead delay, peak hold and smoothed gain so the ceiling is never exceeded;
  true-peak detection by 4x oversampling as in ITU-R BS.1770. Its latency is a parameter and is
  reported.
- `dsp_oversample`: 2x and 4x up and down with polyphase half-band filters. State the passband
  ripple and stopband attenuation.
- `dsp_saturate`: a soft waveshaper run inside the oversampler.

**6.2 Studies.**
- **Log and exponent.** Cycles and error of fast approximations against the C library's
  functions. Decide what runs per sample and what runs per block.
- **Aliasing.** A swept sine through the saturator with no oversampling, 2x, 4x, and first-order
  antiderivative anti-aliasing at 1x. Report the worst alias level for each and the cycles.
- **Cost.** Cycles per sample for each block; update the SPEC budget.

**6.3 Tests.**
- Compressor static curve within 0.1 dB of the design at 20 input levels.
- Attack and release times measured from step responses within 5 % of the setting.
- Limiter: the true peak of the output, measured in Python at 8x oversampling, never exceeds the
  ceiling on a set of hostile signals (full-scale square, inter-sample peaks, bursts).
- Gate: no chatter on a signal that hovers at the threshold.
- Oversampler: passband and stopband measured against the stated figures.

**Acceptance.** Tests pass on host and target; the three studies are in `docs/results/`; a
latency table lists every block that adds delay.

**Design notes:** the compressor; the limiter and true peak; oversampling and aliasing.
**Exercise:** design a half-band filter in Python to a stated stopband, export the coefficients,
and show with a measurement that it meets the figure in the C oversampler.

## 9. Batches 7 to 13: outlines

Each of these gets a detailed spec, written like sections 3 to 8, when its inputs exist.

**Batch 7: shield bring-up and lab session.** Follow the bring-up order from batch 5, stage 2:
rails unloaded, rails loaded, clocks, converter control, digital loopback through the converter,
analogue. Say for every fault what was measured and what is guessed, and reproduce before fixing.
Switch the SAI clock to the oscillators through I2S_CKIN and repeat batch 4's soak. Then one lab
session with a written protocol: frequency response, THD+N against level and frequency, dynamic
range, crosstalk, maximum level, output noise, for each input and output. Results against the
SPEC targets, with the limiting part named where a target is missed.

**Batch 8: strips, monitor mixer, reverb, metering, host control.** The full path except room
correction. New blocks: matrix mixer with pan law; a feedback delay network reverb (8 lines,
modulated, with damping); BS.1770 loudness and peak meters; headphone crossfeed. The parameter
registry (id, label, unit, range, default, smoothing) and the control protocol over the CDC
port; a Python control script first, a GUI only if the owner asks. Gate: the budget table from
batches 3 and 6 must show the path fits under the ceiling at 96 kHz; if it does not, propose
what runs at 48 kHz before writing code.

**Batch 9: room correction.** Start with a costing spike: time real FFTs of 64 to 2048 points on
the target. Then the design from the assessment (correction 4): uniform partitions of 256 to
512 samples, computed at the deferred level with a deadline check and an overrun counter, one
partition of latency on the monitor outputs only. Measurement with the lab microphone on the
PC, filter design in Python (state the target curve, the smoothing and the limits on boost),
upload over the control link, room measured again. Stretch: non-uniform partitions to bring the
latency down to one block.

**Batch 10 (stretch): S/PDIF and ASRC.** The receiver peripheral and S/PDIF out from an SAI.
A software sample-rate converter between the incoming clock and the device clock: a polyphase
interpolator driven by a rate estimate from the buffer fill. Conversion quality measured in the
digital domain.

**Batch 11 (stretch): dual-core split and front panel.** Control, the protocol and the user
interface move to the M4 under FreeRTOS; the M7 keeps audio and USB audio. A mailbox in SRAM4
with a hardware semaphore. OLED and encoders.

**Batch 12 (stretch): rev B.** The H755 and a ULPI PHY on one board for USB high speed and
96 kHz duplex with 4 channels each way; the supply scheme decided for the clock target; an
enclosure. Characterised again in the lab.

**Batch 13: portfolio write-up.** A datasheet-style page of measured figures; the latency and
CPU tables; the fixed-point against float study; a short demo recording made with synthetic or
the owner's own audio; and a list of claims the owner can make, each with its measurement and
command.

## 10. What the owner needs to buy or book, and when

| For batch | Item |
|---|---|
| 2 | PCM1808 ADC module, PCM5102A DAC module, jumper wires, a loopback cable |
| 5 | Nothing until stage 5; then the shield order and the hand-fitted parts |
| 7 | A 12 V supply; a session with the university audio analyser |
| 9 | A session with the university measurement microphone |

## 11. Additions of 2026-11-17 (owner's feature review)

SPEC sections 2, 6.7 and 7 hold the requirements. Where they land:

| Addition | Batch | Work |
|---|---|---|
| Tone: bass, mid, treble | 3 | `dsp_tone_f32` from the biquad and coefficient code, with a self-test case and a cycle count. Driven from the console until the panel exists. |
| USB MIDI | 4 | Add the MIDI class to the composite device and prove enumeration beside UAC2 on Windows. Control change handling arrives with the registry in batch 8. |
| Ableton | 4 | Test with an ASIO wrapper over the in-box driver; record the buffer size and latency that work. |
| Record-source switch and the record tap | 4, 8 | Batch 4 switches between two sources; batch 8 adds the real tap after the effect slot. |
| Control panel board | 5 | A second small board in the same KiCad project: potentiometers, buttons, LEDs, footswitch jack, the OLED and encoder header, a ribbon to the shield. Stage 2 settles the ADC pins or a multiplexer. |
| Panel firmware: ADC scan, filtering, hysteresis, buttons, LEDs | 8 | On the M7 main loop first; it moves to the M4 in batch 11. |
| Knob wins or PC wins, with soft takeover | 8 | Part of the registry. Unit-tested on the PC: no jump on takeover. |
| Effect slot | 8 | One effect at a time; each effect is its own block with a reference model. Gate: the budget table. Read the transcripts listed for batch 8 first. |
| Tempo from MIDI clock and tap tempo | 8 | For the echo and the modulated effects. |
| Presets in flash | 8 | |
