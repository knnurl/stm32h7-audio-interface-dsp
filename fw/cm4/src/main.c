/* The Cortex-M4. It puts its domain (D2) into stop mode and waits there for the Cortex-M7 to
 * release hardware semaphore 0. No option bytes are involved: both cores boot, and this one
 * goes to sleep at once, so it never runs while the M7 changes the clocks.
 *
 * Woken, it looks at the mailbox in SRAM4 (fw/common/mailbox.h). The one job so far (2026-11-18,
 * the budget work of batch 8c): run every DSP self-test case, time its processing with this
 * core's cycle counter, and report the cycles and an output checksum, so the PC can tell whether
 * the M4's results are bit-identical and the budget can tell what the M4 could carry. Then it
 * parks again. The second job (8c split, 2026-11-18): run the reverb and the meters on the
 * blocks the M7 posts (split.h) until the M7 says stop; `splitbench` on the M7 drives it.
 *
 * The sleep sequence is ST's (the NUCLEO-H745ZI-Q BootCM4_CM7 template). While this core sleeps,
 * the D2 peripherals the M7 has enabled keep running (checked on the board: the M7's console on
 * USART3, a D2 peripheral, works with this core parked).
 */
#include "stm32h7xx_hal.h"

#include "dsp/dsp_crc32.h"
#include "dsp/dsp_selftest.h"
#include "mailbox.h"
#include "split.h"
#include "split_dsp.h"

enum { kRuns = 5 };

static uint32_t s_in[kDspSelftestFrames];
static uint32_t s_out[kDspSelftestFrames];
static volatile uint32_t s_mark;

static void mark_now(void) { s_mark = DWT->CYCCNT; }

static void bench(void) {
    volatile Mailbox *mb = MAILBOX;
    mb->state = kMailboxRunning;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0u;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    dsp_selftest_set_mark(mark_now);
    size_t count = dsp_selftest_count();
    if (count > kMailboxMaxCases) {
        count = kMailboxMaxCases;
    }
    for (size_t index = 0; index < count; ++index) {
        dsp_selftest_input(index, s_in);
        uint32_t best = 0xFFFFFFFFu;
        for (int run = 0; run < kRuns; ++run) {
            const uint32_t start = DWT->CYCCNT;
            s_mark = start;
            dsp_selftest_run(index, s_in, s_out);
            const uint32_t proc = DWT->CYCCNT - s_mark;
            best = proc < best ? proc : best;
        }
        mb->entry[index].proc_min = best;
        mb->entry[index].crc = dsp_crc32(0u, s_out, sizeof(s_out));
        mb->entry[index].channels = (uint32_t)dsp_selftest_channels(index);
    }
    dsp_selftest_set_mark(NULL);
    mb->count = (uint32_t)count;
    mb->runs = kRuns;
    mb->command = kMailboxCmdNone;
    __DSB();
    mb->state = kMailboxDone;
    __DSB();
}

enum { kReverbMem = 17888 }; /* dsp_reverb_f32_mem_needed(48000). */
static float s_reverb_mem[kReverbMem];
static SplitDsp s_split;

static uint32_t load_u32(const uint32_t *p) { return *(const volatile uint32_t *)p; }
static void store_u32(uint32_t *p, uint32_t v) { *(volatile uint32_t *)p = v; }

/* The 8c split (split.h): process each block the M7 posts until it says stop. Polls SRAM4. */
static void split_serve(void) {
    volatile Mailbox *mb = MAILBOX;
    SplitShared *sh = SPLIT;
    SplitFromM4 *from = &sh->from_m4;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    if (split_dsp_init(&s_split, s_reverb_mem, kReverbMem) != 0) {
        mb->command = kMailboxCmdNone;
        mb->state = kMailboxDone;
        return;
    }
    uint32_t done = 0u, busy_max = 0u, busy_max_plain = 0u, reading_seq = 0u;
    uint64_t busy_sum = 0u;
    store_u32(&from->seq_done, 0u);
    store_u32(&from->reading_seq, 0u);
    __DSB();
    mb->state = kMailboxRunning;
    __DSB();
    for (;;) {
        uint32_t posted;
        while ((posted = load_u32(&sh->to_m4.seq_in)) == done && load_u32(&sh->to_m4.stop) == 0u) {
        }
        if (posted == done) {
            break; /* Stopped, with every posted block done. */
        }
        __DMB(); /* The block's signals are read after its sequence number. */
        const uint32_t slot = done & 1u;
        const uint32_t start = DWT->CYCCNT;
        const int32_t read = split_dsp_block(&s_split, &sh->to_m4.in[slot], &from->out[slot]);
        if (read) {
            store_u32(&from->reading_seq, ++reading_seq); /* Odd: being written. */
            __DMB();
            for (int32_t m = 0; m < kSplitMeters; ++m) {
                from->raw[m] = s_split.raw[m];
            }
            __DMB();
            store_u32(&from->reading_seq, ++reading_seq);
        }
        const uint32_t busy = DWT->CYCCNT - start;
        busy_max = busy > busy_max ? busy : busy_max;
        if (!read && busy > busy_max_plain) {
            busy_max_plain = busy;
        }
        busy_sum += busy;
        ++done;
        __DMB(); /* The return is written before the sequence number says so. */
        store_u32(&from->seq_done, done);
    }
    from->busy_max = busy_max;
    from->busy_max_plain = busy_max_plain;
    from->busy_sum_lo = (uint32_t)busy_sum;
    from->busy_sum_hi = (uint32_t)(busy_sum >> 32);
    from->out_crc = s_split.out_crc;
    from->reading_crc = s_split.reading_crc;
    mb->command = kMailboxCmdNone;
    __DSB();
    mb->state = kMailboxDone;
    __DSB();
}

int main(void) {
    __HAL_RCC_HSEM_CLK_ENABLE();
    HAL_HSEM_ActivateNotification(__HAL_HSEM_SEMID_TO_MASK(MAILBOX_HSEM_WAKE_CM4));
    for (;;) {
        HAL_PWREx_ClearPendingEvent();
        HAL_PWREx_EnterSTOPMode(PWR_MAINREGULATOR_ON, PWR_STOPENTRY_WFE, PWR_D2_DOMAIN);
        __HAL_HSEM_CLEAR_FLAG(__HAL_HSEM_SEMID_TO_MASK(MAILBOX_HSEM_WAKE_CM4));
        if (MAILBOX->magic == MAILBOX_MAGIC && MAILBOX->command == kMailboxCmdBench) {
            bench();
        } else if (MAILBOX->magic == MAILBOX_MAGIC && MAILBOX->command == kMailboxCmdSplit) {
            split_serve();
        }
    }
}
