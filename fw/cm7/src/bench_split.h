/* `splitbench`: the 8c split (fw/common/split.h) run at the real block rate without audio.
 * The M7 posts 16-frame blocks of -20 dBFS noise to the M4 every 333 us (48 kHz), the M4 runs
 * the reverb and the meters on them, and the M7 collects each return one block later. The M7
 * runs the same code on the same blocks itself, so the M4's results are checked bit for bit.
 * Prints the M4's load, what the M7 saves, what the exchange costs the M7, and how many blocks
 * came back late.
 */
#ifndef BENCH_SPLIT_H
#define BENCH_SPLIT_H

#include <stdint.h>

void bench_split(uint32_t blocks);

#endif
