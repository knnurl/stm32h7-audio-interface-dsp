/* Batch 9's costing spike on the M7: the real FFT at every size and the partitioned convolver at
 * every partition size, so the room correction's cost is measured before its design is fixed.
 *
 *   fftbench   fftbench n=<points> fwd=<cycles> inv=<cycles>, for 64 to 2048 points; then
 *              `fftbench done`. Minimum of 9 runs, data in AXI SRAM, code in ITCM.
 *   convbench  convbench block=<B> parts=<P> taps=4096 ch=2 per_frame=<cycles>
 *              step_call=<cycles> latency_ms48=<ms>, for B = 64 to 512; then `convbench done`.
 *              per_frame: the average over 8 partitions of 16-frame calls, both channels
 *              (what the budget counts). step_call: the dearest 16-frame call, the one that ran
 *              both channels' partition steps (what the deferred level must finish in time).
 *              Minimum over 5 repetitions of each.
 */
#ifndef BENCH_FFT_H
#define BENCH_FFT_H

void bench_fft(void);
void bench_conv(void);

#endif
