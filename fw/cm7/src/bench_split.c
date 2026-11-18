#include "bench_split.h"

#include "board.h"
#include "mailbox.h"
#include "split.h"
#include "split_dsp.h"

#include "dsp/dsp_crc32.h"
#include "dsp/dsp_testsig.h"

#include <stdio.h>
#include <string.h>

enum {
    kReverbMem = 17888, /* dsp_reverb_f32_mem_needed(48000). */
    kSignals = 2 + kSplitTaps,
    kLateLimitBlocks = 20, /* An M4 this late has stopped: give up. */
};
#define TEST_AMPLITUDE 0.1f /* -20 dBFS: nothing reaches a converter, but the house rule holds. */

static float s_reverb_mem[kReverbMem] __attribute__((section(".axi_bss")));
static SplitDsp s_local;

static uint32_t load_u32(const uint32_t *p) { return *(const volatile uint32_t *)p; }
static void store_u32(uint32_t *p, uint32_t v) { *(volatile uint32_t *)p = v; }

static void invalidate(const void *p, size_t n) {
    const uintptr_t a = (uintptr_t)p & ~(uintptr_t)31u;
    SCB_InvalidateDCache_by_Addr((void *)a, (int32_t)(n + ((uintptr_t)p - a)));
}
static void clean(const void *p, size_t n) {
    const uintptr_t a = (uintptr_t)p & ~(uintptr_t)31u;
    SCB_CleanDCache_by_Addr((void *)a, (int32_t)(n + ((uintptr_t)p - a)));
}

/* 400 MHz cycles from the start to block n at 48 kHz, 16 frames: n x 133 333.3. */
static uint32_t block_offset(uint32_t n) {
    return (uint32_t)((uint64_t)n * 400000000u * kSplitFrames / 48000u);
}

static void wait_until(uint32_t target) {
    while ((int32_t)(board_cycles() - target) < 0) {
    }
}

/* Waits for the M4 to finish block n - 1 (seq_done >= n). Returns 0 on time, 1 if it had to
 * wait, -1 if it gave up. */
static int wait_done(SplitFromM4 *from, uint32_t n, uint32_t give_up_at) {
    invalidate(&from->seq_done, sizeof(uint32_t));
    if (load_u32(&from->seq_done) >= n) {
        return 0;
    }
    while (load_u32(&from->seq_done) < n) {
        if ((int32_t)(board_cycles() - give_up_at) >= 0) {
            return -1;
        }
        invalidate(&from->seq_done, sizeof(uint32_t));
    }
    return 1;
}

static int wake_m4(void) {
    volatile Mailbox *mb = MAILBOX;
    mb->magic = MAILBOX_MAGIC;
    mb->state = kMailboxIdle;
    mb->count = 0u;
    mb->command = kMailboxCmdSplit;
    SCB_CleanDCache_by_Addr((void *)MAILBOX_ADDR, (int32_t)sizeof(Mailbox));
    __HAL_RCC_HSEM_CLK_ENABLE();
    (void)HAL_HSEM_FastTake(MAILBOX_HSEM_WAKE_CM4);
    HAL_HSEM_Release(MAILBOX_HSEM_WAKE_CM4, 0u);
    const uint32_t start = HAL_GetTick();
    while (HAL_GetTick() - start < 2000u) {
        SCB_InvalidateDCache_by_Addr((void *)MAILBOX_ADDR, (int32_t)sizeof(Mailbox));
        if (mb->state == kMailboxRunning) {
            return 0;
        }
        if (mb->state == kMailboxDone) {
            return -1; /* It refused (its reverb memory was short). */
        }
    }
    return -1;
}

static int wait_m4_parked(void) {
    volatile Mailbox *mb = MAILBOX;
    const uint32_t start = HAL_GetTick();
    while (HAL_GetTick() - start < 2000u) {
        SCB_InvalidateDCache_by_Addr((void *)MAILBOX_ADDR, (int32_t)sizeof(Mailbox));
        if (mb->state == kMailboxDone) {
            return 0;
        }
    }
    return -1;
}

void bench_split(uint32_t blocks) {
    SplitShared *sh = SPLIT;
    SplitToM4 *to = &sh->to_m4;
    SplitFromM4 *from = &sh->from_m4;
    static SplitIn gen_in;
    static SplitOut local_out, rx;

    if (split_dsp_init(&s_local, s_reverb_mem, kReverbMem) != 0) {
        printf("splitbench error local reverb memory\r\nsplitbench done\r\n");
        return;
    }
    DspNoise noise[kSignals];
    for (uint32_t c = 0; c < kSignals; ++c) {
        dsp_noise_seed(&noise[c], 101u + c);
    }
    store_u32(&to->seq_in, 0u);
    store_u32(&to->stop, 0u);
    clean(to, sizeof(*to));
    invalidate(from, sizeof(*from));
    if (wake_m4() != 0) {
        printf("splitbench error the M4 did not start\r\nsplitbench done\r\n");
        return;
    }

    uint32_t late = 0u, rx_crc = 0u, xfer_max = 0u, local_max = 0u;
    uint64_t xfer_sum = 0u, local_sum = 0u;
    int failed = 0;
    const uint32_t start = board_cycles() + 400000u; /* First block 1 ms from now. */
    for (uint32_t n = 0; n <= blocks && !failed; ++n) {
        wait_until(start + block_offset(n));
        uint32_t xfer = 0u;
        if (n > 0u) {
            /* The return of block n - 1, one block late by design. */
            const int w = wait_done(from, n, start + block_offset(n + kLateLimitBlocks));
            if (w < 0) {
                failed = 1;
                break;
            }
            late += (uint32_t)w;
            const uint32_t t0 = board_cycles();
            const SplitOut *src = &from->out[(n - 1u) & 1u];
            invalidate(src, sizeof(*src));
            memcpy(&rx, src, sizeof(rx));
            xfer += board_cycles() - t0;
            rx_crc = dsp_crc32(rx_crc, &rx, sizeof(rx));
        }
        if (n == blocks) {
            break;
        }
        /* Block n's signals: noise at -20 dBFS, its own generator per signal. */
        for (uint32_t c = 0; c < 2u; ++c) {
            dsp_noise_f32(&noise[c], gen_in.send[c], kSplitFrames, TEST_AMPLITUDE);
        }
        for (uint32_t c = 0; c < kSplitTaps; ++c) {
            dsp_noise_f32(&noise[2u + c], gen_in.tap[c], kSplitFrames, TEST_AMPLITUDE);
        }
        const uint32_t t1 = board_cycles();
        SplitIn *dst = &to->in[n & 1u];
        memcpy(dst, &gen_in, sizeof(*dst));
        clean(dst, sizeof(*dst));
        __DMB();
        store_u32(&to->seq_in, n + 1u);
        clean(&to->seq_in, sizeof(uint32_t));
        xfer += board_cycles() - t1;
        xfer_max = xfer > xfer_max ? xfer : xfer_max;
        xfer_sum += xfer;
        /* The same block on this core: what the M7 no longer has to do, and the reference. */
        const uint32_t t2 = board_cycles();
        (void)split_dsp_block(&s_local, &gen_in, &local_out);
        const uint32_t local = board_cycles() - t2;
        local_max = local > local_max ? local : local_max;
        local_sum += local;
    }
    store_u32(&to->stop, 1u);
    clean(&to->stop, sizeof(uint32_t));
    if (failed || wait_m4_parked() != 0) {
        printf("splitbench error the M4 stopped answering (late=%lu)\r\nsplitbench done\r\n",
               (unsigned long)late);
        return;
    }
    invalidate(from, sizeof(*from));
    const uint64_t busy_sum = ((uint64_t)from->busy_sum_hi << 32) | from->busy_sum_lo;
    const uint32_t busy_mean = (uint32_t)(busy_sum / blocks);
    /* Load in percent of the block: the M4 has 66 666.7 cycles per block. */
    printf("splitbench blocks=%lu seconds=%lu late=%lu\r\n", (unsigned long)blocks,
           (unsigned long)(blocks / 3000u), (unsigned long)late);
    printf("splitbench m4_cycles_per_frame mean=%lu max=%lu load_pct mean=%lu max=%lu\r\n",
           (unsigned long)(busy_mean / kSplitFrames),
           (unsigned long)(from->busy_max / kSplitFrames),
           (unsigned long)((uint64_t)busy_mean * 300u / 200000u),
           (unsigned long)((uint64_t)from->busy_max * 300u / 200000u));
    printf("splitbench m4_cycles_per_frame max_without_meter_read=%lu load_pct=%lu\r\n",
           (unsigned long)(from->busy_max_plain / kSplitFrames),
           (unsigned long)((uint64_t)from->busy_max_plain * 300u / 200000u));
    printf("splitbench m7_saved_cycles_per_frame mean=%lu max=%lu\r\n",
           (unsigned long)(local_sum / blocks / kSplitFrames),
           (unsigned long)(local_max / kSplitFrames));
    printf("splitbench m7_exchange_cycles_per_frame mean=%lu max=%lu\r\n",
           (unsigned long)(xfer_sum / blocks / kSplitFrames),
           (unsigned long)(xfer_max / kSplitFrames));
    const int audio_ok = from->out_crc == s_local.out_crc && rx_crc == s_local.out_crc;
    const int meters_ok = from->reading_crc == s_local.reading_crc;
    printf("splitbench return=%s (m4 %08lx, received %08lx, m7 %08lx) meters=%s (m4 %08lx, m7 "
           "%08lx)\r\n",
           audio_ok ? "identical" : "differs", (unsigned long)from->out_crc,
           (unsigned long)rx_crc, (unsigned long)s_local.out_crc,
           meters_ok ? "identical" : "differs", (unsigned long)from->reading_crc,
           (unsigned long)s_local.reading_crc);
    /* The reader's half: the M4's newest mix snapshot converted to dB here. */
    DspMeterReading r;
    dsp_meter_raw_to_reading(&from->raw[0], &r);
    printf("splitbench mix_meter peak_db=%d true_peak_db=%d momentary_lufs=%d (tenths)\r\n",
           (int)(r.peak_db[0] * 10.0f), (int)(r.true_peak_db[0] * 10.0f),
           (int)(r.momentary_lufs * 10.0f));
    printf("splitbench done\r\n");
}
