# CLAUDE.md

Instructions for Claude Code in this repository. Read this file fully before writing anything.

## What this project is

A USB audio interface with DSP on board, on an STM32H755 (Nucleo-H755ZI-Q plus an audio shield,
later one integrated board). It is a portfolio piece for an embedded DSP role on hardware audio
products, and the owner's home studio interface.

The owner is Kaan Ural: a robotics and embedded engineer working in C/C++, Python, STM32, KiCad
and control systems. Treat him as an expert. Be direct, skip the basics, and flag uncertainty.

## Read these first

1. `docs/PROGRESS.md`, newest entry: where the work stands and what the owner must do next.
2. `docs/SPEC.md`: requirements and design. The source of truth.
3. `docs/PLAN_BATCHES.md`: what each batch delivers. `docs/PLAN.md` has the status.
4. `docs/PLAN_ASSESSMENT.md`: why the plan is what it is. It wins over `PLAN_INTERVIEW.md`.
5. `docs/notes/transcripts_index.md`: which Phil's Lab transcripts to read before each batch. The
   owner treats them as reliable notes. They are automatic captions of videos made on other
   hardware, so check numbers and formulas, and this project's decisions and measurements win
   where they differ.

## Priorities (highest first)

1. Measured correctness
2. Real-time robustness (no dropouts)
3. Monitoring latency
4. Audio quality
5. Cost
6. Feature count

When trade-offs conflict, follow this order and say which priority drove the decision.

## How the work is split

Claude writes the code and the documents. The owner reviews, runs the bench measurements and
does one exercise per batch. One batch is one session: it ends with the build clean, the tests
passing, numbers and commands in `docs/PROGRESS.md`, the review pack written, and a stop for the
owner. Do not start the next batch unless the owner said so.

The review pack every batch ends with:

- **Transcripts first.** Before writing a batch's code, read in full the transcripts
  `docs/notes/transcripts_index.md` lists for it. Every design note has a "From the transcripts"
  section: agrees, differs and why, not done. Ours win where they disagree. A batch is not done
  without it.
- **A design note per DSP block or subsystem** in `docs/notes/<name>.md`: purpose; the maths; the
  structure chosen and the alternatives rejected, with the reason; numerical behaviour (noise,
  overflow, limits of validity); measured cycles per sample on the target; test evidence; open
  questions.
- **One exercise for the owner** in `docs/exercises/EX<batch>_<name>.md`: the task, a header or
  stub, tests that fail until it is done, and the acceptance numbers. Never write the solution.
- **A PROGRESS entry:** what was done, the transcripts read, measured numbers, exact commands,
  what the owner decides or does next.

## Never without the owner's explicit go

- Place an order or do anything that costs money.
- Create a remote or a GitHub repository, or push.
- Write option bytes, or rework the Nucleo.
- Add a dependency that `docs/PLAN_BATCHES.md` does not name.
- Change a decision recorded in the SPEC decision log.
- Flash the board, unless he has said it is connected. `tools/flash.ps1` reads the device
  identity first and stops if it is not a dual-core H7.

## Hardware safety

- **Supply:** the Nucleo-H755ZI-Q is wired for direct SMPS. Firmware always builds with
  `USE_PWR_DIRECT_SMPS_SUPPLY`, voltage scale 1, M7 at 400 MHz at most. An image that selects LDO
  supply leaves the board unable to start. `fw/CMakeLists.txt` refuses any other setting. The
  recovery procedure is in `docs/PROGRESS.md` (batch 1 entry).
- **Audio out of real outputs:** assume speakers or headphones may be connected. Outputs start
  muted. A test signal that reaches an analogue output is at most -20 dBFS, ramps in, and the
  owner is told before it plays. Automated tests use a loopback cable or a digital loopback.
- **Hardware faults:** reproduce before fixing. Say what was measured and what is guessed.

## Code rules

- `dsp/` is hardware-free C11: no HAL, no allocation, no stdio, no global mutable state. It
  builds unchanged for the PC and the target.
- Block API: `dsp_<block>_<fmt>_init`, `_reset`, `_process(state, in, out, n_frames)`, with
  `<fmt>` one of `f32`, `q31`, `q15`. Each header states its assumptions, its latency in samples
  and its measured cycles per sample.
- `math.h` calls are allowed in init and coefficient code. In a `process` function they need a
  measurement that justifies them.
- Types `PascalCase`, functions and variables `snake_case`, constants `kPascalCase`, files
  `snake_case`. Units in names: `_hz`, `_ms`, `_samples`, `_db`, `_cycles`.
- Own code compiles with warnings as errors; vendor code compiles as shipped.
- On the audio path: no allocation, no locks, no printing, no unbounded loops.
- Formatting: `.clang-format` (LLVM base, 4-space indent, 100 columns).

## Test rules

- Every block has a Python reference model in `tests/ref/` and a pytest that calls the C library
  through ctypes.
- Fixed-point blocks match a Python integer model bit-exactly. The model states its rounding and
  saturation rules in words.
- Float blocks match within a stated tolerance, in dB relative to full scale.
- Every block is registered in `dsp/src/dsp_selftest.c`, so the same case runs on the PC and on
  the target. Fixed point: the CRC32 of the target's output equals the host's. Float: the
  target's output is dumped over the console and compared within the tolerance.
- Runs are deterministic: the same input and parameters give the same output, enforced by a test.
- Every latency, CPU, noise or accuracy figure in a document has the command or bench procedure
  that reproduces it. Unchecked claims carry `[Verify]` and are listed in SPEC section 9.

## Licensing and data

- The repository is MIT. Allowed in it: MIT, BSD, Apache-2.0, zlib, ISC, public domain.
- Third-party sources are fetched at pinned commits into `fw/third_party/` (gitignored). The one
  exception is `stm32h7xx_hal_conf.h`, ST's BSD-3 configuration template, edited and committed.
- No copyrighted audio in the repository. Test signals are synthetic.

## Writing conventions

- British English: colour, behaviour, analyse.
- Never use em dashes. Use colons, commas or full stops.
- Sentence case for labels and headings.
- `[Verify]` on unverified technical claims.

## Git

Branch `main`, remote `origin` on GitHub (pushing still needs the owner's go each time). Small
commits, one concern per commit. Docs change in the same
commit as the code they describe: the SPEC section, a decision-log row for every decision,
`docs/PROGRESS.md`, and the commands below.

## Commands

From the repository root. Keep this section accurate.

- Host configure: `cmake --preset host`
- Host build: `cmake --build --preset host-release`
- Host tests: `python -m pytest`
- Exercise tests (fail until the owner has done the exercise): `python -m pytest tests/exercises`
- Fetch firmware dependencies: `powershell -ExecutionPolicy Bypass -File fw/fetch_deps.ps1`
- Firmware configure and build: `cmake --preset fw` then `cmake --build --preset fw`
- Flash both cores: `powershell -ExecutionPolicy Bypass -File tools/flash.ps1`
- Serial console: `python tools/console.py --port COMx`
- Target tests: `python tools/target_test.py --port COMx`
- Control client: `python tools/ctl.py --port COMx <command>`, or `--sim` for the C library on
  the PC (`python tools/ctl.py --sim list`)
- Protocol fuzz under the address sanitiser: `build\host\ctl\Release\ctl_fuzz.exe 200000 7`
  (also run by `python -m pytest`)

## Repository layout

```
dsp/      include/dsp/  src/           hardware-free C11 library
ctl/      include/ctl/  src/  fuzz/    control library: parameters, protocol, MIDI, presets
tests/    unit/  exercises/  ref/      pytest suites and Python reference models
fw/       cmake/  common/  cm7/  cm4/  firmware for both cores; third_party/ is fetched
tools/    flash.ps1  console.py  target_test.py  ctl.py
hw/       shield-a/                    KiCad project (batch 5)
docs/     SPEC, plans, PROGRESS, notes/, exercises/, results/
```
