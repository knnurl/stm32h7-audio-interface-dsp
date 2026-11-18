#include "ctl/ctl_core.h"

#include <math.h>
#include <string.h>

#define PENDING_CAPACITY (CTL_MAX_PARAMS + 1)

static void pending_init(CtlPending *p) { memset(p, 0, sizeof(*p)); }

static void pending_add(CtlPending *p, uint16_t index) {
    if (index >= CTL_MAX_PARAMS || p->in[index] != 0u) {
        return; /* Already waiting: it is reported with its value at that time. */
    }
    p->in[index] = 1u;
    p->ring[p->head] = index;
    p->head = (p->head + 1u) % PENDING_CAPACITY;
}

static int pending_take(CtlPending *p, uint16_t *index) {
    if (p->tail == p->head) {
        return 0;
    }
    *index = p->ring[p->tail];
    p->tail = (p->tail + 1u) % PENDING_CAPACITY;
    p->in[*index] = 0u;
    return 1;
}

void ctl_core_init(CtlCore *core) {
    memset(core, 0, sizeof(*core));
    ctl_queue_init(&core->to_audio);
    pending_init(&core->notify);
    pending_init(&core->midi_out);
    const size_t n = ctl_param_count();
    for (size_t i = 0; i < n; ++i) {
        core->value[i] = ctl_param_desc(i)->def;
    }
}

void ctl_core_sync_audio(CtlCore *core) {
    const size_t n = ctl_param_count();
    for (size_t i = 0; i < n; ++i) {
        ctl_queue_push(&core->to_audio, (uint16_t)i, core->value[i]);
    }
}

void ctl_core_set_time(CtlCore *core, uint32_t now_ms) { core->now_ms = now_ms; }

float ctl_core_get(const CtlCore *core, size_t index) {
    return index < ctl_param_count() ? core->value[index] : 0.0f;
}

int ctl_core_mode(const CtlCore *core, size_t index) {
    const int32_t m = ctl_param_mode_index(index);
    return m < 0 ? -1 : (core->value[m] >= 0.5f ? 1 : 0);
}

int ctl_core_knob_attached(const CtlCore *core, size_t index) {
    return index < ctl_param_count() ? core->knob_attached[index] : 0;
}

void ctl_core_tap(CtlCore *core) { ++core->taps; }

int ctl_core_take_notify(CtlCore *core, uint16_t *index) {
    return pending_take(&core->notify, index);
}

int ctl_core_take_midi(CtlCore *core, uint16_t *index) {
    return pending_take(&core->midi_out, index);
}

static void apply(CtlCore *core, size_t index, float v, CtlSource src);

/* A mode parameter changed: a knob switched to knob wins takes over at once. */
static void mode_changed(CtlCore *core, size_t mode_index) {
    const size_t n = ctl_param_count();
    for (size_t k = 0; k < n; ++k) {
        if (ctl_param_mode_index(k) != (int32_t)mode_index) {
            continue;
        }
        if (ctl_core_mode(core, k) == 0 && core->knob_known[k] != 0u) {
            core->knob_attached[k] = 1u;
            core->knob_locked[k] = 0u;
            apply(core, k, ctl_param_from_norm(ctl_param_desc(k), core->knob_pos[k]),
                  kCtlSrcKnob);
        }
        return;
    }
}

static int is_mode_param(size_t index) {
    const uint16_t id = ctl_param_desc(index)->id;
    return id >= CTL_ID_MODE_FIRST && id <= CTL_ID_MODE_LAST;
}

static void apply(CtlCore *core, size_t index, float v, CtlSource src) {
    const CtlParamDesc *d = ctl_param_desc(index);
    const float old = core->value[index];
    core->value[index] = v;
    if (v == old) {
        return;
    }
    ctl_queue_push(&core->to_audio, (uint16_t)index, v);
    if ((d->flags & (kCtlFlagPreset | kCtlFlagSetting)) != 0u) {
        core->settings_dirty = 1u;
        core->last_change_ms = core->now_ms;
    }
    if (src != kCtlSrcPc && (d->flags & kCtlFlagReadOnly) == 0u) {
        pending_add(&core->notify, (uint16_t)index);
    }
    if (src == kCtlSrcKnob || src == kCtlSrcButton) {
        pending_add(&core->midi_out, (uint16_t)index);
    }
    if (is_mode_param(index)) {
        mode_changed(core, index);
    }
}

static float value_of(const CtlCore *core, const char *name, size_t len) {
    const int32_t i = ctl_param_find(name, len);
    return i < 0 ? 0.0f : core->value[i];
}

/* 1 if writing v to `index` would run the effect slot and a strip's saturation together. */
static int budget_conflict(const CtlCore *core, size_t index, float v) {
    const uint16_t id = ctl_param_desc(index)->id;
    switch (id) {
    case 150u: /* in1_sat_on */
    case 250u: /* in2_sat_on */
        return v >= 0.5f && value_of(core, "fx_on", 5u) >= 0.5f;
    case 401u: /* fx_on */
        return v >= 0.5f && (value_of(core, "in1_sat_on", 10u) >= 0.5f ||
                             value_of(core, "in2_sat_on", 10u) >= 0.5f);
    default:
        return 0;
    }
}

CtlResult ctl_core_set(CtlCore *core, size_t index, float value, CtlSource src, float *applied) {
    const CtlParamDesc *d = ctl_param_desc(index);
    if (d == NULL) {
        return kCtlErrUnknownParam;
    }
    if ((d->flags & kCtlFlagReadOnly) != 0u && src != kCtlSrcDevice) {
        return kCtlErrReadOnly;
    }
    if ((d->flags & kCtlFlagKnob) != 0u && src != kCtlSrcKnob) {
        if (ctl_core_mode(core, index) == 0 && src != kCtlSrcDevice) {
            ++core->refused;
            if (applied != NULL) {
                *applied = core->value[index];
            }
            return kCtlErrKnobWins;
        }
        core->knob_attached[index] = 0u;
        core->knob_locked[index] = 0u;
    }
    const float v = ctl_param_clamp(d, value);
    if (budget_conflict(core, index, v)) {
        ++core->refused;
        if (applied != NULL) {
            *applied = core->value[index];
        }
        return kCtlErrBudget;
    }
    apply(core, index, v, src);
    if (applied != NULL) {
        *applied = v;
    }
    return kCtlOk;
}

CtlResult ctl_core_knob(CtlCore *core, size_t index, float position) {
    const CtlParamDesc *d = ctl_param_desc(index);
    if (d == NULL) {
        return kCtlErrUnknownParam;
    }
    if ((d->flags & kCtlFlagKnob) == 0u) {
        return kCtlErrNotKnob;
    }
    if (isnan(position)) {
        return kCtlErrBadValue;
    }
    const float x = position < 0.0f ? 0.0f : (position > 1.0f ? 1.0f : position);
    const float prev = core->knob_pos[index];
    const int known = core->knob_known[index] != 0u;
    core->knob_pos[index] = x;
    core->knob_known[index] = 1u;

    if (ctl_core_mode(core, index) == 0) {
        core->knob_attached[index] = 1u;
        core->knob_locked[index] = 0u;
        apply(core, index, ctl_param_from_norm(d, x), kCtlSrcKnob);
        return kCtlOk;
    }
    if (core->knob_attached[index] == 0u) {
        const float t = ctl_param_to_norm(d, core->value[index]);
        const int crossed = known && ((prev <= t && x >= t) || (prev >= t && x <= t));
        const int near = fabsf(x - t) <= CTL_PICKUP_HYSTERESIS;
        if (!crossed && !near) {
            return kCtlOk;
        }
        core->knob_attached[index] = 1u;
        if (near) {
            core->knob_locked[index] = 1u;
            core->knob_anchor[index] = t;
            return kCtlOk;
        }
        core->knob_locked[index] = 0u; /* Crossed in one reading: a fast turn. Follow it. */
    } else if (core->knob_locked[index] != 0u) {
        if (fabsf(x - core->knob_anchor[index]) <= CTL_PICKUP_HYSTERESIS) {
            return kCtlOk;
        }
        core->knob_locked[index] = 0u;
    }
    apply(core, index, ctl_param_from_norm(d, x), kCtlSrcKnob);
    return kCtlOk;
}
