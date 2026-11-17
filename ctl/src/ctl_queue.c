#include "ctl/ctl_queue.h"

void ctl_queue_init(CtlQueue *q) {
    for (uint32_t i = 0; i < CTL_MAX_PARAMS; ++i) {
        q->latest[i] = 0.0f;
        q->pending[i] = 0u;
    }
    for (uint32_t i = 0; i < CTL_QUEUE_CAPACITY; ++i) {
        q->ring[i] = 0u;
    }
    q->head = 0u;
    q->tail = 0u;
    q->pushes = 0u;
    q->coalesced = 0u;
}

void ctl_queue_push(CtlQueue *q, uint16_t index, float value) {
    if (index >= CTL_MAX_PARAMS) {
        return;
    }
    ++q->pushes;
    q->latest[index] = value;
    CTL_FENCE();
    if (q->pending[index] != 0u) {
        ++q->coalesced; /* The consumer will read the value just stored. */
        return;
    }
    q->pending[index] = 1u;
    const uint32_t head = q->head;
    q->ring[head] = index;
    CTL_FENCE();
    q->head = (head + 1u) % CTL_QUEUE_CAPACITY;
}

size_t ctl_queue_pop(CtlQueue *q, CtlUpdate *out, size_t max) {
    size_t n = 0;
    uint32_t tail = q->tail;
    while (n < max && tail != q->head) {
        CTL_FENCE();
        const uint16_t index = q->ring[tail];
        tail = (tail + 1u) % CTL_QUEUE_CAPACITY;
        q->tail = tail; /* The slot is free before the index can be pushed again. */
        q->pending[index] = 0u;
        CTL_FENCE();
        out[n].index = index;
        out[n].value = q->latest[index];
        ++n;
    }
    return n;
}

uint32_t ctl_queue_waiting(const CtlQueue *q) {
    return (q->head + CTL_QUEUE_CAPACITY - q->tail) % CTL_QUEUE_CAPACITY;
}
