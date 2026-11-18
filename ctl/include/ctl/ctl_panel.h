/* The control panel: seven potentiometers, five buttons and the footswitch into the control
 * core, and the seven LEDs out of it (batch 8d, docs/notes/panel_input.md).
 *
 * ctl_panel_tick runs once per millisecond with that millisecond's pot readings (ctl_pot.h) and
 * contacts (ctl_button.h). Pots go through ctl_core_knob, so knob ownership and pick-up apply
 * (docs/notes/knob_pickup.md); buttons write with kCtlSrcButton, so the budget rule applies.
 *
 * Button mapping (proposed, for the owner to confirm):
 * - FX select: a short press selects the next effect, a long press the previous one. An effect
 *   the budget rule refuses is skipped, so the button never seems dead.
 * - FX on: each press toggles.
 * - Tap: each press is a tap (timed at the press, so the debounce delay cancels out). In auto
 *   tempo source, the first tap switches the source to tap or stored, so the tap is heard even
 *   while MIDI clock runs, and remembers the tempo it replaced. A long press undoes that: auto
 *   again (MIDI clock if present) and the remembered tempo back.
 * - Mute, dim: each press toggles.
 * - Footswitch, by the setting footswitch_type: 0 each press toggles FX on (a momentary pedal);
 *   1 FX on follows the contact (a latching pedal, or a momentary one held down). Edges only, so
 *   at start-up a latched pedal switches the effect on with its first debounced press.
 *
 * LEDs (ctl_panel_leds, at about 100 Hz): signal per input at CTL_LED_SIGNAL_DB with a 100 ms
 * hold, clip at CTL_LED_CLIP_DB with 300 ms, from the input peak meters; mute, dim and FX on
 * show their state.
 *
 * Hardware-free C11. Main loop only.
 */
#ifndef CTL_PANEL_H
#define CTL_PANEL_H

#include "ctl/ctl_button.h"
#include "ctl/ctl_core.h"
#include "ctl/ctl_pot.h"

#include <stdint.h>

typedef enum {
    kCtlPotBass = 0,
    kCtlPotMid,
    kCtlPotTreble,
    kCtlPotMonitor,
    kCtlPotPhones,
    kCtlPotFxAmount,
    kCtlPotBlend,
    CTL_PANEL_POTS
} CtlPanelPot;

typedef enum {
    kCtlBtnFxSelect = 0,
    kCtlBtnFxOn,
    kCtlBtnTap,
    kCtlBtnMute,
    kCtlBtnDim,
    kCtlBtnFootswitch,
    CTL_PANEL_BUTTONS
} CtlPanelButton;

enum {
    kCtlLedSignal1 = 1u << 0,
    kCtlLedClip1 = 1u << 1,
    kCtlLedSignal2 = 1u << 2,
    kCtlLedClip2 = 1u << 3,
    kCtlLedMute = 1u << 4,
    kCtlLedDim = 1u << 5,
    kCtlLedFxOn = 1u << 6,
};

#define CTL_LED_SIGNAL_DB (-40.0f)
#define CTL_LED_SIGNAL_HOLD_MS 100u
#define CTL_LED_CLIP_DB (-0.5f)
#define CTL_LED_CLIP_HOLD_MS 300u

/* An LED lit while a level is at or over a threshold, and for hold_ms after. */
typedef struct {
    uint32_t until_ms;
    uint8_t on;
} CtlLedHold;

void ctl_led_hold_init(CtlLedHold *h);
/* Returns 1 while lit. now_ms from any free-running millisecond counter (wrap-safe). */
int ctl_led_hold(CtlLedHold *h, float level_db, float threshold_db, uint32_t hold_ms,
                 uint32_t now_ms);

typedef struct {
    CtlPot pot[CTL_PANEL_POTS];
    CtlPotCal cal[CTL_PANEL_POTS];
    CtlButton button[CTL_PANEL_BUTTONS];
    CtlLedHold signal[2];
    CtlLedHold clip[2];
    int32_t pot_param[CTL_PANEL_POTS];
    int32_t idx_fx_select, idx_fx_on, idx_mute, idx_dim;
    int32_t idx_tempo_source, idx_tempo_bpm, idx_footswitch_type;
    int32_t idx_peak[2];
    uint8_t tap_override; /* The panel switched the tempo source to tap. */
    float bpm_before_tap;
    uint32_t refused; /* Button writes the core refused (the budget rule, in practice). */
} CtlPanel;

/* adc_bits: the resolution of one conversion (12 to 16 on the H7). Calibrations default to the
 * ideal pot; set panel->cal[] afterwards for a measured unit. */
void ctl_panel_init(CtlPanel *panel, uint32_t adc_bits);
/* One millisecond: sums[k] is pot k's reading (CTL_POT_AVERAGE conversions summed); bit k of
 * closed is button k's contact (1 = closed). */
void ctl_panel_tick(CtlPanel *panel, CtlCore *core, const uint32_t sums[CTL_PANEL_POTS],
                    uint32_t closed);
/* The LEDs to light, a mask of kCtlLed*. */
uint32_t ctl_panel_leds(CtlPanel *panel, const CtlCore *core, uint32_t now_ms);

#endif
