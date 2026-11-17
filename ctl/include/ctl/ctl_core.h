/* The control core: the current value of every parameter, who may change it, and what has to be
 * told to whom (the audio level, the PC, MIDI out). Runs in the main loop only; the one link to
 * the audio level is `to_audio` (ctl_queue.h).
 *
 * Knob ownership (SPEC 6.7, docs/notes/knob_pickup.md). Each parameter with a knob has a mode
 * parameter: 0 knob wins, 1 PC wins.
 * - Knob wins: writes from the PC, MIDI or a preset are refused (kCtlErrKnobWins); the knob
 *   sets the value.
 * - PC wins: anything may write. A write from anything but the knob detaches the knob. A
 *   detached knob re-attaches when its position reaches the value: it crosses it between two
 *   readings, or comes within kCtlPickupHysteresis of it. If it attached within the
 *   hysteresis, the value stays put until the knob has moved more than the hysteresis from the
 *   pick-up point, so reading noise near the value changes nothing; after that it follows.
 * - Switching a detached knob to knob wins sets the value from the knob at once.
 */
#ifndef CTL_CORE_H
#define CTL_CORE_H

#include "ctl/ctl_params.h"
#include "ctl/ctl_queue.h"

#include <stddef.h>
#include <stdint.h>

/* Pick-up hysteresis, as a fraction of the knob's travel. */
#define CTL_PICKUP_HYSTERESIS 0.01f

typedef enum {
    kCtlSrcKnob = 0,
    kCtlSrcButton = 1,
    kCtlSrcPc = 2,
    kCtlSrcMidi = 3,
    kCtlSrcPreset = 4,
    kCtlSrcDevice = 5, /* The firmware itself: meters, the tempo follower. */
} CtlSource;

/* Results; the protocol's error codes are these numbers (docs/notes/control_protocol.md). */
typedef enum {
    kCtlOk = 0,
    kCtlErrSyntax = 1,
    kCtlErrUnknownCommand = 2,
    kCtlErrUnknownParam = 3,
    kCtlErrBadValue = 4,
    kCtlErrKnobWins = 5,
    kCtlErrReadOnly = 6,
    kCtlErrPreset = 7,
    kCtlErrTooLong = 8,
    kCtlErrNotKnob = 9,
} CtlResult;

/* A set of parameter indices waiting to be reported, in first-changed order, each at most
 * once. Main loop only. */
typedef struct {
    uint16_t ring[CTL_MAX_PARAMS + 1];
    uint8_t in[CTL_MAX_PARAMS];
    uint32_t head;
    uint32_t tail;
} CtlPending;

typedef struct {
    float value[CTL_MAX_PARAMS];
    float knob_pos[CTL_MAX_PARAMS];    /* Last reading, 0..1. */
    float knob_anchor[CTL_MAX_PARAMS]; /* Pick-up point while locked. */
    uint8_t knob_known[CTL_MAX_PARAMS];
    uint8_t knob_attached[CTL_MAX_PARAMS];
    uint8_t knob_locked[CTL_MAX_PARAMS];
    CtlQueue to_audio;
    CtlPending notify;   /* Changes the PC has not been told of (not those it made). */
    CtlPending midi_out; /* Knob and button changes to send as control change. */
    uint32_t now_ms;
    uint32_t last_change_ms;
    uint8_t settings_dirty; /* A preset or setting changed since the power-on record. */
    uint32_t refused;
    uint32_t taps; /* Tap-tempo presses (consumed by the tempo follower). */
} CtlCore;

void ctl_core_init(CtlCore *core);
/* Pushes every value to the audio level, for start-up after the power-on record. */
void ctl_core_sync_audio(CtlCore *core);
void ctl_core_set_time(CtlCore *core, uint32_t now_ms);

/* Writes a value from `src`, clamped. `applied` (may be NULL) gets the value now held. */
CtlResult ctl_core_set(CtlCore *core, size_t index, float value, CtlSource src, float *applied);
/* A knob reading, 0..1, for a parameter with kCtlFlagKnob. */
CtlResult ctl_core_knob(CtlCore *core, size_t index, float position);
float ctl_core_get(const CtlCore *core, size_t index);
/* 0 knob wins, 1 PC wins; -1 when the parameter has no knob. */
int ctl_core_mode(const CtlCore *core, size_t index);
int ctl_core_knob_attached(const CtlCore *core, size_t index);
/* A tap-tempo press. */
void ctl_core_tap(CtlCore *core);

/* Take one index waiting to be reported; 0 when none. */
int ctl_core_take_notify(CtlCore *core, uint16_t *index);
int ctl_core_take_midi(CtlCore *core, uint16_t *index);

#endif
