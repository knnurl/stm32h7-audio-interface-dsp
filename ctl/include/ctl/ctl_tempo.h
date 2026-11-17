/* The tempo follower (batch 8b.5, docs/notes/tempo.md).
 *
 * Sources: MIDI clock (24 ticks per quarter note) and the stored tempo (parameter tempo_bpm),
 * which tap tempo sets. In auto mode MIDI clock wins while it is present: at least 3 ticks, the
 * last within 0.5 s.
 *
 * MIDI clock estimate: a least-squares line through the tick times, over up to 96 ticks (four
 * beats), so the 1 ms jitter of USB MIDI moves it by well under 0.1 BPM. A second fit over the
 * last 24 ticks watches for a real change: when the two differ by more than 0.6 %, the history
 * restarts from the last 4 ticks, so a new tempo is followed within a beat. Until the fresh fit
 * has 16 ticks, the one-beat fit is reported instead (smoother than a fit over a few jittered
 * ticks). On a ramp the estimate lags: a line through the window reports its centre.
 *
 * Tap: the average interval of the last four intervals (fewer at first); a gap over 2 s starts
 * again. Each tap sets tempo_bpm, so the tapped tempo is stored like one typed on the PC.
 *
 * Times are microseconds from any free-running 32-bit counter (wrap-safe). Main loop only.
 */
#ifndef CTL_TEMPO_H
#define CTL_TEMPO_H

#include "ctl/ctl_core.h"

#include <stdint.h>

#define CTL_TEMPO_HISTORY 96
#define CTL_TEMPO_SHORT 24
#define CTL_TEMPO_LOST_US 500000u
#define CTL_TEMPO_TAP_RESET_US 2000000u

typedef enum {
    kCtlTempoStored = 0,
    kCtlTempoMidi = 1,
} CtlTempoSource;

typedef struct {
    /* MIDI clock. */
    uint32_t tick_us[CTL_TEMPO_HISTORY]; /* Ring of tick times. */
    uint32_t tick_head;
    uint32_t tick_count; /* Ticks in the current fit. */
    uint32_t valid;      /* Ticks in the ring since the last dropout. */
    uint8_t settling;    /* After a restart, until the fresh fit has enough ticks. */
    uint32_t last_tick_us;
    uint8_t have_tick;
    double period_us; /* Current estimate of one tick; 0 when none. */
    uint32_t restarts;
    /* Transport and position. */
    uint8_t running;
    uint32_t ticks_since_start;
    /* Tap. */
    uint32_t tap_us[5];
    uint32_t tap_count;
    uint32_t taps_seen; /* CtlCore.taps already handled. */
    /* Output. */
    float bpm;
    CtlTempoSource source;
} CtlTempo;

void ctl_tempo_init(CtlTempo *t);
/* A real-time MIDI byte (0xF8 clock, 0xFA start, 0xFB continue, 0xFC stop). Matches
 * CtlMidiRealtimeFn with ctx = the CtlTempo. */
void ctl_tempo_midi(void *tempo, uint8_t byte, uint32_t now_us);
/* A tap at now_us; returns the tapped tempo, or 0 when it needs another tap. */
float ctl_tempo_tap(CtlTempo *t, uint32_t now_us);
/* Main loop: handles new taps counted in `core`, drops a lost clock, chooses the source,
 * writes tempo_bpm (taps) and the tempo_now_bpm meter. */
void ctl_tempo_update(CtlTempo *t, CtlCore *core, uint32_t now_us);
/* Position within the beat, 0 to 1, from MIDI clock while running; -1 without it. */
float ctl_tempo_beat_phase(const CtlTempo *t, uint32_t now_us);

#endif
