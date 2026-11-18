/* The preset store's flash (ctl_flash.h) on the STM32H755: the last two 128 KB sectors of flash
 * bank 2 (sectors 6 and 7, 0x081C0000 and 0x081E0000). The M4's linker script stops short of
 * them. The M7 runs from bank 1, so erasing and programming bank 2 does not stall its fetches
 * [Verify read-while-write across banks, SPEC V17].
 *
 * Main loop only: an erase blocks for up to about 2 s [Verify against the datasheet], a flash word
 * program for tens of microseconds. Never from the audio interrupt.
 *
 * Reads go through the AXI bus and the D-cache: the cache lines of a sector are invalidated after
 * every erase and program. A word torn by a power cut can fail its ECC check; the read path
 * masks the bus fault and reports the double-error flag as a failed read, so a torn record is
 * skipped instead of faulting at every start-up (docs/notes/preset_store.md). Shown on the board
 * 2026-11-18 with resets in the middle of writes (tools/torn_write_test.py, SPEC V18).
 */
#ifndef FLASH_STORE_H
#define FLASH_STORE_H

#include "ctl/ctl_flash.h"

void flash_store_ops(CtlFlashOps *ops);
/* Reads since start-up that met a corrected single-bit ECC error, and an uncorrectable one. The
 * preset store's own `errors` counts failed programs and erases only, not these. */
void flash_store_ecc_counts(uint32_t *single, uint32_t *dbl);

#endif
