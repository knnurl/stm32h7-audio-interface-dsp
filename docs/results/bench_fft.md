# Batch 9 costing spike: the real FFT and the partitioned convolver (2026-11-18)

Measured on the Nucleo-H755ZI-Q, M7 at 400 MHz, code in ITCM, data in AXI SRAM (D-cache on),
GCC 13.3 `-O2 -ffp-contract=off`. Reproduce:

```
cmake --build --preset fw
powershell -File tools/flash.ps1
python tools/console.py --port COMx      then: fftbench, convbench
python tools/target_test.py --port COMx  (rfft512_f32 and pconv_f32 against the PC)
python tools/m4_bench.py --port COMx     (the same cases on the M4)
```

## Real FFT (`dsp_fft`, radix-2, minimum of 9 runs)

| Points | Forward | Inverse | Cycles per point |
|---|---|---|---|
| 64 | 3318 | 3187 | 52 |
| 128 | 7176 | 6926 | 56 |
| 256 | 15495 | 15019 | 61 |
| 512 | 33584 | 32633 | 66 |
| 1024 | 71945 | 70290 | 70 |
| 2048 | 161479 | 158976 | 79 |

Accuracy against numpy in double precision: 0.9e-7 to 1.3e-7 relative (64 to 2048 points).
This is a plain radix-2 kernel. CMSIS-DSP's `arm_rfft_fast_f32` was reported at about a third of
these cycles on the M7; measured below, it is about 0.55 to 0.6 of them.

### CMSIS-DSP as the yardstick (2026-11-18, v1.16.2, `cmsisfft`)

Same board, same flags (`-O2 -ffp-contract=off`), its code in ITCM like `dsp_fft`, minimum of 9:

| Points | CMSIS forward | `dsp_fft` forward | CMSIS inverse (scales by 1/n) | `dsp_fft` inverse |
|---|---|---|---|---|
| 256 | 8938 | 15567 | 10054 | 15018 |
| 512 | 19070 | 33639 | 21269 | 32576 |
| 1024 | 36579 | 72375 | 40957 | 70266 |

The two forward spectra agree to 1.3e-7 to 1.4e-7 of the largest bin. In the convolver at
B = 256 (one forward and one inverse 512-point FFT per channel per step), CMSIS would save about
(33639 + 32576 - 19070 - 21269) x 2 / 256 = about 200 cycles per frame, not the 340 estimated.
Not adopted: it overwrites its input (the convolver would need a copy), its inverse scales by 1/n
(the filter's 1/N would come out), and the PC build would have to compile CMSIS too to stay
bit-identical. That is for the owner to weigh against 200 cycles.

## Partitioned convolver (`dsp_pconv`), stereo, 4096 taps per channel

16-frame calls as the audio interrupt will make them, eight partitions per repetition, minimum of
five repetitions. Final code: preload hint and `restrict` in the multiply-add loop.

| Partition B | Partitions P | Cycles per frame (average) | Dearest 16-frame call | Latency at 48 kHz |
|---|---|---|---|---|
| 64 | 64 | 2460 | 157 000 | 1.33 ms |
| 128 | 32 | 1534 | 195 000 | 2.67 ms |
| **256** | **16** | **1120** | **286 000** | **5.33 ms** |
| 512 | 8 | 940 | 473 000 | 10.67 ms |

The self-test case `pconv_f32` (B = 256) gives 1112 cycles per frame and is bit-identical with the
PC on the M7 and on the M4. On the M4 it takes 2545 M4 cycles per frame, 61 % of the M4's frame.
Error against direct convolution in double precision: 131 to 133 dB below the output (B = 64 to
512, 4096 taps, one second of noise).

### Where the cycles go at B = 256 (per step, both channels)

| Part | Cycles | Share |
|---|---|---|
| Two forward and two inverse 512-point FFTs | about 132 000 | 46 % |
| 2 x 16 x 256 complex multiply-adds, spectra streamed from AXI SRAM | about 154 000 | 54 % |

The multiply-adds run at about 19 cycles per complex bin, for about 16 instructions. The likely
cause is waiting for AXI SRAM: each step reads 128 KB of spectra through a 16 KB data cache, at
about 0.33 GB/s, and the preload hint alone took 14 % off. Not yet shown directly (a run with the
spectra in DTCM would; they do not fit there in stereo) [Verify]. Every partition size
reads the same 128 KB per step (2 x taps x 2 floats per channel), which is why a larger B costs
less per frame.

### What was tried

| Change | B = 256 | Kept |
|---|---|---|
| First version | 1337 | |
| Preload hint two lines ahead of the multiply-add loop (`__builtin_prefetch`) | 1151 | yes |
| `restrict` on the loop's pointers, two bins per pass | 1120 | yes |

Neither changes a result (the tests and the target comparison are bit-identical before and after).

## Found on the way

With the DSP library in its image, the M4's start-up code copies about 80 KB and zeroes about
250 KB before `main()` parks it. The M7 waited 65535 polls for that and reported `cm4_parked=0`
on one boot, although the M4 then answered `m4bench`. The wait is now up to 524288 polls and the
banner prints the count: 48075 and 49141 on two boots, so the old limit left only about 25 %
margin. The M4's RAM is 99 % used with the convolver's test pool in it.
