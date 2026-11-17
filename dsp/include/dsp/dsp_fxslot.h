/* The effect slot: one of eight effects on the monitor mix, switched without clicks.
 *
 *   out = g_dry x + g_wet E(g_in x)
 * E is the active effect's wet output and `dry` its dry gain (dsp_fx_common.h). The three gains
 * move linearly over kDspFxSlotFadeMs (30 ms):
 *   on:                     g_in 1, g_wet 1, g_dry = the effect's dry gain;
 *   off, trails off:        g_wet 0, g_dry 1; the effect stops once g_wet reaches 0;
 *   off, trails on:         g_in 0, g_wet 1, g_dry 1, for effects with a dry path (echo,
 *                           chorus, flanger, phaser): the input is faded out of the effect and
 *                           its tail rings out; it stops after 0.5 s below -100 dBFS. Effects
 *                           without a dry path fade out as with trails off.
 *   change of effect:       the old one fades out (g_wet to 0), the delay memory it used is
 *                           cleared, the new one starts from cleared state and fades in.
 * A start fades g_in in as well as g_wet: a delay line's first output is then the faded-in
 * input, not the step of a signal arriving in an empty line.
 * Only one effect runs at a time, never two: the cycle budget (SPEC 3.4) counts the dearest
 * single effect. So a change is sequential, a fade out then a fade in, not a cross-fade.
 * Clearing is spread over blocks, kDspFxSlotClearPerChunk floats per chunk of up to
 * kDspFxSubBlock frames (the echo's 563 KB at 96 kHz would take about 0.2 ms in one go, longer
 * than a 16-frame block): about 12 ms for the full echo pool at 96 kHz, during which the slot
 * passes the dry signal. Turning on an effect whose memory is dirty clears it first too, so an
 * effect never replays audio from before it was last stopped.
 *
 * Memory: one caller-provided pool, shared by the echo, chorus and flanger (one runs at a time).
 * The echo takes all of it; its longest time follows from the pool's size.
 * Effect parameters other than the amount are set on the members directly (slot->echo, ...).
 *
 * Assumptions: stereo; any block size, processed in chunks of kDspFxSubBlock.
 * Latency: 0, except the overdrive's 46.5 samples while it runs. Cycles: not yet measured.
 */
#ifndef DSP_FXSLOT_H
#define DSP_FXSLOT_H

#include "dsp/dsp_fx_colour.h"
#include "dsp/dsp_fx_echo.h"
#include "dsp/dsp_fx_mod.h"
#include "dsp/dsp_fx_tremolo.h"

#include <stddef.h>
#include <stdint.h>

typedef enum {
    kDspFxEcho = 0,
    kDspFxChorus = 1,
    kDspFxFlanger = 2,
    kDspFxPhaser = 3,
    kDspFxTremolo = 4,
    kDspFxSweep = 5,
    kDspFxOverdrive = 6,
    kDspFxCrusher = 7,
    kDspFxCount = 8,
} DspFxId;

enum { kDspFxSlotClearPerChunk = 2048 };
#define DSP_FXSLOT_FADE_MS 30.0f
#define DSP_FXSLOT_QUIET 1e-5f

typedef struct {
    float sample_rate_hz;
    float *pool;
    int32_t pool_len;
    int32_t available[kDspFxCount];
    int32_t selected; /* What the control level asked for. */
    int32_t active;   /* What is loaded. */
    int32_t on;
    int32_t trails;
    float amount;
    int32_t running;   /* The active effect is being processed. */
    int32_t dirty_len; /* Floats of the pool to clear before the next start. */
    int32_t clear_pos;
    int32_t quiet;     /* Samples of tail below DSP_FXSLOT_QUIET. */
    int32_t fade;      /* Samples. */
    DspRampF32 g_in, g_wet, g_dry;
    float x_in[2][kDspFxSubBlock];
    float wet[2][kDspFxSubBlock];
    DspFxEchoF32 echo;
    DspFxChorusF32 chorus;
    DspFxFlangerF32 flanger;
    DspFxPhaserF32 phaser;
    DspFxTremoloF32 tremolo;
    DspFxSweepF32 sweep;
    DspFxOverdriveF32 overdrive;
    DspFxCrusherF32 crusher;
} DspFxSlotF32;

/* Returns 0, or -1 if the pool cannot hold the chorus and the flanger. The echo is available
 * when the pool holds at least 10 ms of it. Starts with the echo selected, off, trails on. */
int32_t dsp_fxslot_f32_init(DspFxSlotF32 *slot, float sample_rate_hz, float *pool,
                            int32_t pool_len);
void dsp_fxslot_f32_reset(DspFxSlotF32 *slot);
void dsp_fxslot_f32_select(DspFxSlotF32 *slot, int32_t id);
void dsp_fxslot_f32_set_on(DspFxSlotF32 *slot, int32_t on);
void dsp_fxslot_f32_set_trails(DspFxSlotF32 *slot, int32_t on);
void dsp_fxslot_f32_set_amount(DspFxSlotF32 *slot, float amount);
/* 1 while an effect is being processed (for metering and the CPU table). */
int32_t dsp_fxslot_f32_running(const DspFxSlotF32 *slot);
void dsp_fxslot_f32_process(DspFxSlotF32 *slot, const float *in_l, const float *in_r,
                            float *out_l, float *out_r, size_t n_frames);

#endif
