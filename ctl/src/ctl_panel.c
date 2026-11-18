/* The control panel: pots and buttons into the control core, LEDs out (ctl_panel.h). */
#include "ctl/ctl_panel.h"

#include <string.h>

static const char *const kPotParams[CTL_PANEL_POTS] = {
    "tone_bass_db", "tone_mid_db", "tone_treble_db", "monitor_volume_db",
    "phones_volume_db", "fx_amount", "blend",
};

static const CtlPotKind kPotKinds[CTL_PANEL_POTS] = {
    kCtlPotCentre, kCtlPotCentre, kCtlPotCentre, kCtlPotVolume,
    kCtlPotVolume, kCtlPotLinear, kCtlPotLinear,
};

static int32_t find(const char *name) { return ctl_param_find(name, strlen(name)); }

void ctl_led_hold_init(CtlLedHold *h) {
    h->until_ms = 0u;
    h->on = 0u;
}

int ctl_led_hold(CtlLedHold *h, float level_db, float threshold_db, uint32_t hold_ms,
                 uint32_t now_ms) {
    if (level_db >= threshold_db) {
        h->on = 1u;
        h->until_ms = now_ms + hold_ms;
    } else if (h->on != 0u && (int32_t)(now_ms - h->until_ms) >= 0) {
        h->on = 0u;
    }
    return h->on;
}

void ctl_panel_init(CtlPanel *panel, uint32_t adc_bits) {
    for (size_t k = 0; k < CTL_PANEL_POTS; ++k) {
        ctl_pot_init(&panel->pot[k], adc_bits, CTL_POT_TAU_MS);
        ctl_pot_cal_default(&panel->cal[k]);
        panel->pot_param[k] = find(kPotParams[k]);
    }
    for (size_t k = 0; k < CTL_PANEL_BUTTONS; ++k) {
        ctl_button_init(&panel->button[k]);
    }
    for (size_t k = 0; k < 2u; ++k) {
        ctl_led_hold_init(&panel->signal[k]);
        ctl_led_hold_init(&panel->clip[k]);
    }
    panel->idx_fx_select = find("fx_select");
    panel->idx_fx_on = find("fx_on");
    panel->idx_mute = find("mute");
    panel->idx_dim = find("dim");
    panel->idx_tempo_source = find("tempo_source");
    panel->idx_tempo_bpm = find("tempo_bpm");
    panel->idx_peak[0] = find("in1_peak_db");
    panel->idx_peak[1] = find("in2_peak_db");
    panel->tap_override = 0u;
    panel->bpm_before_tap = 0.0f;
    panel->refused = 0u;
}

static void put(CtlPanel *panel, CtlCore *core, int32_t index, float value) {
    if (ctl_core_set(core, (size_t)index, value, kCtlSrcButton, NULL) != kCtlOk) {
        ++panel->refused;
    }
}

static void toggle(CtlPanel *panel, CtlCore *core, int32_t index) {
    put(panel, core, index, ctl_core_get(core, (size_t)index) >= 0.5f ? 0.0f : 1.0f);
}

/* The next (dir 1) or previous (dir -1) effect the core accepts. */
static void step_effect(CtlPanel *panel, CtlCore *core, int dir) {
    const size_t index = (size_t)panel->idx_fx_select;
    const CtlParamDesc *d = ctl_param_desc(index);
    const int first = (int)d->min;
    const int n = (int)d->max - first + 1;
    const int cur = (int)ctl_core_get(core, index) - first;
    for (int k = 1; k < n; ++k) {
        const int v = ((cur + dir * k) % n + n) % n + first;
        if (ctl_core_set(core, index, (float)v, kCtlSrcButton, NULL) == kCtlOk) {
            return;
        }
    }
    ++panel->refused;
}

static void tap(CtlPanel *panel, CtlCore *core, uint32_t ev) {
    const size_t src = (size_t)panel->idx_tempo_source;
    if ((ev & kCtlButtonPress) != 0u) {
        const int source = (int)ctl_core_get(core, src);
        if (source != 2) {
            panel->tap_override = 0u;
        }
        if (source == 0) {
            panel->bpm_before_tap = ctl_core_get(core, (size_t)panel->idx_tempo_bpm);
            put(panel, core, (int32_t)src, 2.0f);
            panel->tap_override = 1u;
        }
        ctl_core_tap(core);
    }
    if ((ev & kCtlButtonLong) != 0u && panel->tap_override != 0u &&
        (int)ctl_core_get(core, src) == 2) {
        put(panel, core, (int32_t)src, 0.0f);
        put(panel, core, panel->idx_tempo_bpm, panel->bpm_before_tap);
        panel->tap_override = 0u;
    }
}

void ctl_panel_tick(CtlPanel *panel, CtlCore *core, const uint32_t sums[CTL_PANEL_POTS],
                    uint32_t closed) {
    for (size_t k = 0; k < CTL_PANEL_POTS; ++k) {
        float travel;
        if (ctl_pot_update(&panel->pot[k], sums[k], &travel) != 0) {
            const float x = ctl_pot_shape(&panel->cal[k], kPotKinds[k], travel);
            (void)ctl_core_knob(core, (size_t)panel->pot_param[k], x);
        }
    }
    uint32_t ev[CTL_PANEL_BUTTONS];
    for (size_t k = 0; k < CTL_PANEL_BUTTONS; ++k) {
        ev[k] = ctl_button_update(&panel->button[k], (int)((closed >> k) & 1u));
    }
    if ((ev[kCtlBtnFxSelect] & kCtlButtonShort) != 0u) {
        step_effect(panel, core, 1);
    }
    if ((ev[kCtlBtnFxSelect] & kCtlButtonLong) != 0u) {
        step_effect(panel, core, -1);
    }
    if ((ev[kCtlBtnFxOn] & kCtlButtonPress) != 0u) {
        toggle(panel, core, panel->idx_fx_on);
    }
    tap(panel, core, ev[kCtlBtnTap]);
    if ((ev[kCtlBtnMute] & kCtlButtonPress) != 0u) {
        toggle(panel, core, panel->idx_mute);
    }
    if ((ev[kCtlBtnDim] & kCtlButtonPress) != 0u) {
        toggle(panel, core, panel->idx_dim);
    }
}

uint32_t ctl_panel_leds(CtlPanel *panel, const CtlCore *core, uint32_t now_ms) {
    static const uint32_t kSignal[2] = {kCtlLedSignal1, kCtlLedSignal2};
    static const uint32_t kClip[2] = {kCtlLedClip1, kCtlLedClip2};
    uint32_t leds = 0u;
    for (size_t k = 0; k < 2u; ++k) {
        const float peak = ctl_core_get(core, (size_t)panel->idx_peak[k]);
        if (ctl_led_hold(&panel->signal[k], peak, CTL_LED_SIGNAL_DB, CTL_LED_SIGNAL_HOLD_MS,
                         now_ms) != 0) {
            leds |= kSignal[k];
        }
        if (ctl_led_hold(&panel->clip[k], peak, CTL_LED_CLIP_DB, CTL_LED_CLIP_HOLD_MS,
                         now_ms) != 0) {
            leds |= kClip[k];
        }
    }
    if (ctl_core_get(core, (size_t)panel->idx_mute) >= 0.5f) {
        leds |= kCtlLedMute;
    }
    if (ctl_core_get(core, (size_t)panel->idx_dim) >= 0.5f) {
        leds |= kCtlLedDim;
    }
    if (ctl_core_get(core, (size_t)panel->idx_fx_on) >= 0.5f) {
        leds |= kCtlLedFxOn;
    }
    return leds;
}
