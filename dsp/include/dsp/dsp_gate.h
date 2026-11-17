/* Noise gate with hysteresis and hold.
 *
 * Detector: a peak envelope (instant attack, `detector_release_ms` release) in dB.
 * State: it opens when the level reaches `open_db`; it closes only after the level has stayed
 * below `open_db - hysteresis_db` for `hold_ms`. Hysteresis stops chatter on a signal that hovers
 * at the threshold; the hold stops it closing between the notes of a phrase.
 * Gain: follows 1 (open) or `range_db` (closed, clamped to 0 dB or below) through a one-pole,
 * `attack_ms` when opening and `release_ms` when closing. (The Phil's Lab gate names these the
 * other way round; our names follow MATLAB and most hardware.)
 * The effective hold is `hold_ms` plus the time the detector's release takes to fall from the
 * signal's level to the close threshold. Thresholds are compared in the linear domain, so the
 * comparison is exact and costs no logarithm.
 *
 * Assumptions: mono; `in` and `out` may be the same buffer. Latency: 0 samples.
 * Cycles per sample (M7, 400 MHz): not yet measured.
 */
#ifndef DSP_GATE_H
#define DSP_GATE_H

#include "dsp/dsp_env.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    float open_db;
    float hysteresis_db;
    float hold_ms;
    float attack_ms;
    float release_ms;
    float range_db; /* Gain when closed, e.g. -80. */
    float detector_release_ms;
} DspGateParams;

typedef struct {
    DspGateParams params;
    float sample_rate_hz;
    DspEnvF32 detector;
    float close_db;
    float open_lin;  /* Thresholds as linear levels. */
    float close_lin;
    int32_t hold_samples;
    int32_t hold_left;
    int32_t open;
    uint32_t transitions; /* Open and close events since init: for tests and metering. */
    float gain;
    float closed_gain;
    float open_coef;
    float close_coef;
} DspGateF32;

void dsp_gate_f32_init(DspGateF32 *gate, float sample_rate_hz, const DspGateParams *params);
void dsp_gate_f32_set_params(DspGateF32 *gate, const DspGateParams *params);
void dsp_gate_f32_reset(DspGateF32 *gate); /* Closed, gain at the closed level. */
void dsp_gate_f32_process(DspGateF32 *gate, const float *in, float *out, size_t n_frames);

#endif
