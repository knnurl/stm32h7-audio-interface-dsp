# Implementation spec: the DSP audio interface, in batches

Written 2026-11-15 and revised 2026-11-17 with the owner's feature review (section 13 lists
what changed). For the agent that implements it (Claude Opus, working in
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

The device (concept A, with the owner's additions of 2026-11-17; SPEC section 2 is the source):

```
LINE IN 1-2 -> ADC -> [ Input strip x2: trim, HPF, 4-band PEQ, gate, compressor, saturation ]
                         |-> record source A: the processed inputs -> USB record 1-2
                         '-> MONITOR MIXER <- USB play 1-2, S/PDIF in, reverb return (BLEND knob)
                                   v
                             [ Effect slot: one of 8 effects ] -> record source B: the mix
                                   v
                             [ Tone: BASS, MID, TREBLE knobs ]  (never recorded)
                                   |-> [ Speaker stage: room FIR, PEQ, delay, limiter, MUTE, DIM, MONITOR ] -> OUT 1-2
                                   '-> [ Headphone stage: PEQ, crossfeed, limiter, PHONES ]              -> OUT 3-4
Control: 7 knobs, 5 buttons, footswitch, LEDs | USB control link | USB MIDI | presets in flash
```

One batch is one reviewable unit and one session. It ends with the build clean, the tests
passing, its numbers and commands in `docs/PROGRESS.md`, its review pack written, and a stop for
the owner. Do not start the next batch in the same session unless the owner said so.

| Batch | Content | Needs hardware | Depends on | Status (2026-11-17) |
|---|---|---|---|---|
| 0 | Project documents | No | Nothing | Done |
| 1 | Foundation: host library, test harness, firmware skeleton | Nucleo, for the target run | 0 | Built; target run open |
| 2 | Audio pass-through on breakouts | Nucleo, two breakouts, scope | 1 | Waiting for the modules |
| 3 | Filters, float and Q31, and the tone control | Host part: none. Target part: Nucleo | 1 | Not started |
| 4 | USB audio, USB MIDI, Ableton. **Portfolio checkpoint P1** | Nucleo, breakouts | 2, 3 | Not started |
| 5 | Rev A boards: main board and control panel, five stages | No | 0 | Outline drafted |
| 6 | Dynamics and saturation | Host part: none. Target part: Nucleo | 3 | Not started |
| 7 | Bring-up of both boards, lab session | Both boards, lab analyser | 4, 5 | Not started |
| 8a | Control core: registry, knob ownership, protocol, MIDI mapping, presets | None (the UART console on the Nucleo for the target part) | 1 | Not started |
| 8b | Effect slot, reverb and tempo | Host part: none. Target part: Nucleo | 3, 6 | Not started |
| 8c | The full signal path on the boards | Both boards | 6, 7, 8a, 8b | Not started |
| 8d | Control panel firmware | Panel board, or pots and buttons on a breadboard | 8a (7 for the real panel) | Not started |
| 9 | Room correction | Both boards, lab microphone | 8c | Not started |
| 10 | S/PDIF and ASRC (stretch) | Both boards | 8c | Not started |
| 11 | Dual-core split, display and encoders (stretch) | Both boards | 8c, 8d | Not started |
| 12 | Rev B main board (stretch) | New board | 7, 8c | Not started |
| 13 | Portfolio write-up | No | 9 | Not started |

Batches 0 to 6 and 8a to 8d are specified in full below. Batches 7 and 9 to 13 are outlined with
their constraints and gates; each gets its own detailed spec once the measurements it depends on
exist. Batch 5 runs alongside the firmware batches.

**Without any hardware,** this order makes progress: the host parts of 3, 6 and 8b, then 8a.
Each such batch stops before its target part and says so in PROGRESS.

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
  (Apache-2.0), TinyUSB (MIT), FreeRTOS (MIT, batch 11 only). Test tools only, never linked into
  the firmware: numpy, scipy, pytest, pyserial, and from batch 4 mido with python-rtmidi (MIT).
  Third-party sources are fetched at pinned commits into a gitignored folder, never committed.
- **Private data:** no copyrighted audio in the repository. Test signals are synthetic.
- **Writing:** British English, no em dashes, sentence case for labels, units in names (`_hz`,
  `_ms`, `_samples`, `_db`, `_cycles`), `[Verify]` on unmeasured claims.
- **Docs in the same commit:** the SPEC section a change touches, a decision-log row for every
  decision, `docs/PROGRESS.md`, and the commands in `CLAUDE.md` and `README.md`.

### 1.1 The review pack every batch ends with

- **Transcripts first.** Before writing the batch's code, read in full every transcript
  `docs/notes/transcripts_index.md` lists for the batch, and check the design against them.
  Each design note then has a **"From the transcripts"** section: what agrees, what differs and
  why, and what the transcripts suggest that was not done. Where they disagree with our
  measurements or SPEC decisions, ours win and the note says so. Exercise answers stay out.
- **A design note per DSP block or subsystem,** in `docs/notes/<name>.md`, on this template:
  purpose; the maths; the structure chosen and the alternatives rejected, with the reason; the
  numerical behaviour (noise, overflow, limits of validity); measured cycles per sample on the
  target; the test evidence; open questions.
- **One exercise for the owner,** in `docs/exercises/EX<batch>_<name>.md`: the task, a header or
  stub, tests that fail until it is done, and the acceptance numbers. Do not write the solution.
  Review the owner's solution when he asks.
- **A PROGRESS entry:** what was done, the transcripts read, the measured numbers, the exact
  commands, what the owner must do or decide next.

### 1.2 Code rules (batch 0 copies these into `CLAUDE.md`)

- `dsp/` is hardware-free C11: no HAL, no allocation, no stdio, no global mutable state. It
  builds unchanged for the PC and the target. `ctl/` (from batch 8a: parameters, protocol, MIDI,
  presets, panel input) follows the same rules.
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

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1).

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

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1).
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
the manual's page for each row. Reserve, without using them yet:
- the I2S_CKIN pin, an SPDIFRX input, a second SAI sub-block for S/PDIF out, an I2C bus;
- the user USB data pins, which the main board's USB-C socket will drive (SPEC V13);
- seven ADC inputs for the potentiometers (or one input and three GPIO for a multiplexer, SPEC
  V12), five button inputs, the footswitch input, seven LED outputs, preferably on timer
  channels for PWM;
- for batch 11: an SPI or I2C bus for the display and two timer pairs in encoder mode.

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

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). Clean pass-through at both rates (the owner listens or checks on the scope);
the latency table with expected and measured values; zero overruns over an hour; the pin plan
checked against the manual.

**Design notes:** the audio interrupt and its buffering; the latency model.
**Exercise:** `dsp_convert`: 24-bit integer to float and back with saturation is provided. The
owner adds TPDF dither on the way out, with a test that checks the error spectrum is flat and
free of signal-dependent components for a low-level sine.
**Stop for the owner with:** the latency table and the recommended block size.

## 5. Batch 3: filters, float and Q31

Goal: the equaliser building blocks in both number formats, with the first real fixed-point
study and the float policy decided by measurement; and the tone control behind the BASS, MID and
TREBLE knobs. The host part (3.1 to 3.3, 3.5) needs no hardware.

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

**3.4 On the target.** The PEQ and the tone control run in the pass-through. Bands and tone
gains are set from the console. `bench` reports every variant.

**3.5 Tone control (`dsp_tone_f32`).** Monitors and headphones only, never recorded (SPEC 2).
- Three bands on one stereo bus, coefficients shared by both channels: a low shelf at 100 Hz, a
  peak at 1 kHz with Q 0.7, a high shelf at 10 kHz, shelf slope 1 (RBJ cookbook). These corner
  frequencies are a proposal: the owner confirms them at the start of the batch, by ear on the
  breakouts if they are wired. Gain -12 to +12 dB per band.
- Input is the gain in dB per band. The block smooths each gain (one-pole on dB, 20 ms) and
  recomputes that band's coefficients once per block from the smoothed value. Measure what the
  recompute costs per block (each design calls `sinf`, `cosf` and `powf`) and the zipper noise
  of a full sweep; if either fails, interpolate coefficients instead and record why.
- Flat at centre: a band whose smoothed gain is exactly 0 dB is skipped and its state cleared.
  The block enters and leaves the skip only at exactly 0 dB, where the band is the identity, so
  the change cannot click.
- Tests:
  - all three bands at 0 dB: output equals input bit for bit;
  - magnitude at 31 log-spaced frequencies within 0.05 dB of the analytic design, for each band
    at -12, -6, +6 and +12 dB and for five combinations of all three;
  - a sweep of each gain from -12 to +12 dB in 100 ms on a 50 Hz and on a 5 kHz sine at
    -6 dBFS, compared with the same sweep designed per sample in float64: difference under
    -60 dBFS;
  - stereo channels identical when fed identical input.
- A self-test case `tone_f32`, and its cycles per sample on the target for the stereo bus, into
  the SPEC budget row (estimate 60).

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). All tests pass on host and target; the five studies are in `docs/results/` with
their commands; the SPEC's budget rows for filters are replaced by measurements; the float
policy is in the decision log.

**Design notes:** biquad structures and why each format uses the one it does; coefficient design
and quantisation; the float policy; the tone control (bands, smoothing, the exact centre).
**Exercise:** add a notch and an all-pass to `dsp_coef` with tests; then write a variant of the
float kernel that processes two channels in one loop and beat the measured baseline.
**Stop for the owner with:** the noise and speed tables, the two policy decisions, and the tone
control's corner frequencies if he has not confirmed them.

## 6. Batch 4: USB audio, USB MIDI and Ableton (portfolio checkpoint P1)

Goal: the Nucleo and the breakouts appear on Windows as one USB device with an audio interface,
a MIDI port and a serial control port; they play and record without dropouts, carry the PEQ and
the tone control, and work in Ableton Live.

**Owner supplies:** Ableton Live on his PC (he confirms the version at the start), the loopback
cable, and his ears for the listening checks.

**4.1 First, the risks.** Before any other work:
- Bring up TinyUSB (pinned commit, the Synopsys device driver) on the Nucleo's user USB connector
  [Verify the instance and pins: SPEC V1] with the smallest UAC2 device that has an asynchronous
  playback endpoint and an explicit feedback endpoint. Confirm that Windows 11 enumerates it and
  plays without glitches. Developers report that Windows wants a 4-byte feedback value at full
  speed; find out and record what works. If Windows cannot be made to accept it, stop and report.
- Count the endpoints and FIFO bytes the full composite device needs against the OTG_FS
  peripheral [Verify its endpoint count and FIFO size in the reference manual: SPEC V16]:
  - UAC2: control, isochronous OUT, isochronous IN, feedback IN;
  - MIDI: bulk IN and bulk OUT;
  - CDC: bulk IN, bulk OUT and interrupt IN.
  If it does not fit, drop CDC and carry the control protocol on a vendor-specific interface or
  on MIDI system exclusive messages; record the choice in the decision log.

**4.2 The device.**
- Composite: UAC2 with 2 playback and 2 record channels; USB MIDI 1.0 with one port in and one
  out; CDC serial for the control link. Product string "DSP Interface" (the owner may rename it);
  serial number from the chip's unique ID, so Windows keeps its settings per unit.
- Formats: 24 bits in 4-byte subslots. Rates: 44.1 and 48 kHz full duplex. 88.2 and 96 kHz are
  offered so that one direction can run alone; say in the README that duplex at those rates
  needs rev B. If offering them confuses Windows or Ableton, drop them and record it.
- Both audio endpoints asynchronous. The device clock is the master; the host follows the
  feedback.
- MIDI in this batch: enumeration, and a loopback test mode (behind a console command) that sends
  every received message straight back. Control change, program change and clock handling arrive
  with batch 8a.
- CDC in this batch: carries the existing console commands, so the ST-LINK port is not needed in
  use.

**4.3 Buffering.**
- A ring between the USB side and the audio interrupt in each direction, aimed at half full.
- Track minimum and maximum fill. On underrun play silence and count; on overrun drop and count.
- The USB interrupt sits below the audio interrupt. The TinyUSB task runs in the main loop.
- A sample-rate change mutes, reprograms PLL3 and the SAI, flushes the rings and unmutes.

**4.4 Signal flow for this batch.**
- USB playback through the PEQ and the tone control to the DAC.
- A direct monitor path from the ADC to the DAC with its own gain.
- Record source, set from the console: `src inputs` (the ADC, default) or `src mix` (the sum of
  playback and direct monitor, taken before the tone control: the same place as the real record
  tap of batch 8c, so Ableton tests made now stay valid).
- A digital loopback mode that returns USB playback to USB record untouched, for transport tests.

**4.5 Tests, as scripts in `tools/`.** Use WASAPI exclusive mode for the audio scripts; shared
mode goes through the Windows mixer and is not bit-exact.
- Transport: 24-bit noise through the digital loopback comes back bit-exact, at 44.1 and 48 kHz.
- Soak: one hour of duplex streaming with the fill levels logged. No underrun, no overrun, fill
  within a stated band.
- Round trip: a pulse through a loopback cable from DAC to ADC; report the latency in samples
  and ms with its parts (USB buffers, block, converters).
- Rate changes: 20 switches between 44.1 and 48 kHz without a hang or a click above a stated
  level.
- Record source: with the PEQ and the tone control flat, `src mix` returns playback bit-exact at
  48 kHz.
- MIDI: the port appears in Windows; 10 000 messages of mixed kinds sent through the loopback
  mode come back complete and in order (`mido` with `python-rtmidi`).
- Ableton Live (the owner runs it, Claude writes the procedure in
  `docs/notes/ableton_setup.md`):
  - the audio path through an ASIO wrapper over the in-box driver, FlexASIO or ASIO4ALL
    [Verify the current options on Windows 11, including whether Windows now offers an ASIO
    path for class-compliant devices: SPEC V11];
  - the smallest buffer size that runs 30 minutes without a dropout, the latency Ableton reports,
    and the round trip measured with Ableton's driver error compensation through the loopback
    cable;
  - one take recorded from `src inputs` and one from `src mix`;
  - the device listed as a MIDI input and output in Ableton's preferences.

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). The tests pass with their numbers in PROGRESS; Windows needs no driver file; the
README shows the measured tables, and the Ableton settings that work.

**Checkpoint P1.** The project is now showable. Update the README as a portfolio page: what it
is, a photo placeholder for the owner, the latency, CPU and noise tables with their commands.
**Stop for the owner with:** the question of whether to create the public GitHub repository now.

**Design notes:** asynchronous USB audio and the feedback loop; buffer sizing; the composite
device and its endpoint budget; Ableton on Windows (drivers, buffer, latency compensation).
**Exercise:** `dsp_nco_q31`, a test-tone oscillator from a phase accumulator and a sine table
with linear interpolation. The owner measures its distortion in Python for three table sizes
and picks one.

## 7. Batch 5: rev A boards (main board and control panel)

Goal: order files for the two rev A boards. Five stages; stop for the owner after each. Claude
places no order. The enclosure is left for later (owner, 2026-11-17), but the boards must not
make it harder: stage 2 fixes a mechanical interface table that the enclosure work will use.
`docs/notes/shield_outline.md` (sections 9 to 11) and `docs/notes/device_look.svg` are the
starting drafts.

**Scope of rev A.**
- **Main board.** 4 layers, about 160 by 100 mm, the Nucleo-H755ZI-Q plugged in underneath.
  Every rear connector on its rear edge, in one line: power switch, 12 V DC, USB-C, footswitch,
  optical in and out, line in 1 and 2, monitor out L and R. It carries:
  - power entry and all rails, including the Nucleo's supply;
  - two audio oscillators (22.5792 and 24.576 MHz) selected by GPIO, feeding the converter and
    the MCU's I2S_CKIN;
  - the converter on one TDM bus;
  - the balanced line input stages, the balanced monitor output stages with mute relays;
  - the headphone amplifier, unless stage 2 puts it on the panel board;
  - S/PDIF, optical only (it adds no ground connection);
  - the USB-C socket, data only, wired to the Nucleo's user USB data pins (SPEC V13);
  - the ribbon header to the panel board.
- **Control panel board.** 2 or 4 layers, about 160 by 52 mm, behind the front panel, laid out as
  `device_look.svg` shows: groups input, display, effect, tone, output, with monitor volume the
  large knob. It carries:
  - 7 potentiometers: bass, mid and treble with a centre detent; monitor; phones; FX amount;
    blend;
  - 5 buttons: FX select, FX on, tap, mute, dim;
  - 7 LEDs: signal and clip per input, mute, dim, FX on;
  - the headphone jack (6.35 mm, panel mount);
  - a header for the OLED and two encoders (fitted in batch 11);
  - the ribbon header.
- Mid-grade analogue. SMT on the top side only; through-hole parts fitted by hand. Jacks, pots
  and the USB-C socket are panel-mount types, fixed later by their nuts or screws, so no force
  reaches a solder joint.

**Stage 1: part selection.** `docs/notes/part_selection.md`.
- Converter candidates: AK4619VN, CS42448, PCM3168A, and a separate ADC with DACs. For each:
  dynamic range and distortion from the datasheet, TDM and 96 kHz support, clocking needs,
  supply rails, package, live LCSC or JLC stock and price with the date checked, and whether JLC
  lists it as basic, preferred or extended.
- The same table, shorter, for: op-amps, regulators, the split-rail converter, the oscillators,
  the headphone amplifier, the optical modules, the mute relays, the jacks.
- Panel parts: potentiometers with and without a centre detent, from one family so the shafts
  and heights match [Verify a family that offers both]; shaft type and length for a front panel
  of the thickness the owner expects to cut; buttons rated for long life; LEDs; the 6.35 mm
  headphone jack; the USB-C receptacle (through-hole shell legs) and its ESD array; the ribbon
  connector and its pitch.
- A recommendation with the reason, and the runner-up, for each.

**Stage 2: architecture.** `docs/notes/rev_a_architecture.md`.
- Block diagram and level diagram: nominal +4 dBu, the dBu value of 0 dBFS at input and output
  (propose one and say what it costs in noise and headroom), gain of each stage.
- Noise budget for the input and output chains against the converter's floor.
- Power tree: 12 V in, protection against reverse polarity and over-voltage, the analogue rails
  and how they are made, the digital rails, a current budget, and how the Nucleo is fed
  [Verify the allowed input and the jumper setting in the board manual: SPEC V7].
- Grounding: one ground plane per board, placement by zones, where the 12 V return, the USB
  shield, the jack sleeves and the ribbon's grounds connect, and what that means for a ground
  loop through the PC.
- Mute and sequencing: relays on the monitor outputs and a mute on the headphone amplifier, held
  muted until the rails and clocks are good, and during rate changes and power-down.
- Protection: ESD and over-voltage on every external connector, DC blocking.
- USB-C: CC resistors for a device port, ESD, VBUS sensing only; the data pair from the socket to
  the header pins (length, matched routing); which Nucleo solder bridges to open so its own
  socket is disconnected [Verify: SPEC V13]; the fallback, a short internal lead from the
  Nucleo's socket.
- Panel interface:
  - the ribbon pin-out, with grounds between groups of signals;
  - a clean reference for the potentiometers and an RC filter on each wiper;
  - seven ADC pins, or a multiplexer (SPEC V12);
  - button and footswitch inputs with pull-ups and RC filters, the footswitch working with both
    momentary and latching pedals;
  - LED drive: GPIO with PWM, or a driver.
- Headphone signal path: the amplifier on the main board with the line-level signal over the
  ribbon, or the amplifier on the panel board next to the jack. Compare crosstalk from the
  ribbon's digital lines, the ground return and the current in the ribbon; propose one.
- The pin map onto the Nucleo headers, extending `docs/notes/pin_plan.md`.
- Mechanical interface table in `docs/notes/mechanical_interface.md`: board outlines, mounting
  holes, the position and height of every rear connector and every front control, and the stack
  height of Nucleo, main board and tallest part [Verify against a 55 mm case: SPEC V14]. It is
  regenerated from the KiCad files by a script once they exist.
- Test points, and the bring-up order batch 7 will follow.
- Board sizes against JLC's price steps; say what the sizes cost.

**Stage 3: schematic.** Two KiCad 10 projects, `hw/rev-a/main/` and `hw/rev-a/panel/`, with a
shared symbol and footprint library in `hw/lib/`; hierarchical sheets by block.
- Before editing KiCad files from a script, check that KiCad does not have them open; tell the
  owner to reload afterwards.
- A script checks the ribbon: the same pin-out on both sides, from the two netlists.
- ERC clean. A review against a written checklist (decoupling per pin, reference pins, clock
  termination, unused inputs, power sequencing, every net to a header pin checked against the
  pin plan) goes into `docs/notes/rev_a_schematic_review.md`.

**Stage 4: layout.** The owner routes the analogue and clock nets (decided 2026-11-16). Claude
writes `docs/notes/rev_a_layout_rules.md` first (stack-up, placement by zone, the clock and TDM
routes, the analogue input and output routes, the switching converter's loop, the USB pair,
keep-outs), places the parts by zone to the floor plan, may route the low-risk digital nets, and
reviews the owner's routing against the rules. DRC clean on both boards. Control positions on the
panel board match the mechanical interface table.

**Stage 5: order package.** For both boards: Gerbers, BOM and placement files for JLC Economic
assembly; a list of the parts JLC will fit and the parts fitted by hand; a count of extended
parts; the cost read from a live quote by the owner. The owner orders.

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). Each stage's document exists and the owner has signed it off in PROGRESS; ERC
and DRC are clean on both boards; the SPEC's rev A hardware section is complete.

**Design notes:** the stage documents are the notes.
**Exercise:** before reading stage 2, the owner works out the noise and level budget of the
input stage by hand from the chosen parts' datasheets, then compares with Claude's.

## 8. Batch 6: dynamics and saturation

Goal: the compressor, gate, limiter and saturation, tested on the host and timed on the target.
It needs no audio hardware. The overdrive of batch 8b reuses the saturation and oversampler.

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

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). Tests pass on host and target; the three studies are in `docs/results/`; a
latency table lists every block that adds delay.

**Design notes:** the compressor; the limiter and true peak; oversampling and aliasing.
**Exercise:** design a half-band filter in Python to a stated stopband, export the coefficients,
and show with a measurement that it meets the figure in the C oversampler.

## 9. Batch 7: bring-up of both boards and the lab session (outline)

Gets its detailed spec when the boards are ordered.

- Follow the bring-up order from batch 5, stage 2: rails unloaded, rails loaded, clocks,
  converter control, digital loopback through the converter, analogue, then the panel board over
  the ribbon. Say for every fault what was measured and what is guessed, and reproduce before
  fixing.
- Switch the SAI clock to the oscillators through I2S_CKIN and repeat batch 4's soak.
- USB through the main board's USB-C socket: enumeration and a one-hour duplex soak with no
  error.
- Panel board: every potentiometer reads its full travel; reading noise per pot; every button,
  LED and the footswitch work; nothing from the ribbon is audible on the outputs at full
  monitor volume.
- One lab session with a written protocol: frequency response, THD+N against level and
  frequency, dynamic range, crosstalk, maximum level, output noise, for each input and output,
  headphones into 32 and 300 ohm. Results against the SPEC targets, with the limiting part named
  where a target is missed.

## 10. Batch 8: the device, in four parts

Batch 8 was one outline; the feature review made it too large for one session. It is split into
four parts with their own stops. Three of them need no audio hardware.

### 10.1 Batch 8a: control core

Goal: everything that turns a knob, a PC command or a MIDI message into a parameter value, as
hardware-free C tested on the PC. On the target it runs over the UART console, so it needs no
audio hardware; it moves to the USB serial port when batch 4 is done.

**Layout.** A new `ctl/` library beside `dsp/`, under the same rules (1.2), built into the host
DLL and the firmware. `tests/unit/` gets its tests; `tools/ctl.py` is the PC client.

**8a.1 Parameter registry (`ctl_params`).**
- Declared once, in one table (`ctl/src/ctl_param_table.c`). Each parameter has:
  - a stable numeric id, never reused (a removed parameter keeps its id reserved);
  - a name in `snake_case`, used by the protocol, and a label in sentence case, used by the PC
    client and later the display;
  - a unit, minimum, maximum, default, a curve (linear, dB, frequency) and a smoothing time;
  - flags: has a knob, has a MIDI control change, saved in presets, read-only (meters).
- The first table holds every parameter SPEC 2 and 6.7 name:
  - per input strip: trim, high-pass, four PEQ bands, gate, compressor, saturation;
  - mixer levels and pans, blend, reverb send and return;
  - effect select, effect on, effect amount, and each effect's own parameters (8b.2);
  - tone bass, mid and treble;
  - speaker stage PEQ, delay, limiter; headphone PEQ, crossfeed, limiter;
  - monitor volume, phones volume, mute, dim;
  - record source, tempo source, MIDI channel, footswitch type, knob ownership modes.
- Values are floats in engineering units, clamped to range on every write.
- Hand-off to the audio level: a single-producer single-consumer queue of (id, value) from the
  main loop to the audio interrupt, drained at the start of each block. Its depth is stated. On
  overflow the newest value for an id wins and nothing blocks; tested.

**8a.2 Knob ownership (SPEC 6.7).**
- Each parameter with a knob has a mode: knob wins, or PC wins.
- Knob wins: writes from the PC, MIDI or a preset to it are refused with a reason; the PC shows
  the knob's value.
- PC wins: any source may write. After a write from anything other than the knob, the knob is
  detached. It re-attaches when its position crosses the current value (pick-up), with a
  hysteresis of 1 % of travel so reading noise near the value does not detach it again.
- Tests on the PC:
  - no jump in the value on re-attach, approaching from either side;
  - a fast turn that crosses the value between two scans still re-attaches;
  - reading noise of +/-1 % near the value causes no change;
  - a mode change while detached;
  - a preset recall detaches every knob parameter that is in PC-wins mode.

**8a.3 Control protocol (`ctl_proto`).**
- Line-based text, one command per line, so a person can type it and Python can script it:
  `hello` (protocol version, firmware version, unit id), `list`, `get <name>`,
  `set <name> <value>`, `mode <name> knob|pc`, `meters on|off`, `preset save|load|list|name`,
  `src inputs|mix`, `tempo`, `stat`.
- Each command gets one reply line, `ok ...` or `err <code> <reason>`. Unsolicited lines (meters
  at 30 Hz, knob changes, tempo changes) start with `#`.
- Specified in `docs/notes/control_protocol.md` with a version number.
- The parser is transport-agnostic: the UART console now, the USB serial port after batch 4.
- Fuzz-tested on the PC: random bytes never crash it or write out of bounds (run under the MSVC
  address sanitiser).
- `tools/ctl.py`: a Python client with get, set, watch-meters and preset commands. A GUI only if
  the owner asks.

**8a.4 MIDI mapping (`ctl_midi`).**
- Channel: 1 by default, settable, or omni.
- Control change in: a fixed table maps CC numbers to parameters (`docs/notes/midi_map.md`); the
  7-bit value is scaled to the parameter's range along its curve. MIDI counts as a PC source for
  knob ownership (8a.2).
- Control change out (on by default, settable): a knob or button change sends its CC, so
  Ableton's MIDI map can learn the device's controls. A value that arrived by MIDI is not sent
  back.
- Program change in: recall a preset.
- Clock, start and stop in: passed to the tempo follower (8b.5).
- Tests: running status; real-time messages inside other messages; system exclusive skipped
  safely; scaling at 0, 64 and 127 for each curve.

**8a.5 Presets (`ctl_preset`, with a flash back end in `fw/`).**
- 8 slots. A preset holds every parameter flagged for presets, stored by id, so a newer firmware
  loads an older preset (unknown ids ignored, missing ids take their default).
- Store: the last sector of flash bank 2, written as an append-only log of records (slot,
  sequence number, length, CRC-32), erased only when full. The last good record of a slot wins; a
  bad CRC falls back to the previous record, then to defaults. Bank 2 belongs to the M4, whose
  linker script gives up that sector. The M7 runs from bank 1, so writing bank 2 should not stall
  it [Verify the sector size and read-while-write across banks: SPEC V17].
- Power-on state: a "current settings" record written 2 s after the last change, so the device
  starts as it was left.
- Tests on the PC with the flash simulated in RAM: a power cut at every byte of a write (the
  record is either complete or ignored); a full sector; a corrupted record; an old preset with
  fewer parameters.
- On the target: write and read back through the console; the time to write a record; audio is
  not disturbed (the overrun counter stays 0 while 100 records are written, once batch 2 exists).

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). All tests pass on the PC; the firmware builds with `ctl/` in it; on the Nucleo,
`tools/ctl.py` gets and sets parameters and saves and loads presets over the console.

**Design notes:** the registry and the audio hand-off; knob ownership and pick-up; the control
protocol; the MIDI map; the preset store.
**Exercise:** 14-bit control change for the three tone gains (CC n with CC n+32 as the fine
part), with tests that a 7-bit-only controller still works.
**Stop for the owner with:** the parameter table and the MIDI map (names, ranges, defaults,
curves) for review.

### 10.2 Batch 8b: effect slot, reverb and tempo

Goal: each effect as a tested block with a reference model, timed on the target; the slot that
switches between them without clicks; the reverb; the tempo follower. The host part needs no
hardware.

**Read first:** the transcripts listed for batch 8 in `docs/notes/transcripts_index.md` (comb
filters and delay lines #124, delay-based effects #140, all-pass #162, tremolo, overdrive #117
and #153).

**8b.0 Start by stopping for the owner** with two tables: the macro table (8b.2, what the FX
AMOUNT knob does per effect) and the memory budget (8b.6).

**8b.1 Building blocks.**
- `dsp_delayline`: circular buffer of power-of-two length; fractional read by linear, third-order
  Lagrange and first-order all-pass interpolation. A study of each one's error and modulation
  noise on a swept read position.
- `dsp_lfo`: sine, triangle, square with rounded edges, ramp; phase-accurate tempo sync;
  deterministic.
- `dsp_svf`: state-variable filter in the topology-preserving form, which stays stable under fast
  modulation. Compared with a biquad swept at the same rate.

**8b.2 The effects.** Each is `dsp_fx_<name>_f32`, stereo, with a reference model, a self-test
case and its cycles per sample.

| Effect | Algorithm | FX AMOUNT knob (proposed) | Other parameters (PC, MIDI, presets, later the encoders) |
|---|---|---|---|
| Echo | Stereo delay, tempo-synced or free; feedback through a low-pass and a high-pass; optional ping-pong | Mix | Time or note value, feedback, tone, ping-pong |
| Chorus | Two or three modulated taps at 10 to 30 ms | Depth and mix together | Rate, stereo spread |
| Flanger | One modulated delay of 0.5 to 10 ms, with feedback | Depth | Rate or note value, feedback |
| Phaser | 4 or 8 first-order all-pass stages swept by an LFO, with feedback | Depth | Rate or note value, stages, feedback |
| Tremolo | LFO on the gain; a stereo phase offset gives auto-pan | Depth | Rate or note value, shape, stereo phase |
| Sweep filter | DJ style: below the middle a low-pass closes, above it a high-pass opens, the middle is off | Position | Resonance |
| Overdrive | `dsp_saturate` inside the 4x oversampler of batch 6; tone filters before and after; symmetric or asymmetric curve | Drive, with level compensation | Tone, curve, output level |
| Bit crusher | Bit depth reduction and sample-and-hold rate reduction, optional dither | Amount (depth and rate together) | Bits, rate, dither |

The FX AMOUNT knob has no centre detent, so the sweep filter gets a dead zone of +/-3 % around
the middle; the owner may prefer a detented pot there (a batch 5 part choice).

**8b.3 The slot (`dsp_fxslot`).**
- One effect active. FX SELECT steps through the list, FX ON toggles the slot, AMOUNT drives the
  active effect's macro.
- Changing effect: the old one fades out over 30 ms; the new one starts from cleared state and
  fades in over 30 ms.
- Turning the slot off: with trails on (the default for the echo) the effect's input is cut and
  its tail rings out; with trails off it fades out over 30 ms.
- Position: after the monitor mixer, before the record tap, the tone control and the output
  stages (SPEC 2).
- Tests: switching effects and on and off on a sine produces no step above a stated level; echo
  trails decay at the set feedback.

**8b.4 Reverb (`dsp_reverb_f32`).** On the send and return of the monitor mixer, not in the slot.
- An 8-line feedback delay network. The feedback matrix is Householder or Hadamard: the design
  note says which and why.
- Delay lengths mutually prime and scaled with the sample rate; a first-order low-pass in each
  loop with its gain set from the decay time at low and high frequency; slow modulation of two
  lines against metallic ringing; pre-delay.
- Tests: decay time measured by Schroeder backward integration within 10 % of the setting at
  500 Hz and 4 kHz; no growth of energy over 60 s at the longest decay; echo density measured
  and stated.

**8b.5 Tempo (`ctl_tempo`, in `ctl/`).**
- Sources: MIDI clock (24 ticks per quarter note; lost after 0.5 s without a tick), tap tempo
  (the average of the last four taps; a gap over 2 s starts again), and the stored value. MIDI
  clock wins when present.
- The estimate is smoothed: tick jitter of +/-1 ms moves it by less than 0.1 BPM, and a tempo
  change from the host is followed within one beat.
- When the tempo changes, a synced delay time glides over 50 ms (a pitch bend, as a tape echo
  does) or cross-fades (no bend). Proposed: glide. The owner chooses.
- Tests with synthetic tick streams: steady, jittered, a tempo ramp, start and stop, a dropout.

**8b.6 Memory budget, a gate before writing the echo.**

| Buffer, at 96 kHz | Size | Kind |
|---|---|---|
| Echo: 0.75 s maximum, stereo, 16-bit samples | 288 KB | estimate |
| Reverb: 8 lines | about 100 KB | estimate |
| Room FIR of batch 9: 4096 taps, stereo, 256-sample partitions | about 140 KB | estimate |
| Chorus, flanger, phaser, speaker alignment delay | under 20 KB | estimate |
| **Total** | **about 550 KB, against 512 KB of AXI SRAM** | estimate |

Options to decide from the measured section sizes: 16-bit storage for the echo (assumed above;
its noise is about -96 dBFS before feedback, to be measured), a shorter maximum echo, giving the
M7 SRAM1 (128 KB; the M4 needs little in batch 11), or running the echo at 48 kHz. The choice
goes into the decision log.

**8b.7 Cost.** The SPEC budget rows for the effect slot and the reverb are replaced by measured
cycles, one row per effect.

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). All tests pass on the PC and, when the Nucleo is available, on the target; the
cycle and memory tables are in `docs/results/`.

**Design notes:** delay lines and interpolation; modulated filters (why the state-variable
filter); the effects, one section each; the reverb; tempo following.
**Exercise:** the tremolo, `dsp_fx_tremolo_f32`, written by the owner against a given header,
reference model and tests (tempo-synced phase, the rounded square wave).
**Stop for the owner with:** the cycle and memory tables, and a listening check of each effect
on the breakouts.

### 10.3 Batch 8c: the full signal path on the boards

Goal: concept A without the room correction, running on the rev A boards and measured.

**8c.0 Gate.** The SPEC 3.4 budget, with the measured rows from batches 3, 6 and 8b. If the
total at 96 kHz is over 70 % of the M7, stop and propose what runs at 48 kHz (the fallbacks in
SPEC 3.4, in order) before writing code.

**8c.1 Blocks still missing.**
- `dsp_mixer`: a matrix with per-input level, pan (-3 dB at centre) and mute.
- `dsp_meter`: peak with hold and decay, RMS, BS.1770 momentary and short-term loudness with its
  K-weighting, true peak at 4x.
- `dsp_crossfeed`: the opposite channel low-passed and delayed into each ear.

**8c.2 Assembly**, in `fw/cm7/src/audio_path.c`, in this order per block:
1. input conversion;
2. the two input strips; record source A;
3. the mixer: strips, USB playback, reverb return (S/PDIF in from batch 10); BLEND;
4. the reverb send;
5. the effect slot; record source B (the tap);
6. the tone control;
7. the speaker stage: PEQ, alignment delay, limiter, mute, dim, monitor volume;
8. the headphone stage: PEQ, crossfeed, limiter, phones volume;
9. output conversion; meters.

The deferred DSP level stays empty until batch 9.

**8c.3 Outputs (proposed; the owner confirms at the start).**
- Mute and dim act on the monitor outputs only. Dim is -20 dB.
- Monitor and phones volume are digital on rev A (SPEC 6.7): an audio taper from off to 0 dB,
  with the last 3 % of travel as off.
- The MUTE button ramps the signal over 10 ms. The relays open only for power and rate changes,
  not for the button, to spare their contacts.

**8c.4 Blend.** An equal-power crossfade between the inputs and USB playback; -3 dB each at
centre.

**8c.5 Record source.** The switch between the strips' outputs and the tap. An end-to-end test
that the tap carries the effect and never the tone control or the output stages.

**8c.6 Measurements.**
- Analogue in to monitor out latency at 96 kHz, block 16, target under 1.5 ms; the same to the
  headphones.
- Worst-case M7 load with every block active and the dearest effect.
- An 8-hour soak: USB duplex at 48 kHz, the effect changed every 10 s by a script, zero
  overruns, zero underruns.
- The LED thresholds against the PC meters.

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). The measurements are in PROGRESS and the README; the SPEC budget holds measured
values only.

**Design notes:** the signal path and why it is in this order; metering; the output law (mute,
dim, volume).
**Exercise:** the BS.1770 K-weighting filter: two biquads from the standard's 48 kHz
coefficients, then re-derived for 96 kHz, with a test against the published values.
**Stop for the owner with:** the latency and CPU table.

### 10.4 Batch 8d: control panel firmware

Goal: the knobs, buttons, LEDs and footswitch drive the registry. Before the panel board exists
it runs with a few pots and buttons on a breadboard wired to the Nucleo; on the real panel after
batch 7.

**8d.1 Potentiometers.**
- ADC scan with DMA, triggered by a timer at 1 kHz per channel (the ADC and pins from the pin
  plan); 16 samples averaged per reading.
- Then a one-pole smoother and a hysteresis of 0.4 % of travel, so a still knob sends nothing.
  At least 10 bits of usable resolution.
- Curves:
  - tone: linear in dB, with a centre zone of +/-3 % of travel that is exactly 0 dB. The detent
    may not sit at the electrical centre: measure three pots first and decide whether each unit
    needs a stored calibration;
  - monitor and phones: the audio taper of 8c.3;
  - FX amount and blend: linear.
- Each pot is owned as 8a.2 sets out.

**8d.2 Buttons and footswitch.**
- Debounced by integrating samples taken at 1 kHz over 5 ms; events: press, release, long press
  (600 ms).
- Mapping (proposed):
  - FX SELECT: short press next effect, long press previous;
  - FX ON: toggle;
  - TAP: taps feed the tempo; a long press returns to MIDI clock or the stored tempo;
  - MUTE and DIM: toggle.
- Footswitch: momentary or latching pedal, chosen in settings; it mirrors FX ON.

**8d.3 LEDs.**
- Signal per input at -40 dBFS with 100 ms hold; clip at -0.5 dBFS with 300 ms hold, from the
  meters, so they show what the converter sees.
- Mute, dim and FX on show state.
- PWM brightness if the pins allow, else on and off. Updated at 100 Hz from the main loop.

**8d.4 Tests.**
- The pot pipeline and the debouncer are hardware-free C in `ctl/`, tested on the PC with
  synthetic ADC streams: noise, slow turn, fast turn, contact bounce.
- On the board: the reading noise of each pot; the delay from turning a knob to the audio change
  (target under 20 ms); a 30-minute idle test with zero reported changes.

**Acceptance.** The batch's transcripts are read and every design note has its "From the transcripts" section (1.1). Every control works on the panel board; the numbers are in PROGRESS.

**Design notes:** the panel input pipeline (sampling, filtering, hysteresis, curves, debounce).
**Exercise:** a double-press detector for the buttons, with tests, as the owner designs it.
**Stop for the owner with:** pot noise, knob-to-audio delay, and the feel of the curves.

## 11. Batches 9 to 13: outlines

Each gets a detailed spec, written like sections 3 to 10, when its inputs exist.

**Batch 9: room correction.** Start with a costing spike: time real FFTs of 64 to 2048 points on
the target. Then the design from the assessment (correction 4): uniform partitions of 256 to
512 samples, computed at the deferred level with a deadline check and an overrun counter, one
partition of latency on the monitor outputs only. Measurement with the lab microphone on the
PC, filter design in Python (state the target curve, the smoothing and the limits on boost),
upload over the control link, room measured again. The FIR sits after the tone control in the
speaker stage. Stretch: non-uniform partitions to bring the latency down to one block.

**Batch 10 (stretch): S/PDIF and ASRC.** The receiver peripheral and S/PDIF out from an SAI.
A software sample-rate converter between the incoming clock and the device clock: a polyphase
interpolator driven by a rate estimate from the buffer fill. Conversion quality measured in the
digital domain. S/PDIF in joins the monitor mixer.

**Batch 11 (stretch): dual-core split, display and encoders.** Control, the protocol, MIDI
mapping, presets and the panel input move to the M4 under FreeRTOS; the M7 keeps audio and USB
audio. `ctl/` is unchanged; only its home moves. A mailbox in SRAM4 with a hardware semaphore
carries parameter changes and meters. The OLED and two encoders: a menu for effect parameters,
presets and settings (knob ownership, MIDI channel, footswitch type), and the screen shown in
`device_look.svg`.

**Batch 12 (stretch): rev B main board.** The H755 and a ULPI PHY on a main board of the same
outline, for USB high speed and 96 kHz duplex with 4 channels each way; the supply scheme decided
for the clock target. The control panel board and the case carry over. Characterised again in
the lab.

**Batch 13: portfolio write-up.** A datasheet-style page of measured figures; the latency and
CPU tables; the fixed-point against float study; the control and MIDI story (knob ownership,
Ableton mapping); a short demo recording made with synthetic or the owner's own audio; and a
list of claims the owner can make, each with its measurement and command.

## 12. What the owner needs to buy or book, and when

| For batch | Item |
|---|---|
| 2 | PCM1808 ADC module, PCM5102A DAC module, jumper wires, jack breakouts, a loopback cable (ordered 2026-11-16) |
| 4 | Ableton Live on his PC (he confirms the version) |
| 5 | Nothing until stage 5; then both boards and the hand-fitted parts (pots, jacks, buttons, USB-C socket, ribbon) |
| 7 | A 12 V supply; a session with the university audio analyser |
| 8d | Only if the panel board is late: three 10 k linear pots, two tactile buttons, two LEDs for a breadboard |
| 9 | A session with the university measurement microphone |

## 13. Changes to this file

- 2026-11-15: written.
- 2026-11-17: revised with the owner's feature review.
  - Batch 3 gains the tone control (bass, mid, treble, +/-12 dB, flat at centre).
  - Batch 4 gains USB MIDI, the record-source switch and the Ableton tests.
  - Batch 5 designs a main board (160 by 100 mm, Nucleo underneath, every rear connector on its
    rear edge, USB-C) and a control panel board, in place of the 100 by 100 mm shield; the
    enclosure is left for later, with a mechanical interface table so the boards do not make it
    harder.
  - Batch 7 adds the USB-C and panel board bring-up.
  - Batch 8 is split into 8a (control core), 8b (effect slot, reverb, tempo), 8c (the full
    signal path) and 8d (control panel firmware), each specified in full.
  - Batch 11 gains the display and encoders; batch 12 reuses the panel board and the case.
  - The old section 11 ("Additions of 2026-11-17") is folded into the batches.
