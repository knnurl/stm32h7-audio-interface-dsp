# Specification: DSP audio interface

The source of truth for requirements and design. Where a measurement disagrees with this file,
the measurement wins and this file is corrected in the same commit, with a decision-log row.

Every number is marked **target** (what we aim for), **estimate** (arithmetic, not yet measured)
or **measured** (with the command or procedure in `docs/PROGRESS.md` or `docs/results/`).

## 1. Purpose, audience, non-goals

A USB audio interface with its DSP on board. Two jobs:

- A portfolio piece for an embedded DSP role on hardware audio products: DSP algorithms written
  for an embedded processor, real-time constraints met and measured, integration with firmware
  and hardware.
- The owner's home studio interface: line sources in, monitors and headphones out.

Non-goals: microphone preamps and phantom power; a Hi-Z instrument input; a custom ASIO driver
(Windows' in-box USB Audio 2.0 driver is used); network audio; more than 2 analogue inputs.

## 2. Priorities and signal flow

Priorities, highest first: measured correctness, real-time robustness, monitoring latency, audio
quality, cost, feature count.

```
LINE IN 1-2 -> ADC -> [ Input strip x2: trim, HPF, 4-band PEQ, gate, compressor, saturation ]
                              |-> USB record 1-2
                              '-> MONITOR MIXER <- USB play 1-2, S/PDIF in, reverb return
                                        |             ^ send
                                        |             '-- FDN reverb
                                        v
                                  [ Effect slot: one effect at a time ]
                                        |-> record tap (to USB when selected)
                                        v
                                  [ Tone: bass, mid, treble knobs ]
                                        |-> [ Speaker stage: room FIR, PEQ, delay, limiter ] -> OUT 1-2
                                        '-> [ Headphone stage: PEQ, crossfeed, limiter ]    -> OUT 3-4
```

- **Effect slot:** one creative effect at a time on the monitor mix: echo, chorus, flanger,
  phaser, tremolo, sweep filter, overdrive or bit crusher. The reverb stays on its send.
- **Record source:** the USB record channels carry either the processed inputs or the record
  tap. The tap is after the effect slot and before the tone knobs and the room correction, which
  correct the listening and are never recorded. On rev B both sources go to the PC at once.
- **Tone:** bass and treble shelves and a mid peak, +/-12 dB, flat at centre, on monitors and
  headphones together.

The monitor path never passes through the PC, so its latency is set by the converters and the
block size alone.

## 3. Requirements

### 3.1 By hardware revision

| Item | Rev A (Nucleo + shield) | Rev B (integrated) | Kind |
|---|---|---|---|
| Analogue inputs | 2 balanced line | Same | target |
| Analogue outputs | 4: balanced monitor pair, headphone pair | Same | target |
| Converter rates | 44.1, 48, 88.2, 96 kHz | Same | target |
| USB speed | Full speed, through the Nucleo | High speed, ULPI PHY | target |
| USB duplex | 44.1 and 48 kHz, 2 in and 2 out | Up to 96 kHz, 4 in and 4 out | target |
| USB one direction only | 88.2 and 96 kHz | Not needed | target |
| USB format | 24 bits in 4-byte subslots | Same | target |
| S/PDIF | Optical in and out (stretch, batch 10) | Same | target |
| M7 clock | 400 MHz (direct SMPS limit) | Decided with rev B's supply scheme | measured in batch 1 |
| Power | 12 V DC; USB carries data only | Same | target |
| USB MIDI | Yes: parameters by control change, tempo from MIDI clock | Same | target |
| Control panel | A separate board behind the front panel, on a ribbon inside the case: 7 potentiometers, 5 buttons, LEDs, the headphone jack | Same board | target |
| Enclosure | Yes: an aluminium desktop case the owner makes (CNC or waterjet), about 170 x 55 x 140 mm, with legends on the front and rear panels | Same case and panels | target |
| USB connector | USB-C on the rear panel, data only, wired to the MCU through the headers | USB-C | target |
| Main board outline | 160 x 100 mm, Nucleo plugged in underneath | Same outline, MCU on board | target, proposed |
| Display | Header for an OLED and two encoders (batch 11) | Fitted | target |

### 3.2 Performance

| Item | Value | Kind |
|---|---|---|
| Analogue in to monitor out latency, 96 kHz, no room FIR | under 1.5 ms | target, proposed |
| Added latency of the room FIR on monitor outputs | one partition: 2.7 ms at 256 samples, 96 kHz | estimate |
| Headphone path latency | as the monitor path without the room FIR | target |
| USB round trip (play to record through a loopback cable), 48 kHz | under 10 ms | target, proposed |
| M7 load, worst case, 96 kHz | under 70 % of the block period | target, proposed |
| Dropouts over 8 h of duplex streaming | none | target |
| Block size at 96 kHz | 16 frames (167 us) | target, confirmed or changed in batch 2 |

### 3.3 Analogue (mid-grade, rev A)

| Item | Value | Kind |
|---|---|---|
| Nominal level | +4 dBu | target |
| Input level at 0 dBFS | +20 dBu | target, proposed |
| Monitor output level at 0 dBFS | +18 dBu | target, proposed [Verify against the rails] |
| Dynamic range, A-weighted, in and out | 105 dB or better | target [Verify against the chosen converter] |
| THD+N at -1 dBFS, 1 kHz | -90 dB or better | target |
| Frequency response, 20 Hz to 20 kHz | within 0.2 dB | target |
| Crosstalk at 1 kHz | -90 dB or better | target |

### 3.4 Cycle budget

Cycles per sample at 96 kHz on the M7 at 400 MHz. Available: 4166. Ceiling at 70 %: 2916.
Every row is an estimate until its batch replaces it with a measurement.

| Block | Cycles per sample | Kind | Batch that measures it |
|---|---|---|---|
| Sample conversion, 2 in, 4 out, USB both ways | 60 | estimate | 2 |
| Input strip, each: trim, HPF, 4-band PEQ | 110 | estimate | 3 |
| Input strip, each: gate and compressor | 120 | estimate | 6 |
| Input strip, each: saturation at 4x oversampling | 400 | estimate | 6 |
| Monitor mixer | 60 | estimate | 8 |
| Reverb, 8-line FDN | 350 | estimate | 8 |
| Speaker stage: PEQ and delay, stereo | 210 | estimate | 3 |
| Speaker stage: true-peak limiter, stereo | 300 | estimate | 6 |
| Speaker stage: room FIR, stereo, 4096 taps, 256-sample partitions | 900 | estimate | 9 |
| Headphone stage: PEQ, crossfeed, limiter | 390 | estimate | 8 |
| Tone: three bands, stereo | 60 | estimate | 3 |
| Effect slot: the dearest single effect, stereo | 250 | estimate | 8 |
| Metering | 100 | estimate | 8 |
| **Total** (two strips) | **3940** | estimate | |

The estimated total is over the ceiling, by more since the effect slot and tone were added. Nothing is cut on the strength of estimates. If the
measurements agree, the fallbacks in order are: saturation at 2x oversampling; the room FIR at
48 kHz; the reverb at 48 kHz. Batch 8 has a gate on this table.

## 4. Hardware rev A: the shield

A 4-layer board that plugs onto the Nucleo-H755ZI-Q and carries everything analogue. The draft
outline is `docs/notes/shield_outline.md`. Batch 5 fills this section in, in five stages:
part selection, architecture, schematic, layout, order package.

Blocks: 12 V input with protection; analogue rails and digital rails; two audio oscillators
(22.5792 and 24.576 MHz) selected by GPIO; converters on one TDM bus; two balanced line input
stages; a balanced monitor output pair with mute; a headphone amplifier; optical S/PDIF in and
out; a front-panel header; the Nucleo's supply.

Open choices, settled in batch 5: the converter; the dBu value of 0 dBFS; how the analogue rails
are made; whether the shield mounts on the Zio sockets or the morpho rows; who routes the board.

## 5. Hardware rev B: the delta

The H755 and a ULPI PHY on the same board as the analogue, for USB high speed and 96 kHz duplex
with 4 channels each way. Open: the core supply scheme, which sets the maximum M7 clock (direct
SMPS gives 400 MHz; 480 MHz needs the LDO) [Verify whether SMPS feeding the LDO reaches it]; the
enclosure.

## 6. Firmware architecture

### 6.1 Execution levels on the M7

| Level | Mechanism | Priority | Work |
|---|---|---|---|
| Audio | SAI DMA half and full interrupts | 1 | One block of the signal path. Hard deadline: the block period. |
| USB | OTG interrupt | 4 | Endpoint service into ring buffers. |
| Tick | SysTick | 6 | 1 ms time base. |
| Console | USART3 interrupt | 8 | Bytes in and out of queues. |
| Deferred DSP | PendSV | 14 | Long transforms (the room FIR's FFTs). Requested by the audio level; pre-empted by everything above. |
| Main loop | Thread mode | none | USB task, control, console commands, benchmarks. |

No RTOS on the M7. PendSV is free for the deferred level because nothing else uses it.

### 6.2 Memory plan (M7)

| Region | Address, size | Use |
|---|---|---|
| Flash bank 1 | 0x0800 0000, 1 MB | M7 code and constants |
| ITCM | 0x0000 0000, 64 KB | Hot kernels (`.itcm_text`), copied from flash at start-up |
| DTCM | 0x2000 0000, 128 KB | Stack, `.data`, `.bss`, filter state, the fault record |
| AXI SRAM | 0x2400 0000, 512 KB | Large buffers: reverb delay lines, convolution (`.axi_bss`, not zeroed at start) |
| SRAM3 | 0x3004 0000, 32 KB | DMA buffers (`.dma_buffers`), non-cacheable through an MPU region |
| SRAM4 | 0x3800 0000, 64 KB | The M7 to M4 mailbox (`.mailbox`) |
| Flash bank 2, SRAM1, SRAM2 | 0x0810 0000; 0x1000 0000, 256 KB | The M4 |

Both caches are on. DMA never touches a cacheable region, so no cache maintenance calls are
needed on the audio path. DMA1 and DMA2 cannot reach the TCM memories.

### 6.3 Clocks

- System: 8 MHz from the ST-LINK into HSE (bypass), PLL1 to 400 MHz, direct SMPS supply, voltage
  scale 1. AHB 200 MHz, APB buses 100 MHz.
- Audio on breakouts (batches 2 to 4): PLL3 feeds the SAI; MCLK out at 256 fs.
- Audio on the shield: the selected oscillator feeds the converter and the MCU's I2S_CKIN pin,
  which is the SAI kernel clock [Verify the pin on the Nucleo headers]. One low-jitter master.

### 6.4 USB audio

Asynchronous endpoints both ways: the device's audio clock is the master and the host follows an
explicit feedback endpoint. A ring buffer in each direction sits between the USB level and the
audio level, aimed at half full, with underrun and overrun counters. TinyUSB at a pinned commit.
Windows may want a 4-byte feedback value at full speed [Verify in batch 4, first step].

### 6.5 Sample-rate changes

Mute with a ramp, stop the SAI, reprogram the clock source, flush the rings, reset the DSP
state, restart, unmute with a ramp.

### 6.6 The two cores

The M7 runs audio and USB audio. The M4 is parked in stop mode from batch 1 (a minimal image, no
option bytes changed). In batch 11 it takes control, the protocol and the front panel under
FreeRTOS, talking to the M7 through a mailbox in SRAM4 guarded by a hardware semaphore.

### 6.7 Parameters and control (batch 8)

A registry declares every parameter once: id, label, unit, range, default, smoothing time. The
control protocol over the USB serial port reads and writes by id. Parameter changes reach the
audio level through a lock-free queue and are smoothed there.

Ways in, all onto the same registry:

- **Control panel.** Potentiometers (centre detent on the tone three): bass, mid, treble,
  monitor volume, headphone volume, effect amount, input and playback blend. Buttons: effect
  select, effect on and off, mute, dim (-20 dB), tap tempo. A footswitch jack that mirrors
  effect on and off. LEDs: signal and clip for each input, and one for each of mute, dim and
  effect on. The potentiometers are read by the MCU's ADC, filtered, with hysteresis so a still
  knob sends nothing.
- **PC control link** (USB serial): every parameter and the meters.
- **USB MIDI:** control change in and out for every parameter; MIDI clock sets the tempo of
  timed effects. Mapping is by a fixed table first, MIDI learn later.

Each parameter that has a potentiometer has a setting, held on the PC side of the protocol:
**knob wins** (the PC shows the value, read-only) or **PC wins** (the PC and MIDI set the value;
the knob takes over again only once it is turned through the current value, so nothing jumps).

Presets: the full parameter set saved to and recalled from flash (batch 8). A recalled preset
behaves like "PC wins" for the parameters that have knobs.

Volume is applied in the DSP on rev A. That costs converter resolution at low volume; whether
rev B uses an analogue volume stage is decided there.

## 7. DSP blocks

All in `dsp/`, hardware-free C11, API `dsp_<block>_<fmt>_init / _reset / _process`.

| Block | Formats | Algorithm | Latency | Batch |
|---|---|---|---|---|
| `dsp_gain` | f32 | Gain with one-pole smoothing of the linear gain | 0 | 1 |
| `dsp_testsig` | f32, q31 | Deterministic noise, impulse, step; sine (not bit-exact) | n/a | 1 |
| `dsp_dcblock` | f32 | One-pole DC blocker (owner's exercise) | 0 | 1 |
| `dsp_convert` | f32, q31 | 24-bit integer to float and back, saturation, TPDF dither | 0 | 2 |
| `dsp_biquad` | f32, q31 | f32: transposed direct form II. q31: direct form I, Q2.30 coefficients, error feedback | 0 | 3 |
| `dsp_coef` | double | Peaking, shelves, low-pass, high-pass designs | n/a | 3 |
| `dsp_peq` | f32, q31 | High-pass plus four bands, click-free updates | 0 | 3 |
| `dsp_nco` | q31 | Phase accumulator with interpolated sine table (owner's exercise) | 0 | 4 |
| `dsp_env`, `dsp_comp`, `dsp_gate` | f32 | Detectors; feed-forward log-domain compressor; gate with hysteresis and hold | 0 | 6 |
| `dsp_limiter` | f32 | Look-ahead, true-peak detection at 4x | the look-ahead, reported | 6 |
| `dsp_oversample`, `dsp_saturate` | f32 | Polyphase half-band 2x and 4x; soft waveshaper | filter group delay, reported | 6 |
| `dsp_mixer`, `dsp_reverb`, `dsp_meter`, `dsp_crossfeed` | f32 | Matrix mixer; 8-line FDN; BS.1770 meters; crossfeed | 0 | 8 |
| `dsp_tone` | f32 | Low shelf, mid peak, high shelf from `dsp_biquad`, +/-12 dB, smoothed | 0 | 3 |
| `dsp_fx_*` | f32 | Effect slot: echo, chorus, flanger, phaser, tremolo, sweep filter, overdrive, bit crusher | 0, or reported | 8 |
| `dsp_pconv` | f32 | Uniformly partitioned FFT convolution | one partition | 9 |
| `dsp_asrc` | f32 | Polyphase interpolator with a rate-tracking loop | filter group delay | 10 |

Float policy (fused multiply-add contraction, denormal flushing): contraction is off on both
sides until batch 3 measures both and decides.

## 8. Verification

- **Host:** pytest calls the C library through ctypes and compares with Python reference models
  in `tests/ref/`. Fixed point bit-exact; float within a tolerance stated per test.
- **Shared self-test:** `dsp/src/dsp_selftest.c` holds one fixed case per block. The same code
  runs on the PC and on the target.
- **Target:** the `bench` console command runs every self-test case and prints cycles per sample
  and the CRC32 of the output; `vec <case>` dumps the output. `tools/target_test.py` compares
  both with the host library.
- **Latency:** written procedures in `docs/notes/latency.md` (batch 2): scope for analogue in to
  out, a pulse through a loopback cable for the USB round trip. Expected values are written down
  before measuring.
- **Soak:** hour-long and 8-hour runs with overrun, underrun and buffer-fill counters.
- **Lab:** one session on the university analyser with a written protocol (batch 7): frequency
  response, THD+N against level and frequency, dynamic range, crosstalk, maximum level, noise.

## 9. Assumptions to verify

| # | Assumption | Settled in |
|---|---|---|
| V1 | The Nucleo's user USB connector is the OTG_FS instance on PA11 and PA12 | Batch 4 |
| V2 | I2S_CKIN (PC9), the SAI1 pins (PE2 to PE6) and an SPDIFRX input are free on the Nucleo headers once Ethernet, the ST-LINK serial port and the LEDs are accounted for | Batch 2 |
| V3 | TinyUSB's UAC2 feedback endpoint works with Windows' in-box driver at full speed | Batch 4 |
| V4 | Rev B can reach 480 MHz with an SMPS feeding the LDO | Batch 12 |
| V5 | The recovery procedure for a wrong supply setting (see PROGRESS, batch 1) works on this board | Only if it ever happens |
| V6 | Converter performance, prices, stock and JLC part classes | Batch 5, stage 1 |
| V7 | The Nucleo may be powered from the shield, and through which pin and jumper | Batch 5, stage 2 |
| V8 | The full signal path fits under 70 % at 96 kHz (the estimates say it does not) | Batches 3, 6, 8 |
| V9 | Two 96 kHz stereo streams do not fit full-speed USB (source: Apple TN3190; our arithmetic is an estimate) | Batch 4, if tried |
| V11 | Ableton on Windows runs the device through an ASIO wrapper (ASIO4ALL or FlexASIO) over the in-box driver, at a usable latency | Batch 4 |
| V12 | Seven ADC inputs and the panel's GPIO are free on the Nucleo headers; if not, an analogue multiplexer on the panel board | Batch 5 |
| V13 | The Nucleo's user USB data pins can be driven from a socket on the main board (solder bridges, the Nucleo's USB power switch) | Batch 5, stage 2 |
| V14 | The stack height (Nucleo, headers, main board, tallest rear connector) fits a 55 mm high case | Batch 5, stage 2 |
| V15 | The MCU's built-in USB bootloader can update the firmware through the rear USB port | Batch 4 |
| V10 | The M4, parked in stop mode, leaves the D2 peripherals the M7 has enabled running | Batch 1, on the board |

Settled, with the source:

- HSE is 8 MHz from the ST-LINK, in bypass; the console is USART3 on PD8 and PD9; the LEDs are
  PB0, PE1 and PB14. Source: ST's NUCLEO-H745ZI-Q template and board support package in
  STM32Cube_FW_H7 V1.12.1 (same board, MB1363).
- The default supply is direct SMPS and limits the M7 to 400 MHz. Source: ST's FAQ and the same
  template, which runs at 400 MHz.

## 10. Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-15 | Goal: an interview portfolio piece that is also the home studio interface | Owner |
| 2026-11-15 | Claude writes code and documents; the owner reviews, measures, and does one exercise per batch | Owner |
| 2026-11-15 | Concept A: input strips, DSP monitor mixer with reverb, speaker stage with room FIR, headphone stage | Uses every algorithm area the owner chose |
| 2026-11-15 | 2 balanced line inputs, 4 outputs; no mic preamp, phantom power or Hi-Z input | Owner; keeps the analogue front end simple |
| 2026-11-15 | STM32H755; M7 for audio and USB audio, M4 for control and the front panel | Owner has the Nucleo |
| 2026-11-15 | Rev A is a shield on the Nucleo; rev B integrates the MCU and a ULPI PHY | Cost and risk: analogue and firmware are proven before the hard layout |
| 2026-11-15 | Mid-grade analogue, measured honestly | Owner; cost |
| 2026-11-15 | 4-layer board, JLC Economic assembly for SMT, through-hole fitted by hand | Cost |
| 2026-11-15 | 12 V DC supply; USB for data only | Clean rails and full headroom |
| 2026-11-15 | Analogue verification on a borrowed university analyser and microphone | Owner has a scope and logic analyser only |
| 2026-11-15 | C11 DSP library for PC and target, C firmware, Python reference models | Matches embedded audio practice |
| 2026-11-15 | Public GitHub repository under MIT, created only on the owner's word | Owner |
| 2026-11-15 | Rev A USB is 44.1 and 48 kHz duplex; 96 kHz in one direction only | Two 96 kHz stereo streams do not fit full speed (assessment, correction 1) |
| 2026-11-15 | M7 at 400 MHz; firmware selects direct SMPS only | The Nucleo's supply wiring (assessment, corrections 2 and 3) |
| 2026-11-15 | Room FIR: uniform partitions of 256 to 512 samples at a deferred level | A 16-sample partition costs more than the whole budget (assessment, correction 4) |
| 2026-11-15 | Three execution levels: audio interrupt, deferred DSP, main loop | Bursty work cannot run in the audio interrupt (assessment, correction 5) |
| 2026-11-15 | Memory plan of section 6.2 | DTCM is too small for delay lines; DMA cannot reach the TCMs (assessment, correction 6) |
| 2026-11-15 | Toolchain: the GCC inside STM32CubeIDE 1.19 with CMake, after the Psyight node firmware | Already installed and proven (assessment, correction 7) |
| 2026-11-15 | Portfolio checkpoint after batch 4; batches 10 to 12 are stretch | Something showable early (assessment, correction 10) |
| 2026-11-16 | Local git from batch 0; a private remote after batch 1 and public at the checkpoint, each on the owner's word | Owner agreed to the advice |
| 2026-11-16 | The owner routes the shield's analogue and clock nets; Claude writes the rules and reviews | Owner agreed to the advice |
| 2026-11-17 | The deferred DSP level is PendSV at priority 14 | No RTOS on the M7 uses it; set pending from the audio interrupt with one register write |
| 2026-11-17 | ST sources pinned to the versions inside STM32Cube_FW_H7 V1.12.1: HAL 1.11.5, CMSIS device 1.10.6 | Matches the package on the owner's PC |
| 2026-11-17 | Start-up and system code are ST's dual-core files; both linker scripts are our own | ST's scripts know nothing of the memory plan |
| 2026-11-17 | The same self-test cases are compiled into the host library and the firmware | Host and target cannot drift apart |
| 2026-11-17 | Float contraction off on both sides until batch 3 decides | Keeps host and target comparable from the first block |
| 2026-11-17 | Tone knobs: bass, mid, treble, +/-12 dB, flat at centre, on monitors and headphones, never recorded | Owner |
| 2026-11-17 | Potentiometers, with a per-parameter setting: knob wins, or PC wins with soft takeover | Owner |
| 2026-11-17 | An effect slot on the monitor mix, one effect at a time, plus the reverb send | Owner asked for more effects; one at a time keeps the budget honest |
| 2026-11-17 | Record-source switch; the record tap sits after the effects and before tone and room correction | Owner wants the altered output in Ableton; listening corrections do not belong in a recording |
| 2026-11-17 | USB MIDI in the composite device | Owner; lets Ableton map and automate parameters and send tempo |
| 2026-11-17 | Full control set: 7 potentiometers, 5 buttons, LEDs, footswitch jack, presets in flash | Owner chose every option |
| 2026-11-17 | The controls sit on a separate panel board on a ribbon, not on the shield itself | Seven potentiometers and five buttons do not fit a 100 mm edge beside the jacks; the panel carries over to rev B |
| 2026-11-17 | Rev A gets an enclosure; the control panel sits inside it behind the front panel | Owner: build it as a product |
| 2026-11-17 | Proposed: USB-C on the rear panel; an extruded aluminium case with circuit-board panels; a 160 x 100 mm main board whose outline rev B keeps | Professional finish at low cost; nothing is thrown away at rev B. Awaiting the owner's word |
| 2026-11-17 | Headphone jack on the front panel, footswitch jack on the rear | Front for what is plugged often, rear for what stays plugged |
| 2026-11-17 | USB-C confirmed | Owner |
| 2026-11-17 | The owner makes the aluminium case himself by CNC or waterjet; no bought extrusion | Owner. The case is designed around the boards, so the board outline is no longer tied to a catalogue size |
| 2026-11-17 | Front-panel order confirmed; monitor volume is the large knob | Owner |
| 2026-11-17 | `dsp_gain` snaps to its target once the float32 recursion has stalled; its coefficient uses `expm1` | The stall was measured at 3.6e-6 (-109 dBFS); a settled gain should equal what was set |
| 2026-11-17 | pytest pinned to 8.3.5 | 9.2.0 fails with an internal error on the owner's Python 3.10 |

