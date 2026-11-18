/* The parameter registry: every value the device exposes, declared once in
 * ctl/src/ctl_param_table.c (docs/notes/ctl_registry.md).
 *
 * A parameter has a stable numeric id (never reused: a removed parameter keeps its id
 * reserved), a snake_case name used by the protocol, a sentence-case label, a unit, a range, a
 * default, a curve that maps a knob or MIDI position (0 to 1) onto the range, a smoothing time
 * for the audio side, and flags. Values are floats in engineering units, clamped on every write.
 *
 * Hardware-free C11: no allocation, no stdio, no global mutable state (the table is const).
 */
#ifndef CTL_PARAMS_H
#define CTL_PARAMS_H

#include <stddef.h>
#include <stdint.h>

/* Capacity of every per-parameter array. The table's size is checked against it at compile
 * time. */
#define CTL_MAX_PARAMS 192

/* Ids 910 to 919 are the knob ownership modes (ctl_param_mode_index). */
#define CTL_ID_MODE_FIRST 910u
#define CTL_ID_MODE_LAST 919u

typedef enum {
    kCtlCurveLinear = 0, /* v = min + x (max - min) */
    kCtlCurveLog = 1,    /* v = min (max / min)^x; min > 0. Frequencies, times, ratios. */
    kCtlCurveVolume = 2, /* v = max + 60 log10(x) dB, floored at min; min means silence */
    kCtlCurveStep = 3,   /* integers min..max: switches and selectors */
} CtlCurve;

enum {
    kCtlFlagKnob = 1u << 0,     /* a potentiometer on the panel: knob ownership applies */
    kCtlFlagButton = 1u << 1,   /* set by a panel button */
    kCtlFlagPreset = 1u << 2,   /* saved in presets and in the power-on record */
    kCtlFlagSetting = 1u << 3,  /* a device setting: saved in the power-on record only */
    kCtlFlagReadOnly = 1u << 4, /* a meter or status: written only by the device */
};

typedef struct {
    uint16_t id;
    uint8_t curve; /* CtlCurve */
    uint8_t flags;
    const char *name;
    const char *label;
    const char *unit; /* "" when dimensionless */
    float min;
    float max;
    float def;
    float smooth_ms; /* For the audio side; 0 means apply at once. */
} CtlParamDesc;

size_t ctl_param_count(void);
/* NULL when index is out of range. */
const CtlParamDesc *ctl_param_desc(size_t index);
/* Index of the parameter with this name (not NUL-terminated: `len` bytes), or -1. */
int32_t ctl_param_find(const char *name, size_t len);
/* Index of the parameter with this id, or -1. */
int32_t ctl_param_index_of(uint16_t id);
/* For a parameter with kCtlFlagKnob: the index of its ownership mode parameter (0 knob wins,
 * 1 PC wins). -1 for any other parameter. */
int32_t ctl_param_mode_index(size_t index);

/* Clamps to the range; NaN gives the default; step parameters round to the nearest integer. */
float ctl_param_clamp(const CtlParamDesc *desc, float value);
/* Position 0..1 to value along the curve (clamped), and back. */
float ctl_param_from_norm(const CtlParamDesc *desc, float x);
float ctl_param_to_norm(const CtlParamDesc *desc, float value);

/* MIDI 7-bit value to position: 0 gives 0, 64 gives exactly 0.5, 127 gives 1, so a centred
 * parameter (the tone gains) is flat at 64. And back, rounded. */
float ctl_midi7_to_norm(uint8_t value);
uint8_t ctl_norm_to_midi7(float x);

#endif
