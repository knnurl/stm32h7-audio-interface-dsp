#include "ctl/ctl_tempo.h"

#include <math.h>
#include <string.h>

#define CHANGE_RATIO 0.006 /* Short and long fits further apart than this: a real change. */
#define RESTART_KEEP 4u
#define SETTLE_TICKS 16u /* After a restart, the one-beat fit is reported until this many. */
#define MIN_TICKS 3u

void ctl_tempo_init(CtlTempo *t) {
    memset(t, 0, sizeof(*t));
    t->source = kCtlTempoStored;
}

/* Least-squares slope of the last `n` tick times against their index: one tick's period. */
static double fit_period(const CtlTempo *t, uint32_t n) {
    const uint32_t first = (t->tick_head + CTL_TEMPO_HISTORY - n) % CTL_TEMPO_HISTORY;
    const uint32_t t0 = t->tick_us[first];
    const double mean_i = 0.5 * (double)(n - 1u);
    double mean_y = 0.0;
    for (uint32_t k = 0; k < n; ++k) {
        mean_y += (double)(uint32_t)(t->tick_us[(first + k) % CTL_TEMPO_HISTORY] - t0);
    }
    mean_y /= (double)n;
    double sxy = 0.0, sxx = 0.0;
    for (uint32_t k = 0; k < n; ++k) {
        const double di = (double)k - mean_i;
        const double y = (double)(uint32_t)(t->tick_us[(first + k) % CTL_TEMPO_HISTORY] - t0);
        sxy += di * (y - mean_y);
        sxx += di * di;
    }
    return sxx > 0.0 ? sxy / sxx : 0.0;
}

static void clock_tick(CtlTempo *t, uint32_t now_us) {
    if (t->have_tick && now_us - t->last_tick_us > CTL_TEMPO_LOST_US) {
        t->tick_count = 0; /* After a dropout the old ticks say nothing. */
        t->valid = 0;
        t->settling = 0u;
    }
    t->have_tick = 1u;
    t->last_tick_us = now_us;
    t->tick_us[t->tick_head] = now_us;
    t->tick_head = (t->tick_head + 1u) % CTL_TEMPO_HISTORY;
    if (t->tick_count < CTL_TEMPO_HISTORY) {
        ++t->tick_count;
    }
    if (t->valid < CTL_TEMPO_HISTORY) {
        ++t->valid;
    }
    if (t->running) {
        ++t->ticks_since_start;
    }
    if (t->tick_count < MIN_TICKS) {
        t->period_us = 0.0;
        return;
    }
    if (t->tick_count > CTL_TEMPO_SHORT) {
        const double recent = fit_period(t, CTL_TEMPO_SHORT);
        if (fabs(recent / fit_period(t, t->tick_count) - 1.0) > CHANGE_RATIO) {
            t->tick_count = RESTART_KEEP;
            t->settling = 1u;
            ++t->restarts;
        }
    }
    if (t->settling && t->tick_count >= SETTLE_TICKS) {
        t->settling = 0u;
    }
    /* While settling, a fit over 4 to 15 jittered ticks is noisy (about 1.6 BPM at 4 ticks
     * with 1 ms jitter); the one-beat fit across the change is smoother and already moving. */
    const uint32_t n = t->settling ? (t->valid < CTL_TEMPO_SHORT ? t->valid : CTL_TEMPO_SHORT)
                                   : t->tick_count;
    t->period_us = fit_period(t, n);
}

void ctl_tempo_midi(void *tempo, uint8_t byte, uint32_t now_us) {
    CtlTempo *t = (CtlTempo *)tempo;
    switch (byte) {
    case 0xF8u:
        clock_tick(t, now_us);
        break;
    case 0xFAu: /* Start: from the top. */
        t->running = 1u;
        t->ticks_since_start = 0;
        break;
    case 0xFBu: /* Continue: from where it stopped. */
        t->running = 1u;
        break;
    case 0xFCu:
        t->running = 0u;
        break;
    default:
        break;
    }
}

float ctl_tempo_tap(CtlTempo *t, uint32_t now_us) {
    if (t->tap_count > 0u && now_us - t->tap_us[t->tap_count - 1u] > CTL_TEMPO_TAP_RESET_US) {
        t->tap_count = 0;
    }
    if (t->tap_count == 5u) {
        memmove(t->tap_us, t->tap_us + 1, 4u * sizeof(t->tap_us[0]));
        t->tap_count = 4u;
    }
    t->tap_us[t->tap_count++] = now_us;
    if (t->tap_count < 2u) {
        return 0.0f;
    }
    const uint32_t span = t->tap_us[t->tap_count - 1u] - t->tap_us[0];
    const double interval = (double)span / (double)(t->tap_count - 1u);
    return (float)(60.0e6 / interval);
}

static int32_t index_of(const char *name, size_t len) { return ctl_param_find(name, len); }

void ctl_tempo_update(CtlTempo *t, CtlCore *core, uint32_t now_us) {
    while (t->taps_seen != core->taps) {
        ++t->taps_seen;
        const float bpm = ctl_tempo_tap(t, now_us);
        if (bpm > 0.0f) {
            (void)ctl_core_set(core, (size_t)index_of("tempo_bpm", 9u), bpm, kCtlSrcButton,
                               NULL);
        }
    }
    if (t->have_tick && now_us - t->last_tick_us > CTL_TEMPO_LOST_US) {
        t->have_tick = 0u;
        t->tick_count = 0;
        t->valid = 0;
        t->settling = 0u;
        t->period_us = 0.0;
        t->running = 0u;
    }
    const int mode = (int)ctl_core_get(core, (size_t)index_of("tempo_source", 12u));
    const int midi_ok = t->have_tick && t->period_us > 0.0;
    const float stored = ctl_core_get(core, (size_t)index_of("tempo_bpm", 9u));
    if (midi_ok && mode != 2) {
        double bpm = 60.0e6 / (24.0 * t->period_us);
        bpm = bpm < 20.0 ? 20.0 : (bpm > 300.0 ? 300.0 : bpm);
        t->bpm = (float)bpm;
        t->source = kCtlTempoMidi;
    } else {
        t->bpm = mode == 1 ? 0.0f : stored; /* MIDI only, and no clock: no tempo. */
        t->source = kCtlTempoStored;
    }
    (void)ctl_core_set(core, (size_t)index_of("tempo_now_bpm", 13u), t->bpm, kCtlSrcDevice,
                       NULL);
}

float ctl_tempo_beat_phase(const CtlTempo *t, uint32_t now_us) {
    if (!t->have_tick || t->period_us <= 0.0 || !t->running) {
        return -1.0f;
    }
    /* Asked for at or after the last tick normally; a time just before it (two clocks a
     * microsecond apart) must not wrap into a huge positive difference. */
    const int32_t delta = (int32_t)(now_us - t->last_tick_us);
    double since = delta <= 0 ? 0.0 : (double)delta / t->period_us;
    since = since > 1.0 ? 1.0 : since;
    /* ticks_since_start counts the tick that starts the current position after it arrives; the
     * first tick after Start is position 0. */
    const uint32_t ticks = t->ticks_since_start == 0u ? 0u : t->ticks_since_start - 1u;
    return (float)(fmod((double)(ticks % 24u) + since, 24.0) / 24.0);
}
