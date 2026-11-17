#include "dsp/dsp_fxslot.h"

#include <math.h>

static int32_t mem_of(const DspFxSlotF32 *slot, int32_t id) {
    switch (id) {
    case kDspFxEcho:
        return 2 * (slot->pool_len / 2);
    case kDspFxChorus:
        return dsp_fx_chorus_f32_mem_needed(slot->sample_rate_hz);
    case kDspFxFlanger:
        return dsp_fx_flanger_f32_mem_needed(slot->sample_rate_hz);
    default:
        return 0;
    }
}

static float dry_of(const DspFxSlotF32 *slot, int32_t id) {
    switch (id) {
    case kDspFxEcho:
        return slot->echo.dry;
    case kDspFxChorus:
        return slot->chorus.dry;
    case kDspFxFlanger:
        return slot->flanger.dry;
    case kDspFxPhaser:
        return slot->phaser.dry;
    case kDspFxTremolo:
        return slot->tremolo.dry;
    case kDspFxSweep:
        return slot->sweep.dry;
    case kDspFxOverdrive:
        return slot->overdrive.dry;
    default:
        return slot->crusher.dry;
    }
}

/* Clears the effect's filters and rewinds its delay lines; the pool is cleared by the slot. */
static void reset_effect(DspFxSlotF32 *slot, int32_t id) {
    switch (id) {
    case kDspFxEcho:
        dsp_fx_echo_f32_reset(&slot->echo, 0);
        break;
    case kDspFxChorus:
        dsp_fx_chorus_f32_reset(&slot->chorus, 0);
        break;
    case kDspFxFlanger:
        dsp_fx_flanger_f32_reset(&slot->flanger, 0);
        break;
    case kDspFxPhaser:
        dsp_fx_phaser_f32_reset(&slot->phaser);
        break;
    case kDspFxTremolo:
        dsp_fx_tremolo_f32_reset(&slot->tremolo);
        break;
    case kDspFxSweep:
        dsp_fx_sweep_f32_reset(&slot->sweep);
        break;
    case kDspFxOverdrive:
        dsp_fx_overdrive_f32_reset(&slot->overdrive);
        break;
    default:
        dsp_fx_crusher_f32_reset(&slot->crusher);
        break;
    }
}

static void amount_effect(DspFxSlotF32 *slot, int32_t id, float a) {
    switch (id) {
    case kDspFxEcho:
        dsp_fx_echo_f32_set_amount(&slot->echo, a);
        break;
    case kDspFxChorus:
        dsp_fx_chorus_f32_set_amount(&slot->chorus, a);
        break;
    case kDspFxFlanger:
        dsp_fx_flanger_f32_set_amount(&slot->flanger, a);
        break;
    case kDspFxPhaser:
        dsp_fx_phaser_f32_set_amount(&slot->phaser, a);
        break;
    case kDspFxTremolo:
        dsp_fx_tremolo_f32_set_amount(&slot->tremolo, a);
        break;
    case kDspFxSweep:
        dsp_fx_sweep_f32_set_amount(&slot->sweep, a);
        break;
    case kDspFxOverdrive:
        dsp_fx_overdrive_f32_set_amount(&slot->overdrive, a);
        break;
    default:
        dsp_fx_crusher_f32_set_amount(&slot->crusher, a);
        break;
    }
}

static void process_effect(DspFxSlotF32 *slot, size_t n) {
    const float *il = slot->x_in[0], *ir = slot->x_in[1];
    float *wl = slot->wet[0], *wr = slot->wet[1];
    switch (slot->active) {
    case kDspFxEcho:
        dsp_fx_echo_f32_process(&slot->echo, il, ir, wl, wr, n);
        break;
    case kDspFxChorus:
        dsp_fx_chorus_f32_process(&slot->chorus, il, ir, wl, wr, n);
        break;
    case kDspFxFlanger:
        dsp_fx_flanger_f32_process(&slot->flanger, il, ir, wl, wr, n);
        break;
    case kDspFxPhaser:
        dsp_fx_phaser_f32_process(&slot->phaser, il, ir, wl, wr, n);
        break;
    case kDspFxTremolo:
        dsp_fx_tremolo_f32_process(&slot->tremolo, il, ir, wl, wr, n);
        break;
    case kDspFxSweep:
        dsp_fx_sweep_f32_process(&slot->sweep, il, ir, wl, wr, n);
        break;
    case kDspFxOverdrive:
        dsp_fx_overdrive_f32_process(&slot->overdrive, il, ir, wl, wr, n);
        break;
    default:
        dsp_fx_crusher_f32_process(&slot->crusher, il, ir, wl, wr, n);
        break;
    }
}

int32_t dsp_fxslot_f32_init(DspFxSlotF32 *slot, float sample_rate_hz, float *pool,
                            int32_t pool_len) {
    slot->sample_rate_hz = sample_rate_hz;
    slot->pool = pool;
    slot->pool_len = pool != NULL && pool_len > 0 ? pool_len : 0;
    for (int32_t i = 0; i < kDspFxCount; ++i) {
        slot->available[i] = 1;
    }
    /* Each delay effect is initialised on the shared pool; the last one to clear it wins, which
     * is harmless because the slot clears before every start. */
    slot->available[kDspFxEcho] =
        dsp_fx_echo_f32_init(&slot->echo, sample_rate_hz, pool, slot->pool_len) == 0;
    const int32_t ok_chorus =
        dsp_fx_chorus_f32_init(&slot->chorus, sample_rate_hz, pool, slot->pool_len) == 0;
    const int32_t ok_flanger =
        dsp_fx_flanger_f32_init(&slot->flanger, sample_rate_hz, pool, slot->pool_len) == 0;
    slot->available[kDspFxChorus] = ok_chorus;
    slot->available[kDspFxFlanger] = ok_flanger;
    dsp_fx_phaser_f32_init(&slot->phaser, sample_rate_hz);
    dsp_fx_tremolo_f32_init(&slot->tremolo, sample_rate_hz);
    dsp_fx_sweep_f32_init(&slot->sweep, sample_rate_hz);
    dsp_fx_overdrive_f32_init(&slot->overdrive, sample_rate_hz);
    dsp_fx_crusher_f32_init(&slot->crusher, sample_rate_hz);
    slot->fade = (int32_t)(DSP_FXSLOT_FADE_MS * 0.001f * sample_rate_hz);
    slot->selected = slot->active = kDspFxEcho;
    slot->on = 0;
    slot->trails = 1;
    slot->amount = 0.5f;
    dsp_fxslot_f32_reset(slot);
    return ok_chorus && ok_flanger ? 0 : -1;
}

void dsp_fxslot_f32_reset(DspFxSlotF32 *slot) {
    slot->running = 0;
    slot->dirty_len = slot->pool_len; /* Unknown content: clear before the first start. */
    slot->clear_pos = 0;
    slot->quiet = 0;
    dsp_ramp_jump(&slot->g_in, 1.0f);
    dsp_ramp_jump(&slot->g_wet, 0.0f);
    dsp_ramp_jump(&slot->g_dry, 1.0f);
    slot->active = slot->selected;
    reset_effect(slot, slot->active);
}

void dsp_fxslot_f32_select(DspFxSlotF32 *slot, int32_t id) {
    if (id >= 0 && id < kDspFxCount && slot->available[id]) {
        slot->selected = id;
    }
}

void dsp_fxslot_f32_set_on(DspFxSlotF32 *slot, int32_t on) { slot->on = on != 0; }

void dsp_fxslot_f32_set_trails(DspFxSlotF32 *slot, int32_t on) { slot->trails = on != 0; }

void dsp_fxslot_f32_set_amount(DspFxSlotF32 *slot, float amount) {
    slot->amount = amount;
    amount_effect(slot, slot->active, amount);
}

int32_t dsp_fxslot_f32_running(const DspFxSlotF32 *slot) { return slot->running; }

/* One bounded step of clearing. Returns 1 while there is more to clear. */
static int32_t clear_step(DspFxSlotF32 *slot) {
    if (slot->dirty_len <= 0) {
        return 0;
    }
    int32_t end = slot->clear_pos + kDspFxSlotClearPerChunk;
    if (end > slot->dirty_len) {
        end = slot->dirty_len;
    }
    for (int32_t i = slot->clear_pos; i < end; ++i) {
        slot->pool[i] = 0.0f;
    }
    slot->clear_pos = end;
    if (end >= slot->dirty_len) {
        slot->dirty_len = 0;
        slot->clear_pos = 0;
        return 0;
    }
    return 1;
}

static int32_t faded_out(const DspRampF32 *r) { return r->cur == 0.0f && !dsp_ramp_moving(r); }

/* Decides the gains' targets at the start of a chunk; starts and stops the effect. */
static void update(DspFxSlotF32 *slot) {
    const int32_t fade = slot->fade;
    if (slot->selected != slot->active) {
        if (slot->running) {
            dsp_ramp_set(&slot->g_wet, 0.0f, fade);
            dsp_ramp_set(&slot->g_dry, 1.0f, fade);
            if (faded_out(&slot->g_wet)) {
                slot->running = 0;
            }
            return;
        }
        if (clear_step(slot)) {
            return;
        }
        slot->active = slot->selected;
        reset_effect(slot, slot->active);
        amount_effect(slot, slot->active, slot->amount);
    }
    const float dry = dry_of(slot, slot->active);
    if (slot->on) {
        if (!slot->running) {
            if (clear_step(slot)) {
                return;
            }
            reset_effect(slot, slot->active);
            slot->running = 1;
            slot->quiet = 0;
            slot->dirty_len = mem_of(slot, slot->active);
            slot->clear_pos = 0;
            /* The input fades in too. With it at full gain at once, a delay effect's cleared
             * line delivers the onset of the delayed signal as a step 10 to 500 ms later, in the
             * middle of the wet fade: a click (measured, test_switching_makes_no_click). */
            dsp_ramp_jump(&slot->g_in, 0.0f);
            dsp_ramp_jump(&slot->g_wet, 0.0f);
        }
        dsp_ramp_set(&slot->g_in, 1.0f, fade);
        dsp_ramp_set(&slot->g_wet, 1.0f, fade);
        dsp_ramp_set(&slot->g_dry, dry, fade);
        return;
    }
    if (!slot->running) {
        return;
    }
    if (slot->trails && dry > 0.0f) {
        dsp_ramp_set(&slot->g_in, 0.0f, fade);
        dsp_ramp_set(&slot->g_wet, 1.0f, fade);
        dsp_ramp_set(&slot->g_dry, 1.0f, fade);
        if (slot->quiet >= (int32_t)(0.5f * slot->sample_rate_hz)) {
            slot->running = 0;
            dsp_ramp_jump(&slot->g_wet, 0.0f);
        }
    } else {
        dsp_ramp_set(&slot->g_wet, 0.0f, fade);
        dsp_ramp_set(&slot->g_dry, 1.0f, fade);
        if (faded_out(&slot->g_wet)) {
            slot->running = 0;
        }
    }
}

void dsp_fxslot_f32_process(DspFxSlotF32 *slot, const float *in_l, const float *in_r,
                            float *out_l, float *out_r, size_t n_frames) {
    for (size_t start = 0; start < n_frames; start += kDspFxSubBlock) {
        const size_t n = n_frames - start < kDspFxSubBlock ? n_frames - start : kDspFxSubBlock;
        update(slot);
        const float *xl = in_l + start, *xr = in_r + start;
        if (slot->running) {
            for (size_t i = 0; i < n; ++i) {
                const float g = dsp_ramp_next(&slot->g_in);
                slot->x_in[0][i] = g * xl[i];
                slot->x_in[1][i] = g * xr[i];
            }
            process_effect(slot, n);
        } else {
            for (size_t i = 0; i < n; ++i) {
                slot->wet[0][i] = slot->wet[1][i] = 0.0f;
            }
        }
        float peak = 0.0f;
        for (size_t i = 0; i < n; ++i) {
            const float gw = dsp_ramp_next(&slot->g_wet);
            const float gd = dsp_ramp_next(&slot->g_dry);
            const float wl = slot->wet[0][i], wr = slot->wet[1][i];
            out_l[start + i] = gd * xl[i] + gw * wl;
            out_r[start + i] = gd * xr[i] + gw * wr;
            const float al = fabsf(wl), ar = fabsf(wr);
            peak = al > peak ? al : peak;
            peak = ar > peak ? ar : peak;
        }
        slot->quiet = peak < DSP_FXSLOT_QUIET ? slot->quiet + (int32_t)n : 0;
    }
}
