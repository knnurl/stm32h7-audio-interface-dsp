# DSP audio interface

A USB audio interface with its DSP on board, built on an STM32H755. It is an embedded DSP
practice project: every block is written in portable C11, checked against a Python reference on
the PC, then run and timed on the target.

```
LINE IN 1-2 -> ADC -> [ Input strip x2: trim, HPF, 4-band PEQ, gate, compressor, saturation ]
                              |-> USB record 1-2
                              '-> MONITOR MIXER <- USB play 1-2, S/PDIF in, reverb return
                                        |-> [ Speaker stage: room FIR, PEQ, delay, limiter ] -> OUT 1-2
                                        '-> [ Headphone stage: PEQ, crossfeed, limiter ]    -> OUT 3-4
```

Hardware: a Nucleo-H755ZI-Q with an audio shield (rev A), then one integrated board (rev B).
The Cortex-M7 runs the audio DSP at 400 MHz; the Cortex-M4 is parked until it takes over control
and the front panel.

## Status

| Batch | Content | Status |
|---|---|---|
| 0 | Project documents | Done |
| 1 | Host library, test harness, firmware skeleton | Built; target run waits for the board |
| 2 | Audio pass-through on breakouts | Waiting for the modules |
| 3 | Filters, float and Q31, tone control | Not started |
| 4 | USB audio, USB MIDI, Ableton | Not started |
| 5 | Rev A boards: main board and control panel | Outline drafted |
| 6 to 13 | See `docs/PLAN.md` (batch 8 is in four parts, 8a to 8d) | Not started |

No measured figures yet. They appear here, with the command that reproduces each, as the batches
produce them.

## Build and test

Needs CMake 3.25 or later, Visual Studio 2022 build tools (host), Python 3.10 or later, and for
the firmware Ninja and arm-none-eabi-gcc 13.3 (the one inside STM32CubeIDE 1.19 is found by
itself).

Host library and tests, from the repository root:

```
cmake --preset host
cmake --build --preset host-release
python -m pip install -r tests/requirements.txt
python -m pytest
```

Firmware, both cores:

```
powershell -ExecutionPolicy Bypass -File fw/fetch_deps.ps1
cmake --preset fw
cmake --build --preset fw
```

Flash and test on the board (Nucleo-H755ZI-Q on its ST-LINK USB port):

```
powershell -ExecutionPolicy Bypass -File tools/flash.ps1
python tools/target_test.py --port COMx
```

## Documents

- `docs/SPEC.md`: requirements and design, with the decision log.
- `docs/PLAN.md`: the batches and their status.
- `docs/PLAN_BATCHES.md`: the detailed specification of each batch.
- `docs/PROGRESS.md`: the handoff log, newest first.
- `docs/notes/`: one design note per block or subsystem.
- `docs/exercises/`: one exercise per batch.
- `docs/results/`: measured tables and plots.

## Licence

MIT. See `LICENSE`. Third-party sources are fetched at pinned commits and are not part of this
repository; their licences are listed in `fw/fetch_deps.ps1`.
