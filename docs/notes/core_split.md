# Design note: the 8c core split (reverb and meters on the M4)

Owner's decision, 2026-11-18. Code: `fw/common/split.h` (the shared layout), `fw/common/split_dsp.h`
(what the M4 runs), `fw/cm4/src/main.c` (`split_serve`), `fw/cm7/src/bench_split.h` (`splitbench`).
Measurements: `docs/results/budget_target.md`, section "The 8c split, measured".

## What moves, and why these two

The M7's worst case at 48 kHz was about 8400 cycles per frame against a ceiling of 5833 (70 %).
Two blocks are cheap to move because nothing on the M7 waits for them within the block:

- **The reverb.** It sits on a send and comes back as a return. One block of extra delay on the
  return (0.33 ms at 48 kHz) adds to its 10 ms pre-delay and is not heard.
- **The meters.** They feed the panel LEDs, the PC and the protocol's `meters` lines at about
  30 Hz; nothing in the audio path reads them.

Both were bit-identical with the PC on the M4 in the self-test cases. Rejected: the room FIR on
the M4 instead of the reverb. It takes 61 % of the M4, so the meters could not join it, and its
output is on the monitors' direct path, where the block of delay would be heard as latency.

## The exchange

Once per 16-frame block, through SRAM4 (reachable by both cores), after the mailbox:

1. The M7 copies the send (stereo) and the eight metered signals into slot `n & 1`, cleans them
   from its data cache, then writes `seq_in = n + 1` and cleans that line.
2. The M4 sees `seq_in` move, runs the reverb and the meters on the slot, writes the return into
   its own slot `n & 1`, then writes `seq_done = n + 1`.
3. At block n + 1 the M7 reads the return of block n (invalidating its cache first). If
   `seq_done` has not reached n + 1, the block is late.

Rules that keep it correct without locks:
- **Each side writes only its own lines.** `SplitToM4` and `SplitFromM4` start on separate 32-byte
  cache lines and are whole lines long, so the M7's invalidate of the one can never throw away
  its own dirty data in the other. The M4 has no data cache.
- **Order by barriers.** Data first, then a `DMB`, then the sequence number, on both sides.
- **Two slots.** The M7 writes slot `n & 1` only after it has read the return of block n - 1, so
  the slot it overwrites (block n - 2) is finished.
- **Meters go across linear.** The M4 takes `dsp_meter_f32_snapshot` every 100 blocks (33 ms) and
  publishes it under a sequence lock (odd while being written); whoever shows the value calls
  `dsp_meter_raw_to_reading`.

The M4 polls `seq_in` here. Batch 11 replaces the polling with a hardware-semaphore interrupt so
the M4 can run the control tasks between blocks; the layout and the rules stay.

## What the board showed, and what changed because of it

First run (60 s, 180 000 blocks): the reverb's return bit-identical through the exchange, but
**1 block in 30 late** and the **meters differing** between the cores.

1. The M4's dearest block took 165 % of a block period, against a mean of 74 %. Separated by
   block type: blocks with a meter reading 164 %, the others 75 %. The reading converts to dB with
   `log10f` and `log10` (about 30 calls), and the M4's C library also rounds those differently
   from the M7's, which was the meter difference. **Change:** the read split into a snapshot and
   a conversion (`metering.md`). Result: 104 %, meters bit-identical.
2. Still one late block per reading. The rest was the loudness windows' sums in double: the M4
   has no double-precision FPU, so they call `libgcc`'s soft-float routines, which ran from flash
   with no cache while the DSP library runs from SRAM. **Change:** `libgcc` and the split's code
   copied to the M4's SRAM with the DSP library (`stm32h755_cm4.ld`). Result: **0 late blocks
   in 180 000, mean 67 %, dearest 83 %**. As a side effect the M4's full meter went from 1312 to
   1020 cycles and the reverb from 1451 to 1387.

## What it buys and costs

Per frame, from `splitbench 60` (the M7 runs the same code on the same blocks to check the M4,
which is also how the saving is measured):

| | Cycles per frame |
|---|---|
| Removed from the M7 (reverb, four meters) | about 1680 (1772 measured, less about 90 of checksum the bench adds) |
| Added to the M7 (the exchange: copies and cache maintenance) | 151 |
| M4 load | mean 67 %, dearest block 83 % |

The M7's worst case falls from about 8400 to about 6890 cycles per frame (83 %): still about 1050
over the 70 % ceiling. What closes the rest is the owner's call (`budget_target.md`); the
candidates are CMSIS-DSP's FFT for the room filter (about 340, estimate), a budget rule, and the
exchange itself: the mixer could write the send straight into the slot instead of a copy [not
measured].

The M4 has 17 % left in its dearest block for the control tasks of batch 11. That is enough only
if those run between blocks at a lower priority, as planned.

## From the transcripts

Read: #55 (I2S, DMA and double buffering), the double-buffering passage of "Digital Audio
Processing with STM32 #1". None of the 29 covers two cores, inter-core messaging or shared memory
(searched for "dual core", "M4", "semaphore", "shared memory").

- **#55:** Phil splits each DMA buffer in two halves, processes one while the DMA fills the other,
  and flips pointers on the half-complete and complete callbacks, with a flag telling the main
  loop that data is ready. Taken: the same ping-pong idea between the cores, two slots used
  alternately by block number, with a sequence number in place of his ready flag. Differs: his
  flag is set and cleared by one core; here each side owns one counter and never writes the
  other's, which is what makes it safe across two cores and a data cache without a lock.
- **#1 (introduction):** the reason he gives for double buffering, more time to process while the
  transfer runs, is the reason here too: the M4 works on block n while the M7 is already
  producing block n + 1.
