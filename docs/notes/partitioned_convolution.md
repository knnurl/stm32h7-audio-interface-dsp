# Partitioned convolution for the room correction (batch 9 spike)

Blocks: `dsp/include/dsp/dsp_fft.h`, `dsp/include/dsp/dsp_pconv.h`. Measurements:
`docs/results/bench_fft.md`. This note covers the costing spike only; the room measurement, the
filter design and the upload are batch 9 proper.

## Why partitions, and why uniform

A 4096-tap FIR (85 ms at 48 kHz, enough to correct down to about 50 Hz [Verify against the room
measurement]) costs 4096 multiply-adds per sample per channel in direct form: about 8200 cycles
per stereo frame at one cycle each, the whole M7 frame. Fast convolution moves the work to
the frequency domain, where one block of B samples costs two FFTs and a complex multiply per bin.
One FFT block as long as the whole filter would add 85 ms of latency, so the filter is cut into
P partitions of B taps. Each partition's spectrum is computed once, when the filter is loaded.
At run time the input spectra of the last P blocks are kept in a ring (the frequency-domain delay
line), and each block's output is the sum over k of input spectrum (newest - k) times filter
partition k. One forward and one inverse FFT per block then serve every partition.

Uniform partitions (all B) are the simplest form and the one specified for batch 9 (SPEC decision
2026-11-15). Non-uniform partitions (short ones first, long ones later) cut latency at equal cost
but need several FFT sizes and a scheduler; they stay a stretch goal.

## The method in this code

- **Overlap-save.** Each step transforms the last 2B input samples, N = 2B points. After the
  multiply-add and the inverse, the first B output samples are circular wrap-around and are
  dropped; the last B are the linear convolution. No overlap-add buffer is needed.
- **Real FFT, packed spectrum.** The input is real, so an N-point real FFT is done as an
  N/2-point complex FFT plus a split step, about half the work. The spectrum is stored in
  CMSIS-DSP's packed layout (DC and Nyquist in the first two floats), so `arm_rfft_fast_f32` can
  be dropped in as a yardstick or a replacement without touching `dsp_pconv`.
- **Scaling folded into the filter.** Neither transform scales. The inverse returns N times the
  signal, so the filter spectra are stored times 1/N when loaded, which costs nothing per block.
- **Generated twiddles.** cos and sin come from a table written by
  `tools/design/fft_twiddles.py`, not from the C library at start-up. MSVC's, newlib's and the
  M4's `sinf` differ in the last bit (the M4 already showed it with `tanhf`); with one table, the
  PC, the M7 and the M4 give bit-identical output, and the target comparison checks it.
- **Latency: B samples.** The output during a block is the result of the previous step. y[t] =
  sum_j h[j] x[t - B - j]; a test checks the peak lands at exactly B plus the filter's own delay.

## Cost model, and what the board says

Per step and channel: two N-point real FFTs, plus P (B + 1) complex multiply-adds. Per sample:

    cost = (2 FFT(2B) + P (B + 1) c_mac) / B,   P = taps / B

The multiply-add term per sample is about P c_mac = (taps / B) c_mac, so it falls as B grows,
while the FFT term per sample grows only as log B. Measured on the M7 (4096 taps, stereo):
2460 cycles per frame at B = 64, 1120 at 256, 940 at 512. At B = 256 the FFTs are 46 % and the
multiply-adds 54 %. The multiply-adds read 128 KB of spectra per step through a 16 KB cache and
are limited by AXI SRAM; a preload hint and `restrict` took 16 % off.

What would lower it, in order of expected gain per effort:
1. A faster FFT. Done (2026-11-18): CMSIS-DSP's `arm_rfft_fast_f32` replaced `dsp_fft` in the
   convolver, 1120 to 917 cycles per frame at B = 256, measured and bit-identical with the PC.
   It was reported at a third of `dsp_fft`'s cycles; measured, 0.55 to 0.6.
2. A shorter filter. The transcripts' cabinet IRs carry most of their information in the first
   20 to 40 ms; a room correction above the Schroeder frequency needs less length than one that
   chases the modes. The filter design in batch 9 sets the length, and the cost scales with it.
3. B = 512: 940 cycles, at 10.7 ms of latency on the monitors.

## The deferred level

The step is too long for the audio interrupt (286 000 cycles at B = 256, 34 % of a whole 5.3 ms
partition period). The SPEC's interrupt table puts it at the deferred level (PendSV),
pre-empted by audio. It then
finishes somewhere in the next partition period, so its output can be used only from the
partition after: the latency becomes 2B unless the first partition is done in the time domain,
in the audio interrupt (B direct taps: 256 multiply-adds per sample per channel, about 500
cycles per frame [estimate]). Batch 9 chooses between 2B of latency and that cost; this spike
measures only the uniform part.

## From the transcripts

Read in full: #126 (Real-time impulse response simulation), #111 (STM32 FFT with CMSIS-DSP),
#141 (STM32 real-time FIR with CMSIS-DSP).

- **#126:** Phil truncates a 0.5 s cabinet IR to 256, then 128 and 64 taps, and runs it as a
  direct FIR, because "convolution is a fairly costly operation" and long direct filters will not
  run in real time; he names FFT convolution as the faster method for another video. He measures
  the lost detail on an analyser as the taps go down. Taken here: the length trade-off is real
  and audible, so batch 9 should measure the corrected room at two or three filter lengths, not
  only at the longest that fits. Not taken: the hard cut at the end; he notes a window would
  smooth it, and the batch 9 design should taper the tail.
- **#111:** CMSIS's `arm_rfft_fast_f32` takes real input of a power-of-two length and returns
  N/2 complex values interleaved, with the inverse selected by a flag. `dsp_fft` keeps exactly
  that packed layout so the two are interchangeable and can be compared.
- **#141:** `arm_fir_f32` wants time-reversed coefficients and a state buffer of
  taps + block - 1; he warns that coefficients designed in double lose accuracy as float. He
  reports an M7 running a long direct FIR at 48 kHz and starting to struggle above that length
  (the number is garbled in the transcript: "496 point filter at 40K") [Verify]. Taken here: the
  filter spectra are computed in single precision from float taps, and the test compares against
  double-precision direct convolution (132 dB below the output), so the precision loss is
  measured rather than assumed.
