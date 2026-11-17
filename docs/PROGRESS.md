# Progress

The handoff log, newest entry first. Each entry: what was done, the transcripts read (or
"none listed"), measured numbers, exact commands, what the owner decides or does next. A batch
entry with no transcripts line is unfinished.

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
| Float32 TDF-II, low-frequency sections, signal-to-noise | 59 to 97 dB (20 Hz high-pass at 48 kHz: 68 dB at -1 dBFS) | `python tools/studies/b3_filter_noise.py` |
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
