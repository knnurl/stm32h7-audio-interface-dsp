/* A whole control stack in one object, for the PC: the tests, the fuzz driver and
 * `tools/ctl.py --sim` use it as a device without hardware. Not built into the firmware.
 * Python sees it as an opaque buffer of ctl_host_size() bytes and reaches the parts through the
 * accessors, so no structure is mirrored in ctypes. */
#include "ctl/ctl_host.h"

#include <string.h>

#define HOST_OUT_BYTES 65536u

struct CtlHost {
    CtlFlashSim sim;
    CtlFlashOps ops;
    CtlPresetStore store;
    CtlCore core;
    CtlProto proto;
    CtlMidi midi;
    CtlTempo tempo;
    char out[HOST_OUT_BYTES];
    size_t out_len;
    uint32_t out_dropped;
};

static void host_write(void *ctx, const char *line, size_t len) {
    CtlHost *h = (CtlHost *)ctx;
    if (h->out_len + len + 1u > HOST_OUT_BYTES) {
        ++h->out_dropped;
        return;
    }
    memcpy(h->out + h->out_len, line, len);
    h->out_len += len;
    h->out[h->out_len++] = '\n';
}

size_t ctl_host_size(void) { return sizeof(CtlHost); }

/* Start-up as the firmware does it: mount the store, apply the power-on record, then hand every
 * value to the audio level. The flash keeps its contents across calls (a reboot). */
void ctl_host_boot(CtlHost *h) {
    ctl_core_init(&h->core);
    ctl_preset_mount(&h->store, &h->ops);
    (void)ctl_preset_restore(&h->store, &h->core);
    ctl_core_sync_audio(&h->core);
    ctl_proto_init(&h->proto, &h->core, &h->store, host_write, h, "host", 0x00C0FFEEu);
    ctl_midi_init(&h->midi, &h->core, &h->store);
    ctl_tempo_init(&h->tempo);
    h->midi.realtime = ctl_tempo_midi;
    h->midi.realtime_ctx = &h->tempo;
    h->proto.tempo = &h->tempo;
    h->out_len = 0;
}

/* A fresh device with blank flash of the given sector size. */
void ctl_host_init(CtlHost *h, uint32_t sector_bytes) {
    memset(h, 0, sizeof(*h));
    ctl_flash_sim_init(&h->sim, sector_bytes);
    ctl_flash_sim_ops(&h->sim, &h->ops);
    ctl_host_boot(h);
}

size_t ctl_host_take_output(CtlHost *h, char *dst, size_t cap) {
    size_t n = h->out_len < cap ? h->out_len : cap;
    memcpy(dst, h->out, n);
    memmove(h->out, h->out + n, h->out_len - n);
    h->out_len -= n;
    return n;
}

CtlCore *ctl_host_core(CtlHost *h) { return &h->core; }
CtlPresetStore *ctl_host_store(CtlHost *h) { return &h->store; }
CtlFlashSim *ctl_host_sim(CtlHost *h) { return &h->sim; }
CtlProto *ctl_host_proto(CtlHost *h) { return &h->proto; }
CtlMidi *ctl_host_midi(CtlHost *h) { return &h->midi; }
CtlTempo *ctl_host_tempo(CtlHost *h) { return &h->tempo; }

void ctl_host_update(CtlHost *h, uint32_t now_us) {
    ctl_core_set_time(&h->core, now_us / 1000u);
    ctl_tempo_update(&h->tempo, &h->core, now_us);
    ctl_preset_tick(&h->store, &h->core);
}
uint32_t ctl_host_dropped(const CtlHost *h) { return h->out_dropped; }

/* MIDI and tap counters: clocks, starts, stops, continues, cc_in, cc_unmapped, sysex_skipped,
 * taps. */
void ctl_host_counters(const CtlHost *h, uint32_t out[8]) {
    out[0] = h->midi.clocks;
    out[1] = h->midi.starts;
    out[2] = h->midi.stops;
    out[3] = h->midi.continues;
    out[4] = h->midi.cc_in;
    out[5] = h->midi.cc_unmapped;
    out[6] = h->midi.sysex_skipped;
    out[7] = h->core.taps;
}

/* Sizes, for the few structures Python does mirror (tests/unit/test_ctl_params.py). */
size_t ctl_sizeof_update(void) { return sizeof(CtlUpdate); }
size_t ctl_sizeof_queue(void) { return sizeof(CtlQueue); }
