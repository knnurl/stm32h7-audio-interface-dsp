/* The whole control stack as one object, for the PC only (ctl/src/ctl_host.c). */
#ifndef CTL_HOST_H
#define CTL_HOST_H

#include "ctl/ctl_flash.h"
#include "ctl/ctl_midi.h"
#include "ctl/ctl_preset.h"
#include "ctl/ctl_proto.h"
#include "ctl/ctl_tempo.h"

#include <stddef.h>
#include <stdint.h>

typedef struct CtlHost CtlHost;

size_t ctl_host_size(void);
void ctl_host_init(CtlHost *h, uint32_t sector_bytes);
void ctl_host_boot(CtlHost *h);
size_t ctl_host_take_output(CtlHost *h, char *dst, size_t cap);
CtlCore *ctl_host_core(CtlHost *h);
CtlPresetStore *ctl_host_store(CtlHost *h);
CtlFlashSim *ctl_host_sim(CtlHost *h);
CtlProto *ctl_host_proto(CtlHost *h);
CtlMidi *ctl_host_midi(CtlHost *h);
CtlTempo *ctl_host_tempo(CtlHost *h);
/* The main loop's work at now_us: the tempo follower, then the power-on record. */
void ctl_host_update(CtlHost *h, uint32_t now_us);
uint32_t ctl_host_dropped(const CtlHost *h);
void ctl_host_counters(const CtlHost *h, uint32_t out[8]);
size_t ctl_sizeof_update(void);
size_t ctl_sizeof_queue(void);

#endif
