# Progress

The handoff log, newest entry first. Each entry: what was done, measured numbers, exact
commands, what the owner decides or does next.

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
