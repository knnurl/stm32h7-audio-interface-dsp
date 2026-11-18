#include "split_dsp.h"

#include "dsp/dsp_crc32.h"

int32_t split_dsp_init(SplitDsp *dsp, float *reverb_mem, int32_t reverb_mem_len) {
    if (dsp_reverb_f32_init(&dsp->reverb, SPLIT_SAMPLE_RATE_HZ, reverb_mem, reverb_mem_len) != 0) {
        return -1;
    }
    (void)dsp_meter_f32_init(&dsp->meter[0], SPLIT_SAMPLE_RATE_HZ, 2,
                             kDspMeterTruePeak | kDspMeterLoudness);
    for (int32_t m = 1; m < kSplitMeters; ++m) {
        (void)dsp_meter_f32_init(&dsp->meter[m], SPLIT_SAMPLE_RATE_HZ, 2, 0);
    }
    dsp->blocks = 0u;
    dsp->out_crc = 0u;
    dsp->reading_crc = 0u;
    return 0;
}

int32_t split_dsp_block(SplitDsp *dsp, const SplitIn *in, SplitOut *out) {
    dsp_reverb_f32_process(&dsp->reverb, in->send[0], in->send[1], out->ret[0], out->ret[1],
                           kSplitFrames);
    for (int32_t m = 0; m < kSplitMeters; ++m) {
        dsp_meter_f32_process(&dsp->meter[m], in->tap[2 * m], in->tap[2 * m + 1], kSplitFrames);
    }
    dsp->out_crc = dsp_crc32(dsp->out_crc, out, sizeof(*out));
    dsp->blocks += 1u;
    if (dsp->blocks % kSplitReadEvery != 0u) {
        return 0;
    }
    for (int32_t m = 0; m < kSplitMeters; ++m) {
        dsp_meter_f32_snapshot(&dsp->meter[m], &dsp->raw[m]);
    }
    dsp->reading_crc = dsp_crc32(dsp->reading_crc, dsp->raw, sizeof(dsp->raw));
    return 1;
}
