/* The mailbox between the two cores, at the start of SRAM4 (D3, reachable by both; SPEC 6.2).
 * Batch 8c budget work (2026-11-18): the M7 asks the M4 to run the DSP self-test cases and report
 * their cycles, to measure what could move to the M4.
 *
 * Protocol: the M7 writes `command` (and cleans its D-cache over the mailbox), then releases
 * hardware semaphore 0, which wakes the M4 from stop mode. The M4 sets `state` to running, does
 * the work, fills the entries, sets `state` to done and parks again. The M4 has no data cache;
 * the M7 invalidates its own before each read.
 */
#ifndef MAILBOX_H
#define MAILBOX_H

#include <stdint.h>

#define MAILBOX_ADDR 0x38000000u
#define MAILBOX_MAGIC 0x4D344231u /* "M4B1" */
#define MAILBOX_HSEM_WAKE_CM4 0u

enum { kMailboxMaxCases = 64 };

typedef enum {
    kMailboxCmdNone = 0,
    kMailboxCmdBench = 1,
} MailboxCommand;

typedef enum {
    kMailboxIdle = 0,
    kMailboxRunning = 1,
    kMailboxDone = 2,
} MailboxState;

typedef struct {
    uint32_t proc_min; /* M4 cycles for the case's processing (set-up excluded), best of runs. */
    uint32_t crc;      /* CRC-32 of the case's output. */
    uint32_t channels;
} MailboxEntry;

typedef struct {
    uint32_t magic;
    uint32_t command; /* MailboxCommand, written by the M7. */
    uint32_t state;   /* MailboxState, written by the M4. */
    uint32_t count;
    uint32_t runs;
    MailboxEntry entry[kMailboxMaxCases];
} Mailbox;

#define MAILBOX ((volatile Mailbox *)MAILBOX_ADDR)

#endif
