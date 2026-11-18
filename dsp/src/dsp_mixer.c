#include "dsp/dsp_mixer.h"

#include <math.h>

void dsp_mixer_pan_gains(float pan, float *left, float *right) {
    const float p = pan < -1.0f ? -1.0f : (pan > 1.0f ? 1.0f : pan);
    const float t = (p + 1.0f) * 0.785398163f; /* pi / 4 */
    /* The ends and the centre exactly, whatever the C library's last bit. */
    if (p == -1.0f) {
        *left = 1.0f;
        *right = 0.0f;
    } else if (p == 1.0f) {
        *left = 0.0f;
        *right = 1.0f;
    } else if (p == 0.0f) {
        *left = 0.707106781f;
        *right = 0.707106781f;
    } else {
        *left = cosf(t);
        *right = sinf(t);
    }
}

static void targets(const DspMixerChannelF32 *c, float g[4]) {
    float l, r;
    dsp_mixer_pan_gains(c->pan, &l, &r);
    const float level = c->mute ? 0.0f : c->level;
    const float send = level * c->send; /* Post-level: the reverb follows the fader. */
    g[0] = level * l;
    g[1] = level * r;
    g[2] = send * l;
    g[3] = send * r;
}

int32_t dsp_mixer_f32_init(DspMixerF32 *mixer, float sample_rate_hz, int32_t n_channels,
                           float ramp_ms) {
    if (n_channels < 1 || n_channels > kDspMixerMaxChannels) {
        return -1;
    }
    mixer->sample_rate_hz = sample_rate_hz;
    mixer->n_channels = n_channels;
    mixer->ramp_samples = (int32_t)(ramp_ms * 0.001f * sample_rate_hz + 0.5f);
    for (int32_t c = 0; c < kDspMixerMaxChannels; ++c) {
        DspMixerChannelF32 *ch = &mixer->ch[c];
        ch->level = 1.0f;
        ch->pan = 0.0f;
        ch->send = 0.0f;
        ch->mute = 0;
        float g[4];
        targets(ch, g);
        for (int k = 0; k < 4; ++k) {
            dsp_ramp_jump(&ch->gain[k], g[k]);
        }
    }
    return 0;
}

void dsp_mixer_f32_reset(DspMixerF32 *mixer) {
    for (int32_t c = 0; c < kDspMixerMaxChannels; ++c) {
        for (int k = 0; k < 4; ++k) {
            dsp_ramp_jump(&mixer->ch[c].gain[k], mixer->ch[c].gain[k].target);
        }
    }
}

void dsp_mixer_f32_set_channel(DspMixerF32 *mixer, int32_t channel, float level, float pan,
                               float send, int32_t mute) {
    if (channel < 0 || channel >= mixer->n_channels) {
        return;
    }
    DspMixerChannelF32 *ch = &mixer->ch[channel];
    ch->level = level;
    ch->pan = pan;
    ch->send = send;
    ch->mute = mute != 0;
    float g[4];
    targets(ch, g);
    for (int k = 0; k < 4; ++k) {
        dsp_ramp_set(&ch->gain[k], g[k], mixer->ramp_samples);
    }
}

void dsp_mixer_f32_process(DspMixerF32 *mixer, const float *const *in, float *main_l,
                           float *main_r, float *send_l, float *send_r, size_t n_frames) {
    const int32_t with_send = send_l != NULL && send_r != NULL;
    for (size_t i = 0; i < n_frames; ++i) {
        main_l[i] = 0.0f;
        main_r[i] = 0.0f;
    }
    if (with_send) {
        for (size_t i = 0; i < n_frames; ++i) {
            send_l[i] = 0.0f;
            send_r[i] = 0.0f;
        }
    }
    for (int32_t c = 0; c < mixer->n_channels; ++c) {
        DspMixerChannelF32 *ch = &mixer->ch[c];
        DspRampF32 *g = ch->gain;
        const int32_t moving = dsp_ramp_moving(&g[0]) || dsp_ramp_moving(&g[1]) ||
                               dsp_ramp_moving(&g[2]) || dsp_ramp_moving(&g[3]);
        const float *x = in[c];
        if (x == NULL) {
            /* Silence: the ramps still advance, so a later connection finds them where the
             * clock says they are. */
            for (size_t i = 0; moving && i < n_frames; ++i) {
                for (int k = 0; k < 4; ++k) {
                    (void)dsp_ramp_next(&g[k]);
                }
            }
            continue;
        }
        if (!moving) {
            const float gl = g[0].cur, gr = g[1].cur, sl = g[2].cur, sr = g[3].cur;
            if (gl != 0.0f || gr != 0.0f) {
                for (size_t i = 0; i < n_frames; ++i) {
                    main_l[i] += gl * x[i];
                    main_r[i] += gr * x[i];
                }
            }
            if (with_send && (sl != 0.0f || sr != 0.0f)) {
                for (size_t i = 0; i < n_frames; ++i) {
                    send_l[i] += sl * x[i];
                    send_r[i] += sr * x[i];
                }
            }
            continue;
        }
        for (size_t i = 0; i < n_frames; ++i) {
            const float gl = dsp_ramp_next(&g[0]), gr = dsp_ramp_next(&g[1]);
            const float sl = dsp_ramp_next(&g[2]), sr = dsp_ramp_next(&g[3]);
            main_l[i] += gl * x[i];
            main_r[i] += gr * x[i];
            if (with_send) {
                send_l[i] += sl * x[i];
                send_r[i] += sr * x[i];
            }
        }
    }
}
