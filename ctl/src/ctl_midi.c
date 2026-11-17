#include "ctl/ctl_midi.h"

#include <string.h>

/* The fixed map (docs/notes/midi_map.md). Only CC numbers the MIDI specification leaves
 * undefined are used (3, 9, 14, 15, 20 to 31, 85 to 90, 102 to 119), so a DAW's own meaning of
 * the defined ones (volume, pan, sustain, bank select) never collides with the device. CC 20 to
 * 22 (the tone gains) have their fine halves at 52 to 54 (exercise EX8a). */
static const CtlMidiMapEntry kMap[] = {
    {3, 900},    /* record_source */
    {9, 403},    /* fx_trails */
    {14, 300},   /* in1_level_db */
    {15, 302},   /* in2_level_db */
    {20, 500},   /* tone_bass_db */
    {21, 501},   /* tone_mid_db */
    {22, 502},   /* tone_treble_db */
    {23, 800},   /* monitor_volume_db */
    {24, 801},   /* phones_volume_db */
    {25, 402},   /* fx_amount */
    {26, 306},   /* blend */
    {27, 400},   /* fx_select */
    {28, 401},   /* fx_on */
    {29, 802},   /* mute */
    {30, 803},   /* dim */
    {31, 0},     /* tap tempo */
    {85, 304},   /* usb_level_db */
    {86, 310},   /* rev_return_db */
    {87, 307},   /* in1_rev_send_db */
    {88, 308},   /* in2_rev_send_db */
    {89, 309},   /* usb_rev_send_db */
    {90, 350},   /* rev_decay_s */
    {102, 100},  /* in1_trim_db */
    {103, 200},  /* in2_trim_db */
    {104, 141},  /* in1_comp_threshold_db */
    {105, 241},  /* in2_comp_threshold_db */
    {106, 151},  /* in1_sat_drive_db */
    {107, 251},  /* in2_sat_drive_db */
    {108, 301},  /* in1_pan */
    {109, 303},  /* in2_pan */
    {110, 413},  /* echo_feedback */
    {111, 411},  /* echo_time_ms */
    {112, 420},  /* chorus_rate_hz */
    {113, 433},  /* flanger_feedback */
    {114, 442},  /* phaser_rate_hz */
    {115, 452},  /* trem_rate_hz */
    {116, 460},  /* sweep_resonance */
    {117, 472},  /* drive_level_db */
    {118, 480},  /* crush_bits */
    {119, 352},  /* rev_predelay_ms */
};

#define MAP_COUNT (sizeof(kMap) / sizeof(kMap[0]))

static int is_fine_pair(uint8_t cc) { return cc >= 20u && cc <= 22u; }

size_t ctl_midi_map_count(void) { return MAP_COUNT; }

const CtlMidiMapEntry *ctl_midi_map_entry(size_t i) { return i < MAP_COUNT ? &kMap[i] : NULL; }

static const CtlMidiMapEntry *lookup(uint8_t cc) {
    for (size_t i = 0; i < MAP_COUNT; ++i) {
        if (kMap[i].cc == cc) {
            return &kMap[i];
        }
    }
    return NULL;
}

int ctl_midi_cc_of(size_t param_index) {
    const CtlParamDesc *d = ctl_param_desc(param_index);
    if (d == NULL) {
        return -1;
    }
    for (size_t i = 0; i < MAP_COUNT; ++i) {
        if (kMap[i].param_id == d->id) {
            return kMap[i].cc;
        }
    }
    return -1;
}

void ctl_midi_init(CtlMidi *m, CtlCore *core, CtlPresetStore *presets) {
    memset(m, 0, sizeof(*m));
    m->core = core;
    m->presets = presets;
}

static int channel(const CtlMidi *m) {
    const int32_t i = ctl_param_find("midi_channel", 12u);
    return (int)ctl_core_get(m->core, (size_t)i);
}

static void set_param(CtlMidi *m, uint16_t id, float x) {
    const int32_t i = ctl_param_index_of(id);
    if (i >= 0) {
        (void)ctl_core_set(m->core, (size_t)i, ctl_param_from_norm(ctl_param_desc((size_t)i), x),
                           kCtlSrcMidi, NULL);
    }
}

static void control_change(CtlMidi *m, uint8_t cc, uint8_t value) {
    ++m->cc_in;
    if (cc >= 32u && cc < 64u && is_fine_pair((uint8_t)(cc - 32u))) {
        float x;
        if (ctl_midi_cc14(m, cc, value, &x)) {
            set_param(m, lookup((uint8_t)(cc - 32u))->param_id, x);
        }
        return;
    }
    const CtlMidiMapEntry *e = lookup(cc);
    if (e == NULL) {
        ++m->cc_unmapped;
        return;
    }
    if (e->param_id == 0u) {
        if (cc == CTL_MIDI_CC_TAP && value >= 64u) {
            ctl_core_tap(m->core);
        }
        return;
    }
    float x;
    if (is_fine_pair(cc)) {
        if (!ctl_midi_cc14(m, cc, value, &x)) {
            return;
        }
    } else {
        x = ctl_midi7_to_norm(value);
    }
    set_param(m, e->param_id, x);
}

static void channel_message(CtlMidi *m, uint8_t status, const uint8_t *data) {
    const int ch = channel(m);
    if (ch != 0 && (status & 0x0Fu) != (uint8_t)(ch - 1)) {
        return;
    }
    switch (status & 0xF0u) {
    case 0xB0u:
        if (data[0] < 120u) { /* 120 to 127 are channel mode messages. */
            control_change(m, data[0], data[1]);
        }
        break;
    case 0xC0u:
        if (m->presets != NULL && data[0] < CTL_PRESET_SLOTS) {
            (void)ctl_preset_load(m->presets, data[0], m->core);
        }
        break;
    default:
        break; /* Notes, pressure, pitch bend: not used. */
    }
}

static uint8_t data_bytes(uint8_t status) {
    switch (status & 0xF0u) {
    case 0xC0u:
    case 0xD0u:
        return 1u;
    default:
        return 2u;
    }
}

void ctl_midi_in(CtlMidi *m, const uint8_t *bytes, size_t n, uint32_t now_us) {
    for (size_t i = 0; i < n; ++i) {
        const uint8_t b = bytes[i];
        if (b >= 0xF8u) { /* Real time: at once, wherever it falls. */
            switch (b) {
            case 0xF8u:
                ++m->clocks;
                break;
            case 0xFAu:
                ++m->starts;
                break;
            case 0xFBu:
                ++m->continues;
                break;
            case 0xFCu:
                ++m->stops;
                break;
            default:
                break;
            }
            if (m->realtime != NULL) {
                m->realtime(m->realtime_ctx, b, now_us);
            }
            continue;
        }
        if (b >= 0x80u) {
            m->n_data = 0;
            m->skip = 0;
            if (m->in_sysex) {
                m->in_sysex = 0;
                ++m->sysex_skipped;
                if (b == 0xF7u) {
                    m->status = 0;
                    continue;
                }
            }
            if (b < 0xF0u) {
                m->status = b;
            } else {
                m->status = 0; /* System common cancels running status. */
                if (b == 0xF0u) {
                    m->in_sysex = 1;
                } else if (b == 0xF1u || b == 0xF3u) {
                    m->skip = 1;
                } else if (b == 0xF2u) {
                    m->skip = 2;
                }
            }
            continue;
        }
        /* A data byte. */
        if (m->in_sysex) {
            continue;
        }
        if (m->skip > 0u) {
            --m->skip;
            continue;
        }
        if (m->status == 0u) {
            continue; /* No status to attach it to. */
        }
        m->data[m->n_data++] = b;
        if (m->n_data == data_bytes(m->status)) {
            channel_message(m, m->status, m->data);
            m->n_data = 0; /* Running status: the next data bytes reuse it. */
        }
    }
}

size_t ctl_midi_out(CtlMidi *m, uint8_t *out, size_t cap) {
    size_t len = 0;
    const int32_t on = ctl_param_find("midi_cc_out", 11u);
    const int enabled = ctl_core_get(m->core, (size_t)on) >= 0.5f;
    const int ch = channel(m);
    const uint8_t status = (uint8_t)(0xB0u | (uint8_t)(ch == 0 ? 0 : ch - 1));
    uint16_t index;
    while (len + 3u <= cap && ctl_core_take_midi(m->core, &index)) {
        const int cc = ctl_midi_cc_of(index);
        if (!enabled || cc < 0) {
            continue;
        }
        const CtlParamDesc *d = ctl_param_desc(index);
        out[len++] = status;
        out[len++] = (uint8_t)cc;
        out[len++] = ctl_norm_to_midi7(ctl_param_to_norm(d, ctl_core_get(m->core, index)));
    }
    return len;
}
