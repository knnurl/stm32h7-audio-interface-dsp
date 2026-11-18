/* The Cortex-M4. It puts its domain (D2) into stop mode and waits there for the Cortex-M7 to
 * release hardware semaphore 0. No option bytes are involved: both cores boot, and this one
 * goes to sleep at once, so it never runs while the M7 changes the clocks.
 *
 * Woken, it looks at the mailbox in SRAM4 (fw/common/mailbox.h). The one job so far (2026-11-18,
 * the budget work of batch 8c): run every DSP self-test case, time its processing with this
 * core's cycle counter, and report the cycles and an output checksum, so the PC can tell whether
 * the M4's results are bit-identical and the budget can tell what the M4 could carry. Then it
 * parks again.
 *
 * The sleep sequence is ST's (the NUCLEO-H745ZI-Q BootCM4_CM7 template). While this core sleeps,
 * the D2 peripherals the M7 has enabled keep running (checked on the board: the M7's console on
 * USART3, a D2 peripheral, works with this core parked).
 */
#include "stm32h7xx_hal.h"

#include "dsp/dsp_crc32.h"
#include "dsp/dsp_selftest.h"
#include "mailbox.h"

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

int main(void) {
    __HAL_RCC_HSEM_CLK_ENABLE();
    HAL_HSEM_ActivateNotification(__HAL_HSEM_SEMID_TO_MASK(MAILBOX_HSEM_WAKE_CM4));
    for (;;) {
        HAL_PWREx_ClearPendingEvent();
        HAL_PWREx_EnterSTOPMode(PWR_MAINREGULATOR_ON, PWR_STOPENTRY_WFE, PWR_D2_DOMAIN);
        __HAL_HSEM_CLEAR_FLAG(__HAL_HSEM_SEMID_TO_MASK(MAILBOX_HSEM_WAKE_CM4));
        if (MAILBOX->magic == MAILBOX_MAGIC && MAILBOX->command == kMailboxCmdBench) {
            bench();
        }
    }
}
