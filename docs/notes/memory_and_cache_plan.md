# Design note: memory, caches and execution levels on the M7

Batch 1. Where code and data live on the STM32H755's Cortex-M7, and why.

## Purpose

The H7 has six memories with different speeds and different rules about who may touch them.
Putting the wrong thing in the wrong one gives slow code or, worse, DMA that silently reads
stale data. The plan is fixed in the linker script (`fw/cm7/stm32h755_cm7.ld`) so that each
block only has to name a section.

## The plan

| Region | Size | Section | What goes there | Why |
|---|---|---|---|---|
| Flash bank 1 | 1 MB | `.text`, `.rodata` | Code, constants | |
| ITCM | 64 KB | `.itcm_text` | Hot kernels, from batch 3 | Zero wait states, no cache misses, constant timing |
| DTCM | 128 KB | `.data`, `.bss`, stack, `.noinit` | Filter state, small buffers, the fault record | Same; and it is not shared with DMA |
| AXI SRAM | 512 KB | `.axi_bss` | Reverb delay lines, convolution buffers | The only RAM large enough; cached |
| SRAM3 | 32 KB | `.dma_buffers` | SAI DMA buffers | Reachable by DMA1 and DMA2; made non-cacheable |
| SRAM4 | 64 KB | `.mailbox` | The M7 to M4 mailbox | In the D3 domain, which stays up whatever the cores do |
| Flash bank 2, SRAM1, SRAM2 | | | The M4 | ST's convention for the dual-core parts |

## Choices and what was rejected

- **DMA buffers in a non-cacheable region, not cache maintenance calls.** With the data cache on,
  a buffer DMA writes is stale in the cache until it is invalidated, and a buffer the core
  writes is not in RAM until it is cleaned. The two fixes are calling
  `SCB_InvalidateDCache_by_Addr` and `SCB_CleanDCache_by_Addr` at every hand-over, or marking the
  region non-cacheable in the MPU. The region costs slower access to a few hundred bytes per
  block; the calls cost code on the hottest path and fail silently when one is forgotten.
- **SRAM3 for those buffers, not SRAM1 or SRAM2.** ST's dual-core template gives SRAM1 and SRAM2
  to the M4 through the alias at 0x10000000. SRAM3 follows them in that alias, so the M4's
  linker script stops at 256 KB to leave it alone.
- **`.axi_bss` is not zeroed at start.** Clearing 512 KB at every start costs time for nothing:
  each block clears its own buffers in its reset function, which it must do anyway on a
  sample-rate change.
- **The first 32 bytes of ITCM stay empty.** ITCM starts at address 0. A function placed there
  would have a pointer that compares equal to NULL.
- **ST's start-up and system files, our own linker scripts.** ST's start-up applies the supply
  setting before anything else, which must not be got wrong. ST's linker scripts know nothing
  of this plan.

## Execution levels

| Level | Priority | Mechanism | Deadline |
|---|---|---|---|
| Audio | 1 | SAI DMA interrupt (batch 2) | One block: 167 us at 16 frames and 96 kHz |
| USB | 4 | OTG interrupt (batch 4) | 1 ms frames |
| Tick | 6 | SysTick | |
| Console | 8 | USART3 interrupt | |
| Deferred DSP | 14 | PendSV, set pending by the audio level | One partition of the room filter |
| Main loop | none | Thread mode | None |

PendSV is free for the deferred level because the M7 runs no RTOS. Its handler exists now and
calls an empty `deferred_dsp()`.

## Numerical behaviour

Not applicable. The measurable effect of this plan is timing: batch 3 measures a kernel in flash
against the same kernel in ITCM, and state in DTCM against state in AXI SRAM.

## Measured

| Item | Value | How |
|---|---|---|
| Sections land where intended | vector table at 0x08000000, `.data` and `.bss` in DTCM, stack top 0x20020000, M4 image at 0x08100000 with RAM at 0x10000000 | `readelf -l`, `nm` on both images |
| DTCM used by the skeleton | 33 608 B of 128 KB (the console queue, the self-test buffers, heap and stack reserve) | linker memory report |
| The MPU region works, DMA sees fresh data | not measured | batch 2, with the SAI |

## Open questions

- Whether DMA1 and DMA2 can reach DTCM on this part. The plan does not depend on it.
- Whether the M4, parked in stop mode, leaves the D2 peripherals the M7 has enabled running
  (SPEC V10). The console is on USART3, a D2 peripheral, so the first banner answers it.
