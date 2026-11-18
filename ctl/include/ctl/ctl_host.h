/* The whole control stack as one object, for the PC only (ctl/src/ctl_host.c). */
#ifndef CTL_HOST_H
#define CTL_HOST_H

#include "ctl/ctl_flash.h"
#include "ctl/ctl_midi.h"
#include "ctl/ctl_panel.h"
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

/* The panel input (batch 8d) for the tests: object sizes, and a pot or a button run over a whole
 * stream in one call (one reading or sample per millisecond). ctl_pot_run returns the number of
 * reports; travel[i] holds the travel last reported after reading i, reported[i] 1 where it
 * changed. */
size_t ctl_sizeof_pot(void);
size_t ctl_sizeof_button(void);
size_t ctl_sizeof_double(void);
size_t ctl_sizeof_panel(void);
size_t ctl_pot_run(CtlPot *pot, const uint32_t *sums, size_t n, float *travel, uint8_t *reported);
uint32_t ctl_panel_refused(const CtlPanel *panel);
void ctl_button_run(CtlButton *b, const uint8_t *closed, size_t n, uint8_t *events);

#endif
