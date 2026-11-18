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

## Second round (2026-11-17, owner: "keep on")

| Step | Measured on the M7 | Notes |
|---|---|---|
| Saturation at 2x: strip default and the overdrive | overdrive 2479 to 1284; strip saturator 1204 to 578 | aliasing at 5 kHz -64 dB instead of -131 |
| Sample-peak limiter for the headphones (`kDspLimiterSamplePeak`) | 214 against 998 | no sample over the ceiling; true peak up to 3.03 dB over it (a quarter-rate sine at 45 degrees; theory 3.01) |
| Budget rule: the overdrive and strip saturation never together | refused with `err 10` (checked on the board) | the worst case pays for one of them |
| True-peak detector: 63-tap Nyquist interpolator, three 16-tap phases, instead of the 4x oversampler | limiter 998 to 665; latency L + 24 to L + 9; DTCM 8 KB smaller | true peak 0.262 dB over the internal threshold (0.198 before), still 0.24 dB under the set ceiling |
| Float32 PEQ sections at 1 kHz and above | not done | the worst case lets every band sit below 1 kHz, where double is needed: about 300 cycles even with ranges restricted |

Found on the way: the true-peak measurement in the tests read the cut edges of its slice (zero
padding rings, up to 0.77 dB); it now leaves them out. The batch 6 worst case did not change.

## Where it stands at 48 kHz, worst case

| Block | Cycles per frame |
|---|---|
| Two strips saturating (trim, PEQ, gate, compressor, 2x saturation) | 2 x 1163 = 2326 |
| Dearest effect allowed with them (the chorus; the overdrive is refused) | 609 |
| Reverb | 898 |
| Tone | 397 |
| Speaker stage: PEQ, delay, true-peak limiter, room FIR (estimate 900) | 574 + 665 + 900 = 2139 |
| Headphone stage: PEQ, crossfeed (estimate), sample-peak limiter | 564 + 50 + 214 = 828 |
| Conversion, mixer, metering (estimates) | 220 |
| **Total** | **about 7400, against 5833 (1.27 times)** |

The other worst case, the overdrive with the strips not saturating: 1170 + 1284 = 2454 in place of
2935, so about 6900.

## The M4 (2026-11-18)

Measured with `python tools/m4_bench.py --port COMx --results docs/results/bench_m4.md`: the M7
wakes the M4 through the SRAM4 mailbox (`fw/common/mailbox.h`), the M4 runs every self-test case
with its own cycle counter and reports cycles and an output CRC. The M4 runs at 200 MHz: its frame
at 48 kHz is 4166 cycles (2916 at 70 %).

| Case | M4 from flash | M4 from SRAM | M7 | Output vs PC on the M4 |
|---|---|---|---|---|
| gain_f32 | 46 | 17 | 11 | bit-identical |
| biquad_f32 (3 sections) | 229 | 79 | 51 | bit-identical |
| biquad_f64 (3 sections) | 8295 | 7837 | 169 | bit-identical (double in software: no double FPU) |
| reverb_f32 | 4136 | 1451 | 898 | bit-identical |
| fx_overdrive_f32 | 6942 | 2942 | 1284 | differs (its set-up uses the C library's float functions, a different build for the M4's FPU) |
| limiter_sp_f32 | 1949 | 1505 | 214 | bit-identical |

- The M4 has no cache: from flash its loops ran about 4.5 times the M7's cycles. Its DSP code and
  constants now live in its SRAM (copied with `.data` at start-up; `fw/cm4/stm32h755_cm4.ld`),
  about 1.5 to 3 times the M7's cycles.
- Double precision is out on the M4 (2600 cycles per biquad section): the PEQs, the tone control
  and ADAA stay on the M7, or would need float32 or Q31 there.
- **The reverb fits the M4**: 1451 cycles, 35 % of its frame, bit-identical with the PC.
  Moved there, the M7's worst case at 48 kHz falls from about 7400 to about 6500 cycles per frame:
  78 % of its frame, against the 70 % ceiling. The effect slot cannot join it (the overdrive alone
  is 2942 on the M4).

## The room FIR, measured (2026-11-18)

`docs/results/bench_fft.md`: stereo, 4096 taps per channel, on the M7, 1120 cycles per frame at
256-sample partitions (5.3 ms latency at 48 kHz), 940 at 512 (10.7 ms). The estimate was 900.
The FFTs are 46 % of it, and this FFT is plain radix-2; a faster one is the main lever left
(about 340 cycles at B = 256, estimate, [Verify] against CMSIS-DSP). On the M4 it takes 2545 M4
cycles per frame, 61 % of the M4's frame.

| Worst case at 48 kHz (two strips saturating, the chorus) | Room FIR B = 256 | B = 512 |
|---|---|---|
| Everything on the M7 | about 7620 (91 %) | about 7440 (89 %) |
| Reverb on the M4 | about 6720 (81 %) | about 6540 (78 %) |
| Room FIR on the M4 instead, reverb on the M7 | about 6500 (78 %) | about 6500 (78 %) |

The M7's ceiling is 70 % (5833). The last row moves the FIR (61 % of the M4) rather than the
reverb (33 %); the M4 cannot take both (94 %). The M4's RAM is 99 % used with the FIR's test
memory in it, and batch 11 plans to move the control core there, so that row has a cost the
others do not.

## Mixer, crossfeed and meters, measured (2026-11-18)

`python tools/target_test.py --port COMx`, M7, bit-identical with the PC:

| Block | Cycles per frame | Plan's estimate |
|---|---|---|
| Monitor mixer, 8 inputs to main and reverb send | 239 | 60 |
| Headphone crossfeed | 50 | 50 |
| Meter, stereo, true peak and BS.1770 loudness | 601 | 100 for all metering |
| Meter, stereo, peak and RMS only | 57 | |

The worst case's "conversion, mixer, metering" line was 220 (estimates). With the mixer, one full
meter on the mix and peak meters on the two inputs it is at least 239 + 601 + 2 x 57 = 954, before
conversion and any output meters:

| Worst case at 48 kHz, room FIR at B = 256 | Cycles per frame |
|---|---|
| Everything on the M7 | about 8350 (100 %) |
| Reverb on the M4 | about 7450 (89 %) |

Metering only feeds the display, the LEDs and the PC, so it can run late and elsewhere: on the M4
`meter_f32` takes 1312 M4 cycles (31 % of its frame) and is bit-identical with the PC. The
mixer's output differs on the M4 (its pan law calls `cosf` and `sinf`, which the M4's C library
rounds differently), like the overdrive's set-up.

## The 8c split, measured (2026-11-18)

Owner's decision: the reverb and the meters move to the M4 (`docs/notes/core_split.md`). With no
audio path yet, `splitbench` runs the split at the real block rate: the M7 posts 16-frame blocks
of -20 dBFS noise every 333 us, the M4 runs the reverb and four meters (the mix with true peak and
loudness; inputs, speaker out and headphone out with peak and RMS) and hands the return back one
block later, and the M7 runs the same code on the same blocks to check it.

```
cmake --build --preset fw
powershell -File tools/flash.ps1
python tools/console.py --port COMx      then: splitbench 60
```

| | First run | Meter read split | And libgcc in the M4's SRAM |
|---|---|---|---|
| Late blocks (of 180 000) | 1 in 30 | 1790 (one per reading) | **0** |
| M4 load, mean | 74 % | 74 % | **67 %** |
| M4 load, dearest block | 165 % | 104 % | **83 %** |
| Reverb return, M4 vs M7 | bit-identical | bit-identical | bit-identical |
| Meter readings, M4 vs M7 | differ (last bit of log10f) | bit-identical | bit-identical |
| Removed from the M7, cycles per frame | | | 1772 (about 90 of it the bench's checksum) |
| The exchange on the M7, cycles per frame | | | 151 |

| Worst case at 48 kHz, room FIR at B = 256 | Cycles per frame |
|---|---|
| Everything on the M7, with the four meters of the decision (601 + 3 x 57) | about 8410 (101 %) |
| Reverb and meters on the M4, plus the exchange | **about 6890 (83 %)**, ceiling 5833 |

About 1050 cycles per frame are still over the ceiling. Candidates, for the owner: CMSIS-DSP's FFT
in the room filter (about 340, estimate), the room filter at B = 512 (180, 5.3 ms more latency),
a budget rule like the one that keeps the overdrive and the strip saturation apart, and the
mixer writing the send straight into the exchange slot (part of the 151, not measured).

After the linker change the M4's self-test cycles were taken again (`bench_m4.md`): the full meter
1312 to 1020, the reverb 1451 to 1387, every bit-identical case still bit-identical.

## Option D: float32 for PEQ bands 3 and 4 (2026-11-18)

Owner's decision ("A + C + D"); `docs/notes/peq_float32_bands.md`. Bands 3 and 4 of every PEQ run
the float32 section (about 17 cycles per sample) instead of the double one (56.4) at 48 kHz, with
their range starting at 2.5 kHz. Six PEQ channels in the worst case (two strips, speaker and
headphones in stereo), two sections each: about 6 x 2 x 39 = **470 cycles per frame** saved,
estimated from the section costs. Not yet measured on the board: `target_test` reports the new
self-test case `peq_f32` (one PEQ, five sections on), against about 282 cycles before (5 x 56.4).

**Measured on the M7** (`target_test`, after the merge): `peq_f32` 207 cycles per frame,
bit-identical with the PC, against 282 for five double sections (5 x 56.4 from `biquad_f64`). So
75 per PEQ channel, about **450 cycles per frame** over the six in the worst case.

## A + C + D together, worst case at 48 kHz (2026-11-18)

| Step | Cycles per frame | Basis |
|---|---|---|
| Before, with the reverb and meters on the M4 | about 6890 (83 %) | `splitbench`, the measured blocks |
| A: the effect slot and strip saturation never together | -481 | the worst strips plus effect is now the overdrive with clean strips (2454 against 2935), measured blocks |
| C: CMSIS-DSP's FFT in the room filter | -203 | measured, 1120 to 917 |
| D: float32 PEQ bands 3 and 4 | -450 | measured, 282 to 207 per PEQ channel |
| **After** | **about 5760 (69 %)**, ceiling 5833 | |

Under the ceiling, by about 75 cycles per frame. That margin is thin: the conversion line is still an
estimate (batch 2 measures it), and so is the headphone crossfeed's place in the chain. If batch
2 or the assembly in 8c finds more, the next steps in order are the tone's treble shelf in float32
(about 78, `peq_float32_bands.md`), the mixer writing the send straight into the exchange slot,
and the room filter's length (batch 9).
