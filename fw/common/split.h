/* The audio exchange between the cores for the 8c split (SPEC decision 2026-11-18): the M7 keeps
 * the signal path and hands the M4, once per 16-frame block, the reverb's send and the signals
 * to meter; the M4 runs the reverb and the meters (split_dsp.h) and hands back the reverb's
 * return, which the M7 uses one block later (0.33 ms at 48 kHz). The meters go across as linear
 * snapshots (DspMeterRaw); the reader converts them to dB, so the M4 does no logarithms.
 *
 * Layout: in SRAM4 after the mailbox. Two slots each way, used alternately by block number. The
 * M7 writes only `SplitToM4` and the M4 only `SplitFromM4`, each starting on its own 32-byte
 * cache line, so the M7's clean of the one and invalidate of the other never touch a line the
 * other core writes. The M4 has no data cache.
 *
 * Handshake, block n (counting from 0):
 *   M7: copies the block's signals into in[n & 1], cleans them, then writes seq_in = n + 1 and
 *       cleans that line;
 *   M4: waits for seq_in > done, processes in[done & 1] into out[done & 1], then writes
 *       seq_done = done + 1;
 *   M7: at block n + 1, reads out[n & 1] once seq_done > n. Not there yet: the block is late.
 * Batch 11 replaces the M4's polling with a semaphore interrupt; the layout stays.
 */
#ifndef SPLIT_H
#define SPLIT_H

#include "dsp/dsp_meter.h"
#include "mailbox.h"

#include <stdint.h>

#define SPLIT_ADDR (MAILBOX_ADDR + 0x400u)

enum {
    kSplitFrames = 16,
    kSplitSlots = 2,
    /* Signals to meter: the monitor mix (L, R), inputs 1 and 2, speaker out (L, R), headphone
     * out (L, R). */
    kSplitTaps = 8,
    kSplitMeters = 4,
    kSplitReadEvery = 100, /* Meter reads every 100 blocks: 33 ms at 48 kHz, as the protocol. */
};

typedef struct {
    float send[2][kSplitFrames];
    float tap[kSplitTaps][kSplitFrames];
} SplitIn; /* 640 bytes, a whole number of cache lines. */

typedef struct {
    float ret[2][kSplitFrames];
} SplitOut; /* 128 bytes. */

typedef struct {
    SplitIn in[kSplitSlots];
    uint32_t seq_in; /* Blocks posted. */
    uint32_t stop;   /* Non-zero: the M4 finishes and parks. */
    uint32_t pad[6];
} __attribute__((aligned(32))) SplitToM4;

typedef struct {
    SplitOut out[kSplitSlots];
    uint32_t seq_done;      /* Blocks finished. */
    uint32_t busy_max;      /* M4 cycles for the dearest block. */
    uint32_t busy_sum_lo;   /* Sum of the blocks' M4 cycles (64 bits in two words). */
    uint32_t busy_sum_hi;
    uint32_t out_crc;       /* CRC-32 of every return block, in order. */
    uint32_t reading_crc;   /* CRC-32 of every meter snapshot taken, in order. */
    uint32_t reading_seq;   /* Odd while `raw` is being written. */
    uint32_t busy_max_plain; /* M4 cycles for the dearest block without a meter reading. */
    DspMeterRaw raw[kSplitMeters]; /* The newest snapshot of each meter; dB by the reader. */
} __attribute__((aligned(32))) SplitFromM4;

typedef struct {
    SplitToM4 to_m4;
    SplitFromM4 from_m4;
} SplitShared;

#define SPLIT ((SplitShared *)SPLIT_ADDR)

_Static_assert(sizeof(Mailbox) <= 0x400u, "the mailbox runs into the split area");
_Static_assert(sizeof(SplitToM4) % 32u == 0u, "SplitToM4 must be whole cache lines");
_Static_assert(sizeof(SplitFromM4) % 32u == 0u, "SplitFromM4 must be whole cache lines");

#endif
