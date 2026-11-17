/* The hand-off of parameter values from the control level (main loop) to the audio level (the
 * audio interrupt): one producer, one consumer, no locks (docs/notes/ctl_registry.md).
 *
 * Each parameter has a latest-value slot and a pending flag; the ring carries the indices of
 * parameters with a new value. An index is in the ring at most once, so the ring (capacity
 * CTL_MAX_PARAMS + 1) can never be full: on a burst of writes the newest value of each
 * parameter wins and nothing blocks or is dropped. The consumer drains at most `max` entries
 * per call, so its time per block is bounded.
 *
 * Ordering: the producer stores the value, then reads the flag; the consumer clears the flag,
 * then reads the value. Both need a full fence between the two (CTL_FENCE). On the M7, producer
 * and consumer share one core, so the fence costs little; it is there for batch 11, when the
 * producer moves to the M4.
 */
#ifndef CTL_QUEUE_H
#define CTL_QUEUE_H

#include "ctl/ctl_params.h"

#include <stddef.h>
#include <stdint.h>

#if defined(_MSC_VER)
#include <intrin.h>
#define CTL_FENCE()                                                                                \
    do {                                                                                           \
        _ReadWriteBarrier();                                                                       \
        __faststorefence();                                                                        \
        _ReadWriteBarrier();                                                                       \
    } while (0)
#else
#define CTL_FENCE() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#endif

#define CTL_QUEUE_CAPACITY (CTL_MAX_PARAMS + 1)

typedef struct {
    uint16_t index;
    float value;
} CtlUpdate;

typedef struct {
    volatile float latest[CTL_MAX_PARAMS];
    volatile uint8_t pending[CTL_MAX_PARAMS];
    volatile uint16_t ring[CTL_QUEUE_CAPACITY];
    volatile uint32_t head; /* Written by the producer only. */
    volatile uint32_t tail; /* Written by the consumer only. */
    uint32_t pushes;        /* Producer's counters, for `stat`. */
    uint32_t coalesced;     /* Pushes that replaced a value not yet taken. */
} CtlQueue;

void ctl_queue_init(CtlQueue *q);
/* Producer. Index must be below CTL_MAX_PARAMS (ignored otherwise). */
void ctl_queue_push(CtlQueue *q, uint16_t index, float value);
/* Consumer. Takes up to `max` updates; returns how many. */
size_t ctl_queue_pop(CtlQueue *q, CtlUpdate *out, size_t max);
/* Entries waiting, from either side's view (a snapshot). */
uint32_t ctl_queue_waiting(const CtlQueue *q);

#endif
