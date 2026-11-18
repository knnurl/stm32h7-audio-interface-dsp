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
| Monitor mixer | 60 | estimate | 8c |
| Reverb, 8-line FDN | 350 | estimate (self-test case reverb_f32; docs/results/b8b_cycles.md) | 8b |
| Speaker stage: PEQ and delay, stereo | 210 | estimate | 3 |
| Speaker stage: true-peak limiter, stereo | 300 | estimate | 6 |
| Speaker stage: room FIR, stereo, 4096 taps, 256-sample partitions | 900 | estimate | 9 |
| Headphone stage: PEQ, crossfeed, limiter | 390 | estimate | 8c |
| Tone: three bands, stereo | 60 | estimate | 3 |
| Effect slot: the dearest single effect, stereo | 250 | estimate (self-test cases fx_overdrive_f32, and fx_echo96_f32 for the 96 kHz echo; docs/results/b8b_cycles.md) | 8b |
| Metering | 100 | estimate | 8c |
| **Total** (two strips) | **3940** | estimate | |

**Measured 2026-11-17 on the board** (`docs/results/budget_target.md`): about 14 300 cycles per
frame with two strips and the dearest effect, 4.9 times the 96 kHz ceiling and 2.4 times the
48 kHz one. The table above is the plan's estimate; the measured table replaces it at the batch 8c
gate. The estimated total is over the ceiling, by more since the effect slot and tone were added.
Nothing is cut on the strength of estimates. If the measurements agree, the fallbacks in order
are: saturation at 2x oversampling; the room FIR at 48 kHz; the reverb at 48 kHz. Batch 8c has a
gate on this table.

## 4. Hardware rev A: main board and control panel

Two boards (revised 2026-11-17; the earlier 100 by 100 mm "shield" is replaced):

- **Main board**, 4 layers, about 160 by 100 mm, with the Nucleo-H755ZI-Q plugged in underneath.
  It carries everything analogue and every rear connector, on its rear edge, including USB-C.
- **Control panel board** behind the front panel, on a ribbon: the knobs, buttons, LEDs and the
  headphone jack.

The drafts are `docs/notes/shield_outline.md` (sections 9 to 11) and
`docs/notes/device_look.svg`. Batch 5 fills this section in, in five stages: part selection,
architecture, schematic, layout, order package. The enclosure is designed later, from the
mechanical interface table batch 5 produces.

Blocks: 12 V input with protection; analogue rails and digital rails; two audio oscillators
(22.5792 and 24.576 MHz) selected by GPIO; converters on one TDM bus; two balanced line input
stages; a balanced monitor output pair with mute; a headphone amplifier; optical S/PDIF in and
out; a front-panel header; the Nucleo's supply.

Open choices, settled in batch 5: the converter; the dBu value of 0 dBFS; how the analogue rails
are made; whether the main board meets the Nucleo on the Zio sockets or the morpho rows; whether
the headphone amplifier sits on the main board or the panel board; seven ADC pins or a
multiplexer for the potentiometers. Decided: the owner routes the analogue and clock nets.

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

### 6.7 Parameters and control (batches 8a and 8d)

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

Presets: the full parameter set saved to and recalled from flash (batch 8a). A recalled preset
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
| `dsp_mixer`, `dsp_meter`, `dsp_crossfeed` | f32 | Matrix mixer; BS.1770 meters; crossfeed | 0 | 8c |
| `dsp_reverb` | f32 | 8-line FDN on the mixer's send and return, 50 ms pre-delay, decay anchored at DC and 8 kHz | pre-delay only | 8b |
| `dsp_delayline`, `dsp_lfo`, `dsp_svf` | f32 | Delay line of any length with linear, Lagrange and all-pass reads, and a 16-bit line for the echo; 32-bit phase LFO with tempo sync; TPT state-variable filter | n/a | 8b |
| `dsp_tone` | f32 | Low shelf, mid peak, high shelf from `dsp_biquad`, +/-12 dB, smoothed | 0 | 3 |
| `dsp_fx_*`, `dsp_fxslot` | f32 | Effect slot: echo, chorus, flanger, phaser, tremolo, sweep filter, overdrive, bit crusher; switching with fades and trails | 0; the overdrive 46.5 samples | 8b |
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
| V16 | The OTG_FS peripheral has the endpoints and FIFO space for UAC2, MIDI and CDC at once | Batch 4, first step |
| V17 | Flash bank 2's sectors 6 and 7 are 128 KB each (confirmed by the store working), and writing them does not stall the M7 running from bank 1 (not yet: needs audio running, batch 2) | Batch 8a, on the board |
| V18 | A double ECC error on a flash load is masked by FAULTMASK with CCR.BFHFNMIGN and shows in FLASH_SR2 (the preset store's read path relies on it) | Batch 8a, on the board, by cutting the supply during a write |
| V19 | A bank 2 sector erase takes up to about 2 s (measured: 0.96 s with a record write), and the flash endures 10 000 cycles (datasheet, not testable here) | Batch 8a, on the board |
| V10 | The M4, parked in stop mode, leaves the D2 peripherals the M7 has enabled running (settled: the M7's console on USART3, in D2, works with the M4 parked) | Batch 1, on the board |

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
| 2026-11-17 | Batch 8 split into 8a (control core), 8b (effect slot, reverb, tempo), 8c (full signal path) and 8d (control panel firmware) | Too large for one session; 8a and the host parts of 8b need no audio hardware |
| 2026-11-17 | Control code (`ctl/`) is hardware-free C under the same rules as `dsp/`, tested on the PC | Knob ownership, the protocol, MIDI and presets can then be proven before any board exists |
| 2026-11-17 | Presets in an append-only log in the last sector of flash bank 2 | The M7 runs from bank 1, so writing presets should not interrupt audio (SPEC V17) |
| 2026-11-17 | The PEQ and the tone control use double-precision state, float in and out (provisional until the M7 cycle cost is measured) | Measured: float32 TDF-II gives 59 to 111 dB signal-to-noise on low-frequency sections, double about 152 dB (docs/results/b3_filter_noise.md) |
| 2026-11-17 | Q31 biquads: direct form I, per-section shift chosen so the 64-bit accumulator cannot overflow for any input; error feedback optional | Proven bound: sum of |coefficients| <= 2^32 - 1 |
| 2026-11-17 | Tone defaults proposed: 100 Hz low shelf, 1 kHz peak Q 0.7, 10 kHz high shelf, 20 ms smoothing | Awaiting the owner's ears |
| 2026-11-17 | Compressor after Giannoulis et al. (instantaneous detector, gain reduction smoothed in dB); times are time constants | Measured: static curve within 0.1 dB, times within 5 %; bass distortion documented against release |
| 2026-11-17 | Saturation by tanh at 4x through polyphase half-band filters (83 and 23 taps), with 2x and ADAA as options | Measured aliasing at 5 kHz: -131 dB at 4x against -27 dB plain; latency 46.5 samples |
| 2026-11-17 | Limiter: stereo-linked, 4x true-peak detection, sliding minimum then moving average; at least 32 samples of look-ahead; non-finite input replaced by 0 | No output sample above the ceiling by construction; the true-peak gap (up to 0.47 dB) awaits the owner's choice of remedy |
| 2026-11-17 | Limiter true-peak remedy: detect against a threshold 0.5 dB under the set ceiling; interpolation between the four detector samples later, if measured to help | Owner. Measured: true peak 0.198 dB over the threshold at every look-ahead, so about 0.3 dB under the set ceiling |
| 2026-11-17 | Strip compressor default release 50 ms; saturation default 4x oversampled | Owner, from the measured bass distortion (-33 dB THD at 50 ms) and aliasing (-131 dB at 4x) |
| 2026-11-17 | Tone corners 100 Hz, 1 kHz (Q 0.7), 10 kHz adopted as defaults, provisional | Owner: accepted, to be checked by ear on the hardware |
| 2026-11-17 | Repository published at github.com/knnurl/stm32h7-audio-interface-dsp | Owner created it and gave the URL |
| 2026-11-17 | Control library `ctl/` beside `dsp/`: one const parameter table (169 entries, ids by group with gaps, never reused), knob ownership with pick-up (1 % hysteresis), text protocol version 1, fixed MIDI map on the 40 undefined CC numbers, presets by id | Batch 8a; notes `ctl_registry.md`, `knob_pickup.md`, `control_protocol.md`, `midi_map.md`, `preset_store.md` |
| 2026-11-17 | The audio hand-off queue holds each parameter at most once, so it cannot overflow and the newest value always wins | Replaces "newest wins on overflow" with no overflow; tested with 10 000 writes and no consumer |
| 2026-11-17 | Preset store on two sectors of flash bank 2 (6 and 7), not one; the M4's flash shrinks to 768 KB | With one sector, a power cut during the erase before a rewrite loses every preset |
| 2026-11-17 | Mute is neither a preset nor a setting: the outputs always start muted | Hardware safety rule |
| 2026-11-17 | Speaker and headphone corrections, knob modes, MIDI channel and the tone corners are settings (power-on record only), not preset contents | A preset recall must not change the room correction or the volume |
| 2026-11-17 | The board's self-test list command is renamed `cases`; `list` belongs to the control protocol | One console carries both until batch 4 |
| 2026-11-17 | Tempo follower: least-squares fit over up to four beats of MIDI clock, a one-beat fit to detect change (0.6 %), restart and settling; taps set the stored tempo | Measured: 0.04 BPM worst under 1 ms jitter; a step followed within one beat; a 0.75 BPM-per-beat ramp lags by 1.35 BPM (docs/notes/tempo.md) |
| 2026-11-17 | Delay lines in caller memory of any length (not power of two); modulated reads by third-order Lagrange | Measured: Lagrange 20 to 50 dB better than linear on a swept delay; a power-of-two echo line at 96 kHz would be 131 072 samples instead of 72 000 |
| 2026-11-17 | Modulated filters are TPT state-variable filters, coefficients every 16 samples | Measured: a TDF-II biquad diverged when its cutoff jumped every 16 samples; the SVF stayed under the static bound |
| 2026-11-17 | Effect slot: one effect runs at a time; a change is fade out, clear, fade in (30 ms each way); trails on by default for effects with a dry path | Cycle budget counts one effect; measured worst transition 1.13x the steady second difference |
| 2026-11-17 | FX AMOUNT macros as proposed in PLAN_BATCHES 8b.2; echo time changes glide over 50 ms | Proposals built pending the owner's review |
| 2026-11-17 | Reverb: 8-line FDN, Hadamard feedback, prime lengths 19.3 to 47.9 ms, Jot absorbent filters, two modulated lines | Measured: T60 within 3.7 %; Hadamard reaches echo density 0.9 at 405 ms on the model, Householder not within 0.5 s |
| 2026-11-17 | Large self-test buffers live in AXI SRAM (`.axi_bss`) on the target, where the real delay lines go | Cycle counts must reflect the real memory; DTCM went from 107 KB to 76 KB of 128 |
| 2026-11-17 | Echo lines 16-bit (2^13 per 1.0, saturating, no dither); echo core at fs / 2 above 48 kHz between the 83-tap half-bands; resting delay in whole samples | Owner chose 16-bit at 48 kHz; measured: 141 KB for 0.75 s, repeat within 1 sample of the set time, passband 0.001 dB to 18 kHz, image -113 dB |
| 2026-11-17 | Echo quantiser rounds toward zero below 16 LSB (nearest above) | Owner: "as you recommend". Measured: pure nearest hung a feedback-0.95 tail at -59 dBFS forever; this ends every tail, at -74.2 instead of -79.5 dBFS error. `DSP_DELAYLINE_S16_SNAP_LSB` 0 restores pure nearest |
| 2026-11-17 | Reverb pre-delay up to 50 ms, stereo; T_hi anchored at 8 kHz | Owner ("as you recommend"); memory 140 KB at 96 kHz; Schroeder T60 within 3.5 % at 500 Hz, 4 and 8 kHz |
| 2026-11-17 | Reverb matrix: Hadamard kept; the density claim withdrawn; input diffusers not built | Measured with the 8 kHz anchor: Hadamard and Householder close and mixed. Both left to the owner's ears |
| 2026-11-17 | Accepted as built: the FX AMOUNT macro table, glide on echo time changes, the 60 ms dry gap on an effect change, two preset flash sectors, mute never restored, a four-beat tempo window | Owner: "as you recommend" |
| 2026-11-17 | First board run: all 24 self-test cases match the PC (22 bit-identical, 2 within -132 dBFS); 400 MHz confirmed against the HSE; the M4 parks; console, protocol and preset store work | Measured on the Nucleo-H755ZI-Q (`docs/results/bench_target.md`) |
| 2026-11-17 | The bench times processing only (cases mark the end of their set-up) and reports cycles per frame | The first run's whole-run figures were up to 10 times too high where set-up cleared delay memory |
| 2026-11-17 | Rev A runs at 48 kHz: the budget is judged at 48 kHz (8333 cycles per frame, ceiling 5833); 96 kHz stays a rev B target | Owner; rev A's USB duplex is 48 kHz anyway; the measured path is 4.9 times over the 96 kHz ceiling |
| 2026-11-17 | Saturators use `dsp_fast_tanhf`; the half-band kernel folds symmetric taps into four partial sums; the DSP library runs from ITCM | Measured on the M7 (`docs/results/budget_target.md`): 4x saturator 1678 to 1204, limiter 1241 to 993, overdrive 3661 to 2479; ITCM itself no measurable change; still bit-identical with the PC |
| 2026-11-17 | `flash.ps1` writes both images in one programmer session | Two sessions left the core in ST's flash loader and faulted on every flash (reproduced, then fixed) |
| 2026-11-17 | Saturation at 2x by default (strips) and in the overdrive | Owner (budget gate); measured 1204 to 578 and 2479 to 1284 cycles; aliasing at 5 kHz -64 dB instead of -131 |
| 2026-11-17 | Headphone limiter detects sample peaks; the speaker limiter keeps true-peak detection | Owner; measured 214 against 665 cycles; headphone true peak can exceed the ceiling by up to 3 dB |
| 2026-11-17 | The overdrive and the strips' saturation never run together (control core refuses, error 10) | Owner; the worst case pays for one |
| 2026-11-17 | True-peak detector: a 63-tap Nyquist interpolator (three 16-tap phases) instead of the 4x oversampler; limiter latency L + 9 | Measured: 998 to 665 cycles; true peak still 0.24 dB under the set ceiling on the hostile set |
| 2026-11-18 | The M4 runs its DSP code from its SRAM; it can be woken through the SRAM4 mailbox to run the self-test cases (`m4bench`) | Measured: from flash about 4.5 times the M7's cycles, from SRAM 1.5 to 3 times; the reverb 1451 cycles, 35 % of the M4's frame, bit-identical with the PC |
| 2026-11-18 | The 8c split (reverb on the M4, the ceiling, float32 PEQ) waits for the room FIR's measured cost in batch 9 | Owner: the FIR's 900 cycles is still an estimate, and it decides whether 78 % is the real worst case |
