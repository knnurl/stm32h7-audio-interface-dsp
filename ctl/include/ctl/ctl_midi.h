/* MIDI in and out (docs/notes/midi_map.md has the map and the reasoning).
 *
 * In: a byte-stream parser with running status. Real-time bytes (0xF8 to 0xFF) may arrive
 * anywhere, even inside another message, and are handled at once without disturbing it.
 * System exclusive is skipped to its end (or to the next status byte). Channel messages are
 * taken on the device's channel (parameter midi_channel, 0 meaning omni).
 * - Control change: a fixed table maps CC numbers to parameters; the 7-bit value is scaled
 *   along the parameter's curve with 64 at the centre (ctl_midi7_to_norm). MIDI counts as a PC
 *   source for knob ownership. CC 31 at 64 or above is a tap-tempo press.
 * - Program change 0 to 7: recall preset 1 to 8.
 * - Clock, start, continue, stop: counted, time-stamped and passed to `realtime` (the tempo
 *   follower, batch 8b).
 * Out: a knob or button change sends its CC on the device's channel (omni sends on channel 1),
 * when midi_cc_out is on. A value that arrived by MIDI is not sent back.
 *
 * USB MIDI carries 4-byte event packets; the batch 4 transport turns them into this byte stream.
 */
#ifndef CTL_MIDI_H
#define CTL_MIDI_H

#include "ctl/ctl_core.h"
#include "ctl/ctl_preset.h"

#include <stddef.h>
#include <stdint.h>

#define CTL_MIDI_CC_TAP 31u

typedef void (*CtlMidiRealtimeFn)(void *ctx, uint8_t byte, uint32_t now_us);

typedef struct {
    uint8_t cc;
    uint16_t param_id; /* 0: an action (tap tempo), not a parameter */
} CtlMidiMapEntry;

typedef struct {
    CtlCore *core;
    CtlPresetStore *presets; /* May be NULL. */
    CtlMidiRealtimeFn realtime;
    void *realtime_ctx;
    /* Parser. */
    uint8_t status;  /* Running status; 0 when none. */
    uint8_t data[2];
    uint8_t n_data;
    uint8_t in_sysex;
    uint8_t skip;    /* Data bytes of a system common message still to skip. */
    /* 14-bit control change (exercise EX8a): most significant parts by CC 0..31. */
    uint8_t msb[32];
    uint8_t msb_valid[32];
    /* Counters. */
    uint32_t clocks;
    uint32_t starts;
    uint32_t stops;
    uint32_t continues;
    uint32_t cc_in;
    uint32_t cc_unmapped;
    uint32_t sysex_skipped;
} CtlMidi;

void ctl_midi_init(CtlMidi *m, CtlCore *core, CtlPresetStore *presets);
void ctl_midi_in(CtlMidi *m, const uint8_t *bytes, size_t n, uint32_t now_us);
/* Fills `out` with control change messages for pending knob and button changes; returns the
 * bytes written (whole messages only). */
size_t ctl_midi_out(CtlMidi *m, uint8_t *out, size_t cap);

/* The fixed map. */
size_t ctl_midi_map_count(void);
const CtlMidiMapEntry *ctl_midi_map_entry(size_t i);
/* CC number for a parameter index, or -1. */
int ctl_midi_cc_of(size_t param_index);

/* Exercise EX8a (ctl/src/ctl_midi_cc14.c, the owner's): a control change on a CC that may be
 * half of a 14-bit pair. Returns 1 and sets *x (0..1) when the mapped parameter should be set,
 * 0 when the message only updates state. `cc` is the received number, which may be the fine
 * half (cc 32..63) of a mapped CC 0..31. */
int ctl_midi_cc14(CtlMidi *m, uint8_t cc, uint8_t value, float *x);

#endif
