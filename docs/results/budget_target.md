# The SPEC 3.4 budget, with the first board measurements

Measured 2026-11-17 on the Nucleo-H755ZI-Q, M7 at 400 MHz (checked against the HSE: 399 999
cycles per ms), firmware 0.2.0 built with `-O2`, code in flash, both caches on, delay memory in
AXI SRAM. Command: `python tools/target_test.py --port COMx --results docs/results/bench_target.md`
(per-case table in `bench_target.md`). Every case matched the PC: 22 bit-identical, 2 within
-132 dBFS (the two that call `tanhf`).

Cycles are per frame (all channels of one sample period), processing only: the bench times
each case from the point its set-up ends. Per-frame cost hardly depends on the sample rate, so the
same column serves both rates.

| Block | Cycles per frame | Source |
|---|---|---|
| Sample conversion, USB both ways | 60 | estimate (batch 2) |
| Input strip, each: trim, HPF and 4-band PEQ (5 double-state sections) | 293 | measured: gain_f32 11 + 5 x 56.4 (biquad_f64, 169 for 3 sections) |
| Input strip, each: gate and compressor | 289 | measured: gate_f32 44 + comp_f32 245 |
| Input strip, each: saturation, 4x | 1678 | measured: sat_os4_f32 (ADAA: 490) |
| Monitor mixer | 60 | estimate (batch 8c) |
| Reverb, 8-line FDN, stereo | 909 | measured: reverb_f32 |
| Effect slot, dearest effect | 3661 | measured: fx_overdrive_f32 (next: echo at 96 kHz 800, chorus 614) |
| Tone, stereo | 396 | measured: tone_f32 |
| Speaker stage: PEQ (5 double-state sections, stereo) and delay | 574 | derived: 2 x 282 + 10 estimated for the delay |
| Speaker stage: true-peak limiter, stereo | 1241 | measured: limiter_f32 |
| Speaker stage: room FIR | 900 | estimate (batch 9) |
| Headphone stage: PEQ, crossfeed, limiter | 1855 | derived: 564 + 50 estimated crossfeed + 1241 |
| Metering | 100 | estimate (batch 8c) |
| **Total, two strips** | **about 14 300** | |

| Rate | Cycles per frame available | Ceiling at 70 % | Total against it |
|---|---|---|---|
| 96 kHz | 4166 | 2916 | 4.9 times over |
| 48 kHz | 8333 | 5833 | 2.4 times over |

## Where it goes

Four items are 74 % of the total: the two saturators (3356), the overdrive (3661), the two
limiters (2482) and the five double-state PEQ sets (about 1700). Not yet measured, so not yet
claimed: how much of the saturator and the overdrive is `tanhf` from the C library (four calls
per input sample at 4x), how much the oversampling filters, and what moving the hot kernels to
ITCM (SPEC 6.2, not done yet) gains.

## Flash, from the board

| Item | Value | Command |
|---|---|---|
| First preset-store write: sector erase (128 KB) plus a record | 960 ms | `ptime` on a blank store |
| A record of 1.3 KB | 4.5 ms (about 110 us per 32-byte flash word) | `ptime` |
| Power-on record and a preset across a hardware reset | restored; mute back on | `-hardRst`, then `get`, `preset load 1` |

## First optimisation round (2026-11-17, owner's go)

Each step measured before and after on the board (`python tools/target_test.py --port COMx`),
every case still matching the PC.

| Step | What it measured | Result |
|---|---|---|
| Decompose the 4x saturator | `tanhf` from the C library 178 cycles per call; the 4x oversampler alone 952 per sample | The filters, not `tanhf`, were the larger part: the guess in the first table was wrong |
| `dsp_fast_tanhf` (exp2 polynomial and one division; absolute error 1.9e-7) | 121 cycles per call | Only a third cheaper; kept, as it is also bit-identical between the PC and the M7 (no library call) |
| Half-band kernel: symmetric taps folded, four partial sums | oversampler 952 to 715; 4x saturator 1678 to 1204; limiter 1241 to 993; 96 kHz echo 800 to 537; overdrive 3661 to 2479 | The generated loop is now about 3 to 4 cycles per tap pair; six calls per input sample remain |
| The whole DSP library in ITCM (27.6 KB) | no change beyond noise (within 10 cycles on every case) | The I-cache already held the loops; kept, harmless |
| Saturation at 2x (`sat_os2_f32`, new case) | 570 against 1204 at 4x | Aliasing at 5 kHz: -64 dB at 2x, -131 dB at 4x (`b6_aliasing.md`) |

Found on the way: every flash added a HardFault to the fault record (pc 0x24000000, in ST's flash
loader in AXI SRAM). Reproduced: three resets added none, each flash one. Cause: `flash.ps1` ran
two programmer sessions and the core was left running in the loader between them. Fixed with one
session and one reset; two further flashes added none.

## Where it stands at 48 kHz (the rate rev A runs at, owner 2026-11-17)

| Block | Cycles per frame |
|---|---|
| Two input strips (trim, PEQ, gate, compressor, 4x saturation) | 2 x 1789 = 3578 |
| Reverb | 898 |
| Dearest effect: the overdrive (4x) | 2499 |
| Tone | 397 |
| Speaker stage: PEQ, delay, limiter, room FIR (estimate 900) | 2473 |
| Headphone stage: PEQ, crossfeed (estimate 50), limiter | 1613 |
| Conversion, mixer, metering (estimates) | 220 |
| **Total** | **about 11 700, against a ceiling of 5833 (2.0 times over)** |

With saturation at 2x in the strips and the overdrive (the overdrive's 2x figure estimated from
the saturator's ratio): about 9200, 1.6 times over. What is left is spread out: two limiters
2000, the PEQs about 1700, the reverb 900, the room FIR 900 (estimate).

