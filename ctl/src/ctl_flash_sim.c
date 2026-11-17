/* Flash simulator for the PC tests. Models what the preset store depends on: erased bytes read
 * 0xFF; a flash word is programmed once between erases (a second program is refused, as the H7
 * refuses it); a power cut can tear a write at any byte or interrupt an erase. A torn H7 word
 * can also read back with an ECC error rather than mixed bytes; that case belongs to the
 * firmware's read path (docs/notes/preset_store.md). */
#include "ctl/ctl_flash.h"

#include <string.h>

void ctl_flash_sim_init(CtlFlashSim *sim, uint32_t sector_bytes) {
    memset(sim, 0, sizeof(*sim));
    if (sector_bytes > CTL_FLASH_SIM_MAX_SECTOR) {
        sector_bytes = CTL_FLASH_SIM_MAX_SECTOR;
    }
    sim->sector_bytes = sector_bytes;
    memset(sim->mem, 0xFF, sizeof(sim->mem));
    sim->bytes_left = -1;
}

static int sim_read(void *ctx, uint32_t sector, uint32_t offset, void *dst, uint32_t n) {
    CtlFlashSim *sim = (CtlFlashSim *)ctx;
    if (sim->dead || sector > 1u || offset > sim->sector_bytes || n > sim->sector_bytes - offset) {
        return -1;
    }
    memcpy(dst, &sim->mem[sector][offset], n);
    return 0;
}

static int sim_program(void *ctx, uint32_t sector, uint32_t offset, const void *src, uint32_t n) {
    CtlFlashSim *sim = (CtlFlashSim *)ctx;
    if (sim->dead) {
        return -1;
    }
    if (sector > 1u || offset % CTL_FLASH_WORD != 0u || n % CTL_FLASH_WORD != 0u ||
        offset > sim->sector_bytes || n > sim->sector_bytes - offset) {
        ++sim->refused;
        return -2;
    }
    uint8_t *mem = &sim->mem[sector][offset];
    for (uint32_t i = 0; i < n; ++i) {
        if (mem[i] != 0xFFu) {
            ++sim->refused;
            return -3;
        }
    }
    const uint8_t *s = (const uint8_t *)src;
    for (uint32_t i = 0; i < n; ++i) {
        if (sim->bytes_left == 0) {
            sim->dead = 1;
            return -4;
        }
        mem[i] = s[i];
        ++sim->programmed;
        if (sim->bytes_left > 0) {
            --sim->bytes_left;
        }
    }
    return 0;
}

static int sim_erase(void *ctx, uint32_t sector) {
    CtlFlashSim *sim = (CtlFlashSim *)ctx;
    if (sim->dead || sector > 1u) {
        return -1;
    }
    ++sim->erases[sector];
    if (sim->cut_during_erase) {
        memset(sim->mem[sector], 0xFF, sim->sector_bytes / 2u);
        sim->cut_during_erase = 0;
        sim->dead = 1;
        return -4;
    }
    memset(sim->mem[sector], 0xFF, sim->sector_bytes);
    return 0;
}

void ctl_flash_sim_ops(CtlFlashSim *sim, CtlFlashOps *ops) {
    ops->ctx = sim;
    ops->sector_bytes = sim->sector_bytes;
    ops->read = sim_read;
    ops->program = sim_program;
    ops->erase = sim_erase;
}

void ctl_flash_sim_cut_after(CtlFlashSim *sim, int64_t bytes) { sim->bytes_left = bytes; }

void ctl_flash_sim_cut_next_erase(CtlFlashSim *sim) { sim->cut_during_erase = 1; }

void ctl_flash_sim_power_on(CtlFlashSim *sim) {
    sim->dead = 0;
    sim->bytes_left = -1;
    sim->cut_during_erase = 0;
}

uint8_t *ctl_flash_sim_mem(CtlFlashSim *sim, uint32_t sector) {
    return sector <= 1u ? sim->mem[sector] : NULL;
}
