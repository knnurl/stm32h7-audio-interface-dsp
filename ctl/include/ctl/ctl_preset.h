/* Presets and the power-on record, as an append-only log in flash (docs/notes/preset_store.md).
 *
 * Slots 0 to 7 are presets (parameters with kCtlFlagPreset); slot 8 is the power-on record
 * (kCtlFlagPreset and kCtlFlagSetting), written CTL_PRESET_SAVE_DELAY_MS after the last change.
 * Values are stored by parameter id, so a newer firmware loads an older record: unknown ids are
 * ignored, missing ids take their default.
 *
 * Layout: two sectors. Each starts with a header word (magic, generation, CRC); the one with the
 * valid header and the higher generation holds the log. Records follow, each aligned to a flash
 * word: magic, slot, sequence number, length, count, CRC-32, then a 16-byte name and the
 * (id, value) entries. The last record of a slot with a good CRC wins; a torn or corrupted
 * record is skipped, so the slot falls back to its previous record, then to the defaults.
 * When the log is full, the latest good record of each slot is copied into the other sector,
 * whose header is written last: a power cut at any point leaves the old sector in charge.
 */
#ifndef CTL_PRESET_H
#define CTL_PRESET_H

#include "ctl/ctl_core.h"
#include "ctl/ctl_flash.h"

#include <stddef.h>
#include <stdint.h>

#define CTL_PRESET_SLOTS 8
#define CTL_PRESET_POWER_ON 8
#define CTL_PRESET_NAME_LEN 16
#define CTL_PRESET_SAVE_DELAY_MS 2000u
#define CTL_PRESET_HEADER_BYTES 16u
#define CTL_PRESET_RECORD_MAX                                                                      \
    ((CTL_PRESET_HEADER_BYTES + CTL_PRESET_NAME_LEN + 8u * CTL_MAX_PARAMS + CTL_FLASH_WORD - 1u) / \
     CTL_FLASH_WORD * CTL_FLASH_WORD)

typedef struct {
    CtlFlashOps flash;
    int32_t active; /* Sector holding the log; -1 before the first write. */
    uint32_t generation;
    uint32_t free_offset;
    uint32_t next_seq;
    uint8_t needs_compact; /* Unreadable bytes after the last record: compact before writing. */
    uint32_t writes;
    uint32_t compactions;
    uint32_t errors;
    uint8_t buf[CTL_PRESET_RECORD_MAX];
} CtlPresetStore;

/* Reads both sectors and finds the log. 0 on success (also when the flash is blank). */
int ctl_preset_mount(CtlPresetStore *store, const CtlFlashOps *flash);
/* Saves the parameters of `core` to a slot (0..8). 0 on success. */
int ctl_preset_save(CtlPresetStore *store, int slot, const char *name, size_t name_len,
                    const CtlCore *core);
/* Applies a slot to `core` (as source kCtlSrcPreset). 0 on success, -1 if the slot is empty. */
int ctl_preset_load(CtlPresetStore *store, int slot, CtlCore *core);
/* Name and sequence number of a slot's latest good record. 0 if it has one. `name` holds
 * CTL_PRESET_NAME_LEN + 1 bytes. */
int ctl_preset_info(CtlPresetStore *store, int slot, char *name, uint32_t *seq);
int ctl_preset_rename(CtlPresetStore *store, int slot, const char *name, size_t name_len);
/* At start-up: applies the power-on record if there is one; leaves the core clean. */
int ctl_preset_restore(CtlPresetStore *store, CtlCore *core);
/* Main loop: writes the power-on record once the settings have been still for the delay. */
void ctl_preset_tick(CtlPresetStore *store, CtlCore *core);
/* Bytes left in the active sector. */
uint32_t ctl_preset_free_bytes(const CtlPresetStore *store);

#endif
