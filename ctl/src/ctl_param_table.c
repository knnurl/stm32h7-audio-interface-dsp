/* The parameter table: every parameter of the device, declared once (docs/notes/ctl_registry.md
 * has the reasoning; `python tools/ctl.py --sim list` prints it).
 *
 * Rules, checked by tests/unit/test_ctl_params.py:
 * - ids ascend through the table and are never reused; gaps are reserved for later parameters
 *   of the same group;
 * - names are unique snake_case with the unit in the name where there is one;
 * - min < max, the default is in range, log curves have min > 0, step parameters are integers.
 *
 * Id ranges: 100 input 1, 200 input 2, 300 monitor mixer, 350 reverb, 400 effect slot,
 * 410-489 the effects, 500 tone, 600 speaker stage, 700 headphone stage, 800 monitor controls,
 * 900 device settings, 910 knob ownership modes, 1000 meters.
 */
#include "ctl/ctl_params.h"

#define LIN kCtlCurveLinear
#define LOG kCtlCurveLog
#define VOL kCtlCurveVolume
#define STEP kCtlCurveStep
#define KNOB kCtlFlagKnob
#define BUTTON kCtlFlagButton
#define PRESET kCtlFlagPreset
#define SETTING kCtlFlagSetting
#define METER kCtlFlagReadOnly

#define P(id, name, label, unit, mn, mx, df, curve, flags, smooth)                                 \
    {(id), (curve), (flags), (name), (label), (unit), (mn), (mx), (df), (smooth)}

/* One parametric band: frequency, gain, Q. Band 1 is a low shelf, 2 and 3 are peaks, 4 is a
 * high shelf (types fixed in this table version). Bands 3 and 4 start at 2.5 kHz: they run in
 * float32 (dsp_peq.h, budget option D, 2026-11-18). */
#define PEQ_BAND(base, pfx, lpfx, k, f_min, f_def, flags)                                          \
    P((base) + 3 * ((k)-1), pfx "peq" #k "_hz", lpfx "band " #k " frequency", "Hz", (f_min),       \
      20000.0f, (f_def), LOG, (flags), 20.0f),                                                     \
        P((base) + 3 * ((k)-1) + 1, pfx "peq" #k "_gain_db", lpfx "band " #k " gain", "dB",        \
          -15.0f, 15.0f, 0.0f, LIN, (flags), 20.0f),                                               \
        P((base) + 3 * ((k)-1) + 2, pfx "peq" #k "_q", lpfx "band " #k " Q", "", 0.1f, 10.0f,      \
          0.7f, LOG, (flags), 20.0f)

#define PEQ4(base, pfx, lpfx, flags)                                                               \
    PEQ_BAND(base, pfx, lpfx, 1, 20.0f, 100.0f, flags),                                            \
        PEQ_BAND(base, pfx, lpfx, 2, 20.0f, 400.0f, flags),                                        \
        PEQ_BAND(base, pfx, lpfx, 3, 2500.0f, 2500.0f, flags),                                     \
        PEQ_BAND(base, pfx, lpfx, 4, 2500.0f, 8000.0f, flags)

/* An input strip: trim, high-pass, four PEQ bands, gate, compressor, saturation. */
#define STRIP(b, pfx, lpfx)                                                                        \
    P((b) + 0, pfx "trim_db", lpfx "trim", "dB", -20.0f, 20.0f, 0.0f, LIN, PRESET, 20.0f),         \
        P((b) + 1, pfx "hpf_on", lpfx "high-pass on", "", 0.0f, 1.0f, 1.0f, STEP, PRESET, 0.0f),   \
        P((b) + 2, pfx "hpf_hz", lpfx "high-pass frequency", "Hz", 20.0f, 400.0f, 40.0f, LOG,      \
          PRESET, 20.0f),                                                                          \
        PEQ4((b) + 10, pfx, lpfx, PRESET),                                                         \
        P((b) + 30, pfx "gate_on", lpfx "gate on", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f),      \
        P((b) + 31, pfx "gate_threshold_db", lpfx "gate threshold", "dB", -80.0f, 0.0f, -50.0f,    \
          LIN, PRESET, 0.0f),                                                                      \
        P((b) + 32, pfx "gate_range_db", lpfx "gate range", "dB", -80.0f, 0.0f, -60.0f, LIN,       \
          PRESET, 0.0f),                                                                           \
        P((b) + 33, pfx "gate_release_ms", lpfx "gate release", "ms", 5.0f, 2000.0f, 100.0f, LOG,  \
          PRESET, 0.0f),                                                                           \
        P((b) + 40, pfx "comp_on", lpfx "compressor on", "", 0.0f, 1.0f, 0.0f, STEP, PRESET,       \
          0.0f),                                                                                   \
        P((b) + 41, pfx "comp_threshold_db", lpfx "compressor threshold", "dB", -60.0f, 0.0f,      \
          -18.0f, LIN, PRESET, 0.0f),                                                              \
        P((b) + 42, pfx "comp_ratio", lpfx "compressor ratio", "", 1.0f, 20.0f, 4.0f, LOG, PRESET, \
          0.0f),                                                                                   \
        P((b) + 43, pfx "comp_attack_ms", lpfx "compressor attack", "ms", 0.1f, 100.0f, 10.0f,     \
          LOG, PRESET, 0.0f),                                                                      \
        P((b) + 44, pfx "comp_release_ms", lpfx "compressor release", "ms", 10.0f, 2000.0f, 50.0f, \
          LOG, PRESET, 0.0f),                                                                      \
        P((b) + 45, pfx "comp_knee_db", lpfx "compressor knee", "dB", 0.0f, 24.0f, 6.0f, LIN,      \
          PRESET, 0.0f),                                                                           \
        P((b) + 46, pfx "comp_makeup_db", lpfx "compressor make-up gain", "dB", 0.0f, 24.0f, 0.0f, \
          LIN, PRESET, 20.0f),                                                                     \
        P((b) + 50, pfx "sat_on", lpfx "saturation on", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f), \
        P((b) + 51, pfx "sat_drive_db", lpfx "saturation drive", "dB", 0.0f, 36.0f, 6.0f, LIN,     \
          PRESET, 20.0f),                                                                          \
        P((b) + 52, pfx "sat_mode", lpfx "saturation mode (0 plain, 1 2x, 2 4x, 3 ADAA)", "",      \
          0.0f, 3.0f, 1.0f, STEP, PRESET, 0.0f)

/* Note values for synced effects: 0 1/2, 1 1/4, 2 dotted 1/8, 3 1/8, 4 1/8 triplet, 5 1/16. */
#define NOTE_MAX 5.0f

static const CtlParamDesc kTable[] = {
    STRIP(100, "in1_", "Input 1 "),
    STRIP(200, "in2_", "Input 2 "),

    /* Monitor mixer. */
    P(300, "in1_level_db", "Input 1 level", "dB", -80.0f, 6.0f, 0.0f, VOL, PRESET, 20.0f),
    P(301, "in1_pan", "Input 1 pan", "", -1.0f, 1.0f, 0.0f, LIN, PRESET, 20.0f),
    P(302, "in2_level_db", "Input 2 level", "dB", -80.0f, 6.0f, 0.0f, VOL, PRESET, 20.0f),
    P(303, "in2_pan", "Input 2 pan", "", -1.0f, 1.0f, 0.0f, LIN, PRESET, 20.0f),
    P(304, "usb_level_db", "Playback level", "dB", -80.0f, 6.0f, 0.0f, VOL, PRESET, 20.0f),
    P(305, "spdif_level_db", "S/PDIF level", "dB", -80.0f, 6.0f, -80.0f, VOL, PRESET, 20.0f),
    P(306, "blend", "Input and playback blend", "", 0.0f, 1.0f, 0.5f, LIN, KNOB | PRESET, 20.0f),
    P(307, "in1_rev_send_db", "Input 1 reverb send", "dB", -80.0f, 0.0f, -80.0f, VOL, PRESET,
      20.0f),
    P(308, "in2_rev_send_db", "Input 2 reverb send", "dB", -80.0f, 0.0f, -80.0f, VOL, PRESET,
      20.0f),
    P(309, "usb_rev_send_db", "Playback reverb send", "dB", -80.0f, 0.0f, -80.0f, VOL, PRESET,
      20.0f),
    P(310, "rev_return_db", "Reverb return", "dB", -80.0f, 6.0f, 0.0f, VOL, PRESET, 20.0f),

    /* Reverb. */
    P(350, "rev_decay_s", "Reverb decay", "s", 0.2f, 10.0f, 1.8f, LOG, PRESET, 0.0f),
    P(351, "rev_hf_ratio", "Reverb decay ratio at 8 kHz", "", 0.1f, 1.0f, 0.5f, LIN, PRESET,
      0.0f),
    /* 50 ms, not 100: halves the pre-delay's 75 KB at 96 kHz (owner, 2026-11-17). */
    P(352, "rev_predelay_ms", "Reverb pre-delay", "ms", 0.0f, 50.0f, 10.0f, LIN, PRESET, 0.0f),

    /* Effect slot: 0 echo, 1 chorus, 2 flanger, 3 phaser, 4 tremolo, 5 sweep filter,
     * 6 overdrive, 7 bit crusher. */
    P(400, "fx_select", "Effect", "", 0.0f, 7.0f, 0.0f, STEP, BUTTON | PRESET, 0.0f),
    P(401, "fx_on", "Effect on", "", 0.0f, 1.0f, 0.0f, STEP, BUTTON | PRESET, 0.0f),
    P(402, "fx_amount", "Effect amount", "", 0.0f, 1.0f, 0.5f, LIN, KNOB | PRESET, 20.0f),
    P(403, "fx_trails", "Effect trails", "", 0.0f, 1.0f, 1.0f, STEP, PRESET, 0.0f),

    P(410, "echo_sync", "Echo tempo sync", "", 0.0f, 1.0f, 1.0f, STEP, PRESET, 0.0f),
    P(411, "echo_time_ms", "Echo time", "ms", 10.0f, 750.0f, 375.0f, LOG, PRESET, 50.0f),
    P(412, "echo_note", "Echo note value", "", 0.0f, NOTE_MAX, 3.0f, STEP, PRESET, 0.0f),
    P(413, "echo_feedback", "Echo feedback", "", 0.0f, 0.95f, 0.4f, LIN, PRESET, 20.0f),
    P(414, "echo_tone", "Echo tone", "", 0.0f, 1.0f, 0.5f, LIN, PRESET, 20.0f),
    P(415, "echo_ping_pong", "Echo ping-pong", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f),

    P(420, "chorus_rate_hz", "Chorus rate", "Hz", 0.05f, 5.0f, 0.8f, LOG, PRESET, 0.0f),
    P(421, "chorus_spread", "Chorus stereo spread", "", 0.0f, 1.0f, 0.7f, LIN, PRESET, 20.0f),

    P(430, "flanger_sync", "Flanger tempo sync", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f),
    P(431, "flanger_note", "Flanger note value", "", 0.0f, NOTE_MAX, 1.0f, STEP, PRESET, 0.0f),
    P(432, "flanger_rate_hz", "Flanger rate", "Hz", 0.02f, 5.0f, 0.25f, LOG, PRESET, 0.0f),
    P(433, "flanger_feedback", "Flanger feedback", "", -0.95f, 0.95f, 0.5f, LIN, PRESET, 20.0f),

    P(440, "phaser_sync", "Phaser tempo sync", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f),
    P(441, "phaser_note", "Phaser note value", "", 0.0f, NOTE_MAX, 1.0f, STEP, PRESET, 0.0f),
    P(442, "phaser_rate_hz", "Phaser rate", "Hz", 0.02f, 5.0f, 0.4f, LOG, PRESET, 0.0f),
    P(443, "phaser_stages", "Phaser stages (0 four, 1 eight)", "", 0.0f, 1.0f, 0.0f, STEP, PRESET,
      0.0f),
    P(444, "phaser_feedback", "Phaser feedback", "", -0.9f, 0.9f, 0.3f, LIN, PRESET, 20.0f),

    P(450, "trem_sync", "Tremolo tempo sync", "", 0.0f, 1.0f, 1.0f, STEP, PRESET, 0.0f),
    P(451, "trem_note", "Tremolo note value", "", 0.0f, NOTE_MAX, 3.0f, STEP, PRESET, 0.0f),
    P(452, "trem_rate_hz", "Tremolo rate", "Hz", 0.1f, 20.0f, 4.0f, LOG, PRESET, 0.0f),
    P(453, "trem_shape", "Tremolo shape (0 sine, 1 triangle, 2 square, 3 ramp)", "", 0.0f, 3.0f,
      0.0f, STEP, PRESET, 0.0f),
    P(454, "trem_phase_deg", "Tremolo stereo phase", "deg", 0.0f, 180.0f, 0.0f, LIN, PRESET,
      0.0f),

    P(460, "sweep_resonance", "Sweep filter resonance", "", 0.0f, 1.0f, 0.3f, LIN, PRESET, 20.0f),

    P(470, "drive_tone", "Overdrive tone", "", 0.0f, 1.0f, 0.5f, LIN, PRESET, 20.0f),
    P(471, "drive_asym", "Overdrive asymmetric curve", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f),
    P(472, "drive_level_db", "Overdrive output level", "dB", -24.0f, 6.0f, 0.0f, LIN, PRESET,
      20.0f),

    P(480, "crush_bits", "Bit crusher depth", "bits", 2.0f, 16.0f, 8.0f, STEP, PRESET, 0.0f),
    P(481, "crush_rate_hz", "Bit crusher rate", "Hz", 1000.0f, 48000.0f, 12000.0f, LOG, PRESET,
      0.0f),
    P(482, "crush_dither", "Bit crusher dither", "", 0.0f, 1.0f, 0.0f, STEP, PRESET, 0.0f),

    /* Tone: monitors and headphones, never recorded. The corners are settings so the owner can
     * try values by ear without a new image (provisional defaults, SPEC decision log). */
    P(500, "tone_bass_db", "Bass", "dB", -12.0f, 12.0f, 0.0f, LIN, KNOB | PRESET, 20.0f),
    P(501, "tone_mid_db", "Mid", "dB", -12.0f, 12.0f, 0.0f, LIN, KNOB | PRESET, 20.0f),
    P(502, "tone_treble_db", "Treble", "dB", -12.0f, 12.0f, 0.0f, LIN, KNOB | PRESET, 20.0f),
    P(503, "tone_bass_hz", "Bass corner", "Hz", 40.0f, 400.0f, 100.0f, LOG, SETTING, 20.0f),
    P(504, "tone_mid_hz", "Mid centre", "Hz", 300.0f, 3000.0f, 1000.0f, LOG, SETTING, 20.0f),
    P(505, "tone_treble_hz", "Treble corner", "Hz", 3000.0f, 16000.0f, 10000.0f, LOG, SETTING,
      20.0f),

    /* Speaker stage: listening corrections, so settings, not presets. */
    PEQ4(600, "spk_", "Speaker ", SETTING),
    P(612, "spk_delay_ms", "Speaker delay", "ms", 0.0f, 10.0f, 0.0f, LIN, SETTING, 0.0f),
    P(613, "spk_ceiling_db", "Speaker limiter ceiling", "dB", -20.0f, 0.0f, -1.0f, LIN, SETTING,
      0.0f),
    P(614, "spk_release_ms", "Speaker limiter release", "ms", 10.0f, 1000.0f, 50.0f, LOG,
      SETTING, 0.0f),

    /* Headphone stage. */
    PEQ4(700, "hp_", "Headphone ", SETTING),
    P(712, "hp_crossfeed_on", "Crossfeed on", "", 0.0f, 1.0f, 0.0f, STEP, SETTING, 0.0f),
    P(713, "hp_crossfeed_amount", "Crossfeed amount", "", 0.0f, 1.0f, 0.5f, LIN, SETTING, 20.0f),
    P(714, "hp_ceiling_db", "Headphone limiter ceiling", "dB", -20.0f, 0.0f, -1.0f, LIN, SETTING,
      0.0f),

    /* Monitor controls. Mute is neither a preset nor a setting: the outputs start muted. */
    P(800, "monitor_volume_db", "Monitor volume", "dB", -80.0f, 0.0f, -40.0f, VOL,
      KNOB | SETTING, 20.0f),
    P(801, "phones_volume_db", "Headphone volume", "dB", -80.0f, 0.0f, -40.0f, VOL,
      KNOB | SETTING, 20.0f),
    P(802, "mute", "Mute", "", 0.0f, 1.0f, 1.0f, STEP, BUTTON, 20.0f),
    P(803, "dim", "Dim", "", 0.0f, 1.0f, 0.0f, STEP, BUTTON, 20.0f),
    P(804, "dim_db", "Dim level", "dB", -40.0f, 0.0f, -20.0f, LIN, SETTING, 20.0f),

    /* Device settings. */
    P(900, "record_source", "Record source (0 inputs, 1 mix)", "", 0.0f, 1.0f, 0.0f, STEP,
      SETTING, 0.0f),
    P(901, "tempo_source", "Tempo source (0 auto, 1 MIDI clock, 2 tap or stored)", "", 0.0f, 2.0f,
      0.0f, STEP, SETTING, 0.0f),
    P(902, "tempo_bpm", "Tempo", "BPM", 40.0f, 300.0f, 120.0f, LIN, PRESET, 0.0f),
    P(903, "midi_channel", "MIDI channel (0 omni)", "", 0.0f, 16.0f, 1.0f, STEP, SETTING, 0.0f),
    P(904, "midi_cc_out", "MIDI control change out", "", 0.0f, 1.0f, 1.0f, STEP, SETTING, 0.0f),

    /* Knob ownership: 0 knob wins, 1 PC wins (SPEC 6.7, docs/notes/knob_pickup.md). */
    P(910, "mode_tone_bass", "Bass knob ownership", "", 0.0f, 1.0f, 0.0f, STEP, SETTING, 0.0f),
    P(911, "mode_tone_mid", "Mid knob ownership", "", 0.0f, 1.0f, 0.0f, STEP, SETTING, 0.0f),
    P(912, "mode_tone_treble", "Treble knob ownership", "", 0.0f, 1.0f, 0.0f, STEP, SETTING,
      0.0f),
    P(913, "mode_monitor_volume", "Monitor volume knob ownership", "", 0.0f, 1.0f, 0.0f, STEP,
      SETTING, 0.0f),
    P(914, "mode_phones_volume", "Headphone volume knob ownership", "", 0.0f, 1.0f, 0.0f, STEP,
      SETTING, 0.0f),
    P(915, "mode_fx_amount", "Effect amount knob ownership", "", 0.0f, 1.0f, 0.0f, STEP, SETTING,
      0.0f),
    P(916, "mode_blend", "Blend knob ownership", "", 0.0f, 1.0f, 0.0f, STEP, SETTING, 0.0f),

    /* Meters and status, written by the device. */
    P(1000, "in1_peak_db", "Input 1 peak", "dB", -120.0f, 6.0f, -120.0f, LIN, METER, 0.0f),
    P(1001, "in2_peak_db", "Input 2 peak", "dB", -120.0f, 6.0f, -120.0f, LIN, METER, 0.0f),
    P(1002, "mix_l_peak_db", "Mix left peak", "dB", -120.0f, 6.0f, -120.0f, LIN, METER, 0.0f),
    P(1003, "mix_r_peak_db", "Mix right peak", "dB", -120.0f, 6.0f, -120.0f, LIN, METER, 0.0f),
    P(1004, "in1_gr_db", "Input 1 gain reduction", "dB", -40.0f, 0.0f, 0.0f, LIN, METER, 0.0f),
    P(1005, "in2_gr_db", "Input 2 gain reduction", "dB", -40.0f, 0.0f, 0.0f, LIN, METER, 0.0f),
    P(1006, "spk_gr_db", "Speaker limiter gain reduction", "dB", -40.0f, 0.0f, 0.0f, LIN, METER,
      0.0f),
    P(1007, "hp_gr_db", "Headphone limiter gain reduction", "dB", -40.0f, 0.0f, 0.0f, LIN, METER,
      0.0f),
    P(1008, "cpu_load_pct", "Audio load", "%", 0.0f, 100.0f, 0.0f, LIN, METER, 0.0f),
    P(1009, "tempo_now_bpm", "Followed tempo", "BPM", 0.0f, 300.0f, 0.0f, LIN, METER, 0.0f),
};

#define TABLE_COUNT (sizeof(kTable) / sizeof(kTable[0]))
_Static_assert(TABLE_COUNT <= CTL_MAX_PARAMS, "raise CTL_MAX_PARAMS");

/* Each knob and its ownership mode parameter. */
static const uint16_t kKnobModes[][2] = {
    {306, 916}, {402, 915}, {500, 910}, {501, 911}, {502, 912}, {800, 913}, {801, 914},
};

size_t ctl_param_count(void) { return TABLE_COUNT; }

const CtlParamDesc *ctl_param_desc(size_t index) {
    return index < TABLE_COUNT ? &kTable[index] : NULL;
}

int32_t ctl_param_index_of(uint16_t id) {
    size_t lo = 0, hi = TABLE_COUNT;
    while (lo < hi) {
        const size_t mid = lo + (hi - lo) / 2u;
        if (kTable[mid].id < id) {
            lo = mid + 1u;
        } else {
            hi = mid;
        }
    }
    return (lo < TABLE_COUNT && kTable[lo].id == id) ? (int32_t)lo : -1;
}

int32_t ctl_param_find(const char *name, size_t len) {
    for (size_t i = 0; i < TABLE_COUNT; ++i) {
        const char *n = kTable[i].name;
        size_t k = 0;
        while (k < len && n[k] != '\0' && n[k] == name[k]) {
            ++k;
        }
        if (k == len && n[k] == '\0') {
            return (int32_t)i;
        }
    }
    return -1;
}

int32_t ctl_param_mode_index(size_t index) {
    if (index >= TABLE_COUNT) {
        return -1;
    }
    for (size_t i = 0; i < sizeof(kKnobModes) / sizeof(kKnobModes[0]); ++i) {
        if (kKnobModes[i][0] == kTable[index].id) {
            return ctl_param_index_of(kKnobModes[i][1]);
        }
    }
    return -1;
}
