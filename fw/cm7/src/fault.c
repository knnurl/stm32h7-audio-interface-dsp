#include "fault.h"

#include "stm32h7xx_hal.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#define FAULT_MAGIC 0x46415531u /* "FAU1" */

typedef struct {
    uint32_t magic;
    uint32_t count;   /* Faults since power-on. */
    uint32_t pending; /* Not yet printed at a start. */
    uint32_t exception;
    uint32_t pc;
    uint32_t lr;
    uint32_t psr;
    uint32_t cfsr;
    uint32_t hfsr;
    uint32_t mmfar;
    uint32_t bfar;
    uint32_t uptime_ms;
    uint32_t check; /* Of the fields above: RAM holds noise after a power cycle. */
} FaultRecord;

static FaultRecord s_fault __attribute__((section(".noinit")));

static uint32_t checksum(const FaultRecord *record) {
    const uint32_t *words = (const uint32_t *)record;
    uint32_t sum = 0x5A5AA5A5u;
    for (size_t i = 0; i < offsetof(FaultRecord, check) / 4u; ++i) {
        sum = ((sum << 5) | (sum >> 27)) ^ words[i];
    }
    return sum;
}

static bool valid(void) {
    return s_fault.magic == FAULT_MAGIC && s_fault.check == checksum(&s_fault);
}

/* From the handlers' assembly (interrupts.c), with the frame the core stacked on entry: r0, r1,
 * r2, r3, r12, lr, pc, xpsr. */
void fault_capture(const uint32_t *frame) __attribute__((used, noreturn));
void fault_capture(const uint32_t *frame) {
    if (!valid()) {
        memset(&s_fault, 0, sizeof(s_fault));
        s_fault.magic = FAULT_MAGIC;
    }
    ++s_fault.count;
    s_fault.pending = 1u;
    s_fault.exception = __get_IPSR() & 0x1FFu;
    s_fault.lr = frame[5];
    s_fault.pc = frame[6];
    s_fault.psr = frame[7];
    s_fault.cfsr = SCB->CFSR;
    s_fault.hfsr = SCB->HFSR;
    s_fault.mmfar = SCB->MMFAR;
    s_fault.bfar = SCB->BFAR;
    s_fault.uptime_ms = HAL_GetTick();
    s_fault.check = checksum(&s_fault);
    __DSB();
    NVIC_SystemReset();
    for (;;) {
    }
}

static const char *exception_name(uint32_t exception) {
    switch (exception) {
    case 2u:
        return "NMI";
    case 3u:
        return "HardFault";
    case 4u:
        return "MemManage";
    case 5u:
        return "BusFault";
    case 6u:
        return "UsageFault";
    default:
        return "exception";
    }
}

size_t fault_describe(char *out, size_t capacity) {
    int n;
    if (!valid() || s_fault.count == 0u) {
        n = snprintf(out, capacity, "fault none");
    } else {
        n = snprintf(out, capacity,
                     "fault %lu since power-on; the last: %s (%lu) %lu ms after its start, pc "
                     "0x%08lx lr 0x%08lx psr 0x%08lx cfsr 0x%08lx hfsr 0x%08lx mmfar 0x%08lx bfar "
                     "0x%08lx",
                     (unsigned long)s_fault.count, exception_name(s_fault.exception),
                     (unsigned long)s_fault.exception, (unsigned long)s_fault.uptime_ms,
                     (unsigned long)s_fault.pc, (unsigned long)s_fault.lr,
                     (unsigned long)s_fault.psr, (unsigned long)s_fault.cfsr,
                     (unsigned long)s_fault.hfsr, (unsigned long)s_fault.mmfar,
                     (unsigned long)s_fault.bfar);
    }
    if (n < 0 || capacity == 0u) {
        return 0;
    }
    return (size_t)n < capacity ? (size_t)n : capacity - 1u;
}

void fault_report_boot(void) {
    if (!valid()) {
        memset(&s_fault, 0, sizeof(s_fault)); /* A power cycle: noise. */
        return;
    }
    if (s_fault.pending != 0u) {
        char text[260];
        fault_describe(text, sizeof(text));
        printf("previous reset: %s\r\n", text);
        s_fault.pending = 0u;
        s_fault.check = checksum(&s_fault);
    }
}
