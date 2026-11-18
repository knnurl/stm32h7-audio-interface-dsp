/* Monitor mixer: mono input channels into a stereo main bus and a stereo send bus (the reverb's).
 *
 * Per channel: level (linear), pan p in [-1, 1], send (linear) and mute. Its four gains:
 *   main L = level cos(t),  main R = level sin(t),  t = (p + 1) pi / 4
 *   send L = level send cos(t),   send R = level send sin(t)
 * A constant-power pan: -3.01 dB to each side at the centre, unity on the hard side, and the
 * power (L^2 + R^2) the same at every position. The send is post-pan and post-level: turning a
 * channel down turns its reverb down with it, so the wet and dry balance stays. A stereo source
 * is two channels panned -1 and +1, so it passes at unity. Muted, all four gains are 0.
 * Every gain moves linearly to a new value over the ramp time, from wherever it is, so no change
 * clicks; the gains are computed at the control level (cosf, sinf), never per sample.
 *
 * Assumptions: up to kDspMixerMaxChannels channels; the outputs are overwritten, not added to;
 * an input pointer may be NULL (an unconnected channel, read as silence); a channel whose four
 * gains are 0 and still costs nothing. Inputs and outputs must not overlap.
 * Latency: 0 samples. Cycles: self-test case mixer_f32.
 */
#ifndef DSP_MIXER_H
#define DSP_MIXER_H

#include "dsp/dsp_fx_common.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspMixerMaxChannels = 8 };

typedef struct {
    float level;
    float pan;
    float send;
    int32_t mute;
    DspRampF32 gain[4]; /* main L, main R, send L, send R. */
} DspMixerChannelF32;

typedef struct {
    float sample_rate_hz;
    int32_t ramp_samples;
    int32_t n_channels;
    DspMixerChannelF32 ch[kDspMixerMaxChannels];
} DspMixerF32;

/* The pan law: the left and right gains for a pan position (clamped to [-1, 1]). */
void dsp_mixer_pan_gains(float pan, float *left, float *right);

/* Every channel at level 1, centre, send 0, not muted, settled. Returns 0, or -1 when
 * n_channels is outside 1 to kDspMixerMaxChannels. */
int32_t dsp_mixer_f32_init(DspMixerF32 *mixer, float sample_rate_hz, int32_t n_channels,
                           float ramp_ms);
/* Every gain jumps to its target. */
void dsp_mixer_f32_reset(DspMixerF32 *mixer);
/* Sets one channel; the gains ramp from where they are. Ignored for a channel out of range. */
void dsp_mixer_f32_set_channel(DspMixerF32 *mixer, int32_t channel, float level, float pan,
                               float send, int32_t mute);
/* in[c] is channel c's block (or NULL). send_l and send_r may both be NULL: no send bus. */
void dsp_mixer_f32_process(DspMixerF32 *mixer, const float *const *in, float *main_l,
                           float *main_r, float *send_l, float *send_r, size_t n_frames);

#endif
