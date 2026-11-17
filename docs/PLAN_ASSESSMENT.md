# Assessment of the interview plan

Written 2026-11-15. It reviews `docs/PLAN_INTERVIEW.md` (the plan that came out of the scoping
interview, copied here unchanged). Where this file and the interview plan disagree, this file
wins. The work itself is specified in `docs/PLAN_BATCHES.md`.

## 1. Verdict

The plan is sound in direction and worth building: the device concept, the processor, the
shield-first hardware path, the host-plus-target test method and the milestone order all hold up.
It is not correct as written. Ten points need changing, three of them because a claim the plan
marked `[Verify]` turned out wrong when checked. None of them changes what the device is. One
changes an interview answer (section 4).

## 2. What holds up

- **Concept A on an STM32H755.** It gives every algorithm area a real job in one signal path, and
  the monitor path gives a latency story that can be measured with a scope.
- **Shield first, integrated board second.** The analogue design and the firmware get proven
  before the risky part (H755 power, ULPI, 144-pin layout) is attempted.
- **C11 library built for PC and target, Python as the reference.** This is how embedded audio
  teams work, and it makes every claim reproducible.
- **Fixed point bit-exact, float within a tolerance.** The right test rule.
- **Firmware on breakouts while the shield is in fabrication.** No idle time.
- **I2S_CKIN as the SAI kernel clock, fed from audio oscillators.** The H7 offers this clock
  source, so the converters and the SAI share one low-jitter master [Verify the pin on the Nucleo
  headers].

## 3. Corrections

Basis column: **source** = checked against a document today; **known** = from knowledge of the
part, not re-checked today; **estimate** = arithmetic that a measurement must confirm.

| # | The plan says | Finding | Basis | Change |
|---|---|---|---|---|
| 1 | Rev A: USB full speed carries 2 record and 2 playback channels at 96 kHz | Not viable. Two 96 kHz stereo 24-bit streams need about 1164 B of payload per 1 ms frame; with packet overhead and worst-case bit stuffing that is about 1400 B of a 1500 B frame, over the 90 % periodic limit. Apple's design note says outright that a 96 kHz 2-in 2-out full-speed device is not possible. One direction alone fits. | source ([Apple TN3190](https://developer.apple.com/tutorials/data/documentation/technotes/tn3190-usb-audio-device-design-considerations.md)); the arithmetic is an estimate | Rev A USB: 44.1 and 48 kHz full duplex; 88.2 and 96 kHz in one direction only, for tests. 96 kHz full duplex arrives with rev B (USB high speed). The analogue path and all benchmarks still run at 96 kHz. |
| 2 | M7 at 480 MHz (implied by the cycle budgets) | The Nucleo-H755ZI-Q is wired for direct SMPS supply, which caps the M7 at 400 MHz. 480 MHz needs the board reworked to LDO supply. | source ([ST FAQ](https://community.st.com/t5/stm32-mcus/faq-why-the-direct-smps-supply-option-is-not-shown-in/ta-p/853623)) | Budget for 400 MHz: 4166 cycles per sample at 96 kHz, about 66 600 per 16-sample block. No board rework. Rev B decides its supply scheme with this in mind. |
| 3 | Firmware sets the supply as usual | On this board a firmware image that selects LDO supply stops the MCU from starting, and it stays stuck until recovered. | known [Verify the recovery steps in the board manual] | A ground rule in the batches: direct SMPS only, and the recovery procedure is written down before the first flash. |
| 4 | Partitioned convolution "at a latency of one block" (M8) | Cost per sample grows as filter length over partition size. With 16-sample partitions a 4096-tap filter needs about 256 complex multiply-adds per sample per channel, which is over the whole budget for stereo. Larger partitions are cheap on average, but each one is a burst of work several blocks long. | estimate | M8 baseline: uniform partitions of 256 to 512 samples, computed outside the audio interrupt, adding one partition of latency on the monitor outputs only. Non-uniform partitioning (short head, long tail) is the stretch goal that cuts the latency. Sizes are chosen from measured FFT timings. |
| 5 | "Bare metal, DSP running in the DMA interrupt" | Follows from 4, and from USB: some work is too bursty for the audio interrupt. | known | Three execution levels from the first firmware batch: the audio interrupt (per block, hard deadline), a deferred DSP level below it (long transforms), and the main loop (USB task, control, console). |
| 6 | "State in DTCM"; "DMA buffers in D2 SRAM" | DTCM is 128 KB. Reverb delay lines at 96 kHz and the convolution buffers are several hundred KB, so they belong in AXI SRAM. ST's dual-core template gives most of D2 SRAM to the M4, so the M7's DMA buffers must not be placed there blindly. | known [Verify against the linker scripts in STM32Cube_FW_H7_V1.12.1] | Memory plan in the first firmware batch: hot state and filter state in DTCM; large buffers in AXI SRAM; DMA buffers in SRAM3, non-cacheable; the M7 to M4 mailbox in SRAM4; SRAM1 and SRAM2 left for the M4. |
| 7 | Toolchain from STM32CubeCLT; CubeMX output in `vendor/` | Neither is needed. This PC has STM32CubeIDE 1.19 (GCC 13.3, STM32_Programmer_CLI) and the H7 firmware package V1.12.1. `Psyight/firmware/node-f767` already has a working pattern: a CMake toolchain file, `fetch_deps.ps1` pinning ST's repositories, strict warnings on own code only, a fault handler, flashing by command line. | source (checked on this machine) | Copy that pattern. Take start-up code and linker scripts from the H7 package's dual-core templates. MATLAB R2026a is installed and may be used for an occasional cross-check; Python stays the reference. |
| 8 | Async feedback endpoint, details left open | Developers report that Windows only accepts a 4-byte feedback value from a full-speed UAC2 device, where the USB specification calls for 3 bytes. | source, unofficial ([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/103549/usb-audio-2-0-feedback-endpoint-requirements)); the driver's documented limits are in [Microsoft's driver page](https://learn.microsoft.com/windows-hardware/drivers/audio/usb-2-0-audio-drivers) | The USB batch tests enumeration and feedback on Windows before anything else is built on it. |
| 9 | Shield design and layout as one milestone written by Claude | A script-generated layout is the weakest link for low-noise analogue. The SPEC outline also misses: the ground loop through the 12 V supply, the USB shield and the audio grounds; mute sequencing at power-up, power-down and rate changes; powering the Nucleo from the shield; the 0 dBFS to dBu alignment. | known | The shield batch has five stages with an owner stop after each. Claude selects parts, draws the schematic and writes the placement and routing rules; who routes is an owner decision at that stage. |
| 10 | Thirteen milestones, nothing showable until late | With no deadline, the risk is a project that never reaches a state worth showing. | judgement | A portfolio checkpoint after the USB batch: the Nucleo and two breakouts working as a USB sound card with a parametric EQ, measured tables in the README. Core path: batches 0 to 9. Stretch, each droppable: S/PDIF with ASRC, the dual-core split, rev B. |

Smaller points, folded into the batches:

- **Float policy.** Whether to allow fused multiply-add contraction, and whether to flush
  denormals to zero, changes both speed and host-to-target agreement. The filter batch measures
  both and fixes the policy; the host test harness is set to match.
- **Subslot size.** 4-byte subslots carrying 24 bits avoid packing code and still fit full speed
  at 48 kHz duplex. Windows documents subslots of 1 to 4 bytes.
- **Dual-core parking.** The M4 must be parked from the first firmware batch, not at M10. A
  minimal M4 image that stops itself does this without touching option bytes.
- **Bit-exact USB tests** need WASAPI exclusive mode. Shared mode passes through the Windows
  mixer, which may resample and limit.

## 4. What changes for the owner

1. **Rev A is a 48 kHz duplex USB interface, not 96 kHz.** At 96 kHz it can play or record, not
   both. If 96 kHz duplex on rev A matters more than a simple first board, the alternative is a
   ULPI PHY breakout wired to the Nucleo: possible, but 60 MHz signals over jumper wires are a
   known source of trouble. The batches assume the simple route.
2. **Rev A runs at 400 MHz.** The budgets are tighter by a sixth. If the full concept does not
   fit at 96 kHz, the first fallback is to run the room-correction stage at 48 kHz.
3. **Room correction adds a few milliseconds on the monitor outputs** (2.7 ms for a 256-sample
   partition at 96 kHz, about a metre of air). Headphones are not affected.
4. **You decide who routes the shield**, and you place every order.
5. **Local git from batch 0.** The interview plan said no git until you say so. The batches
   commit locally, one concern per commit, and never create a remote or push without your word.

## 5. Risks that remain

- **Practice value.** Claude writes the code, so the learning rests on the design notes and the
  exercises. The batches put each exercise inside a DSP kernel and ask the owner to run the
  measurements himself. If interviews show gaps, add explain-back questions later.
- **The full signal path may not fit** in 70 % of the M7 at 96 kHz and 400 MHz. Nobody knows
  until the filter and dynamics batches produce cycle counts. The SPEC's budget table starts as
  estimates and is replaced by measurements batch by batch.
- **Converter availability and price** are unchecked. The trade study in the shield batch does it
  against live stock.
- **Lab access.** Two batches depend on booked time with the university analyser and microphone.

## 6. Still unverified

Every item below is carried into the SPEC's "Assumptions to verify" by batch 0.

- Which USB instance the Nucleo's user connector uses, and its pins.
- That the I2S_CKIN pin, the SAI pins and an SPDIFRX input are free on the Nucleo headers once
  Ethernet, the ST-LINK serial port and the LEDs are accounted for.
- The Nucleo's HSE source and frequency.
- TinyUSB's UAC2 feedback behaviour on Windows at full speed.
- Whether rev B can reach 480 MHz with an SMPS feeding the LDO.
- All prices, all converter performance figures, JLC fees.
