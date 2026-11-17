/* Runs the DSP library's self-test cases on the target (dsp/include/dsp/dsp_selftest.h) and
 * prints what tools/target_test.py compares with the PC library.
 *
 * Output format, one line per case:
 *   bench <name> fmt=<f32|q31> frames=<n> runs=<n> min=<cycles> med=<cycles> max=<cycles>
 *         crc=<8 hex digits>
 * Cycles are for the whole case (set-up of the block's state plus every frame), with interrupts
 * left on, so `max` includes whatever the tick and the console took. `min` is the figure to
 * quote. The checksum is of the output bytes, little-endian words.
 *
 *   vec <name> <n>      then <n> output words as 8 hex digits, 8 to a line, then `end`.
 */
#ifndef BENCH_H
#define BENCH_H

#include <stdbool.h>

void bench_run_all(void);
/* False when no case has that name. */
bool bench_dump_vector(const char *name);
void bench_list(void);

#endif
