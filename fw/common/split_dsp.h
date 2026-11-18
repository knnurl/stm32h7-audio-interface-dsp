/* What the M4 runs in the 8c split, per 16-frame block: the reverb on the send, and four meters
 * (the monitor mix with true peak and loudness; inputs, speaker out and headphone out with peak
 * and RMS; metering.md). Compiled into both images, so the M7 can run the same code on the same
 * blocks and check the M4's results bit for bit (`splitbench`).
 *
 * Assumptions: 48 kHz; the reverb at its defaults (2 s low, 1 s high, 10 ms pre-delay).
 * Latency: none inside; the exchange adds one block (split.h).
 */
#ifndef SPLIT_DSP_H
#define SPLIT_DSP_H

#include "split.h"

#include "dsp/dsp_meter.h"
#include "dsp/dsp_reverb.h"

#include <stdint.h>

#define SPLIT_SAMPLE_RATE_HZ 48000.0f

typedef struct {
    DspReverbF32 reverb;
    DspMeterF32 meter[kSplitMeters];
    uint32_t blocks;
    uint32_t out_crc;
    uint32_t reading_crc;
    DspMeterRaw raw[kSplitMeters];
} SplitDsp;

/* Returns 0, or -1 if mem is shorter than dsp_reverb_f32_mem_needed at 48 kHz. */
int32_t split_dsp_init(SplitDsp *dsp, float *reverb_mem, int32_t reverb_mem_len);
/* One block. Returns 1 when it took the meters' snapshots (every kSplitReadEvery blocks). */
int32_t split_dsp_block(SplitDsp *dsp, const SplitIn *in, SplitOut *out);

#endif
