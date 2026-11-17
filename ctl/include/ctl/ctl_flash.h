/* The flash the preset store writes to: two sectors, programmed in flash words of
 * CTL_FLASH_WORD bytes, each word programmed at most once between erases (the STM32H7 keeps ECC
 * per 256-bit word, so a word cannot be programmed twice). The firmware implements it for the
 * last two sectors of flash bank 2 (fw/cm7/src/flash_store.c); the PC tests use the simulator.
 */
#ifndef CTL_FLASH_H
#define CTL_FLASH_H

#include <stdint.h>

#define CTL_FLASH_WORD 32u

typedef struct {
    void *ctx;
    uint32_t sector_bytes;
    /* Each returns 0 on success. Offsets and lengths for program are multiples of
     * CTL_FLASH_WORD; read takes any. */
    int (*read)(void *ctx, uint32_t sector, uint32_t offset, void *dst, uint32_t n);
    int (*program)(void *ctx, uint32_t sector, uint32_t offset, const void *src, uint32_t n);
    int (*erase)(void *ctx, uint32_t sector);
} CtlFlashOps;

/* ---- Simulator, for the PC tests (not built into the firmware) ---------------------------- */

#define CTL_FLASH_SIM_MAX_SECTOR (128u * 1024u)

typedef struct {
    uint8_t mem[2][CTL_FLASH_SIM_MAX_SECTOR];
    uint32_t sector_bytes;
    int64_t bytes_left;    /* Bytes that may still be programmed before the power fails; -1 none. */
    int cut_during_erase;  /* The next erase is interrupted half way, then the power fails. */
    int dead;              /* The power has failed: every call fails until power_on. */
    uint64_t programmed;   /* Bytes programmed, all time. */
    uint32_t erases[2];
    uint32_t refused;      /* Programs refused: misaligned, or the words were not erased. */
} CtlFlashSim;

void ctl_flash_sim_init(CtlFlashSim *sim, uint32_t sector_bytes);
void ctl_flash_sim_ops(CtlFlashSim *sim, CtlFlashOps *ops);
/* The power fails after `bytes` more bytes are programmed (a write is torn at that byte). */
void ctl_flash_sim_cut_after(CtlFlashSim *sim, int64_t bytes);
void ctl_flash_sim_cut_next_erase(CtlFlashSim *sim);
/* Power back: the flash keeps what was written; no cut is pending. */
void ctl_flash_sim_power_on(CtlFlashSim *sim);
uint8_t *ctl_flash_sim_mem(CtlFlashSim *sim, uint32_t sector);

#endif
