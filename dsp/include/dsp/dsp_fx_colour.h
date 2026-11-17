/* The effects that colour the whole signal (dry 0): sweep filter, overdrive, bit crusher.
 *
 * Sweep filter (DJ style), FX AMOUNT = position p in [0, 1]:
 *   |p - 0.5| <= 0.03   off: the output is the input (the dead zone the plan asks for, since
 *                       the pot has no centre detent);
 *   p < 0.47            low-pass, fc = 20 kHz x (50 / 20000)^((0.47 - p) / 0.47): 20 kHz at the
 *                       dead zone's edge down to 50 Hz at 0;
 *   p > 0.53            high-pass, fc = 20 Hz x (10000 / 20)^((p - 0.53) / 0.47).
 * Over the 0.07 of travel next to the dead zone the output fades from the input to the filter,
 * so entering or leaving the dead zone is continuous. Filter: dsp_svf, resonance Q in
 * [0.5, 8], coefficients every kDspFxSubBlock samples from the ramped position (Pade tan,
 * dsp_fast_exp2f).
 *
 * Overdrive, FX AMOUNT = drive, 0 to 36 dB:
 *   one-pole high-pass at 100 Hz (#153's cure for mud) -> optional bias for an asymmetric curve
 *   (0.3 / d added before tanh: even harmonics) -> dsp_saturate at 2x (batch 6) -> one-pole
 *   high-pass at 10 Hz (removes the bias's DC) -> one-pole low-pass, tone 0 to 1 = 1 kHz to
 *   12 kHz -> level compensation -> output level (dB).
 * Level compensation: a table, built at init, of the gain that keeps a -18 dBFS sine at the same
 * RMS through the symmetric curve at each whole dB of drive (37 entries, interpolated), so
 * turning the drive up changes the character more than the loudness.
 * Latency: 41 samples (the 2x oversampler): a cross-fade with the dry signal comb-filters for
 * its 30 ms, which is the slot's fade time. 2x, not 4x, since the budget round of 2026-11-17
 * (owner): it halves the cost; aliasing at 5 kHz -64 dB instead of -131 (b6_aliasing.md).
 *
 * Bit crusher, FX AMOUNT = amount a in [0, 1], applied to the `bits` and `rate` settings:
 *   effective bits = 16 + a (bits - 16), effective rate = fs (rate / fs)^a,
 * so a = 0 is 16 bits at the full rate. Rate reduction is a sample-and-hold driven by a phase
 * accumulator (no resampling filter: the aliasing is the sound). Quantisation rounds half away
 * from zero to steps of 2^-(bits - 1); optional TPDF dither of one step.
 *
 * Assumptions: stereo; any block size. Cycles: not yet measured.
 */
#ifndef DSP_FX_COLOUR_H
#define DSP_FX_COLOUR_H

#include "dsp/dsp_fx_common.h"
#include "dsp/dsp_saturate.h"
#include "dsp/dsp_svf.h"
#include "dsp/dsp_testsig.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspOverdriveTable = 37 };

typedef struct {
    float sample_rate_hz;
    float dry;
    DspSvfF32 svf[2];
    float q;
    DspRampF32 position;
} DspFxSweepF32;

typedef struct {
    float sample_rate_hz;
    float dry;
    DspSaturatorF32 sat[2];
    DspOnePoleF32 pre[2], dc[2], post[2];
    int32_t asymmetric;
    float level;          /* Linear. */
    float drive_db;       /* Applied to the saturators. */
    DspRampF32 amount;
    float comp[kDspOverdriveTable];
    float buf[kDspFxSubBlock];
} DspFxOverdriveF32;

typedef struct {
    float sample_rate_hz;
    float dry;
    float bits;     /* Setting, 1 to 16. */
    float rate_hz;  /* Setting. */
    int32_t dither;
    DspRampF32 amount;
    float phase;    /* Sample-and-hold phase, [0, 1). */
    float held[2];
    DspNoise noise;
    float rnd[4 * kDspFxSubBlock];
} DspFxCrusherF32;

void dsp_fx_sweep_f32_init(DspFxSweepF32 *fx, float sample_rate_hz);
void dsp_fx_sweep_f32_reset(DspFxSweepF32 *fx);
void dsp_fx_sweep_f32_set_amount(DspFxSweepF32 *fx, float position);
void dsp_fx_sweep_f32_set_resonance(DspFxSweepF32 *fx, float q);
/* The filter a position selects: mode (-1 off, 0 low-pass, 2 high-pass), corner and blend. */
void dsp_fx_sweep_map(float position, int32_t *mode, float *fc_hz, float *blend);
void dsp_fx_sweep_f32_process(DspFxSweepF32 *fx, const float *in_l, const float *in_r,
                              float *wet_l, float *wet_r, size_t n_frames);

void dsp_fx_overdrive_f32_init(DspFxOverdriveF32 *fx, float sample_rate_hz);
void dsp_fx_overdrive_f32_reset(DspFxOverdriveF32 *fx);
void dsp_fx_overdrive_f32_set_amount(DspFxOverdriveF32 *fx, float amount);
void dsp_fx_overdrive_f32_set_tone(DspFxOverdriveF32 *fx, float tone);
void dsp_fx_overdrive_f32_set_asymmetric(DspFxOverdriveF32 *fx, int32_t on);
void dsp_fx_overdrive_f32_set_level_db(DspFxOverdriveF32 *fx, float level_db);
float dsp_fx_overdrive_f32_latency(const DspFxOverdriveF32 *fx);
void dsp_fx_overdrive_f32_process(DspFxOverdriveF32 *fx, const float *in_l, const float *in_r,
                                  float *wet_l, float *wet_r, size_t n_frames);

void dsp_fx_crusher_f32_init(DspFxCrusherF32 *fx, float sample_rate_hz);
void dsp_fx_crusher_f32_reset(DspFxCrusherF32 *fx);
void dsp_fx_crusher_f32_set_amount(DspFxCrusherF32 *fx, float amount);
void dsp_fx_crusher_f32_set_bits(DspFxCrusherF32 *fx, float bits);
void dsp_fx_crusher_f32_set_rate(DspFxCrusherF32 *fx, float rate_hz);
void dsp_fx_crusher_f32_set_dither(DspFxCrusherF32 *fx, int32_t on);
void dsp_fx_crusher_f32_process(DspFxCrusherF32 *fx, const float *in_l, const float *in_r,
                                float *wet_l, float *wet_r, size_t n_frames);

#endif
