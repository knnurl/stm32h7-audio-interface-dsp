#include "flash_store.h"

#include "board.h"

#include <string.h>

#define STORE_BASE 0x081C0000u /* Bank 2, sector 6. */
#define STORE_SECTOR_BYTES 0x20000u
#define STORE_FIRST_SECTOR FLASH_SECTOR_6

static uint32_t sector_address(uint32_t sector) { return STORE_BASE + sector * STORE_SECTOR_BYTES; }

static void invalidate(uint32_t address, uint32_t n) {
    SCB_InvalidateDCache_by_Addr((void *)(address & ~31u), (int32_t)(n + (address & 31u)));
}

static int store_read(void *ctx, uint32_t sector, uint32_t offset, void *dst, uint32_t n) {
    (void)ctx;
    if (sector > 1u || offset > STORE_SECTOR_BYTES || n > STORE_SECTOR_BYTES - offset) {
        return -1;
    }
    /* A double ECC error on a load is a precise bus fault. With FAULTMASK set and
     * CCR.BFHFNMIGN, the load completes with unknown data instead; the flag tells. FAULTMASK
     * also holds off the audio interrupt, so the copy goes in 64-byte pieces. */
    FLASH->CCR2 = FLASH_CCR_CLR_DBECCERR | FLASH_CCR_CLR_SNECCERR;
    const uint8_t *from = (const uint8_t *)(sector_address(sector) + offset);
    for (uint32_t i = 0; i < n; i += 64u) {
        const uint32_t piece = n - i < 64u ? n - i : 64u;
        __set_FAULTMASK(1u);
        SCB->CCR |= SCB_CCR_BFHFNMIGN_Msk;
        __DSB();
        __ISB();
        memcpy((uint8_t *)dst + i, from + i, piece);
        __DSB();
        SCB->CCR &= ~SCB_CCR_BFHFNMIGN_Msk;
        SCB->CFSR = SCB_CFSR_BUSFAULTSR_Msk; /* Clear any bus fault status the load left. */
        __set_FAULTMASK(0u);
    }
    if ((FLASH->SR2 & FLASH_SR_DBECCERR) != 0u) {
        FLASH->CCR2 = FLASH_CCR_CLR_DBECCERR | FLASH_CCR_CLR_SNECCERR;
        return -2;
    }
    return 0;
}

static int store_program(void *ctx, uint32_t sector, uint32_t offset, const void *src,
                         uint32_t n) {
    (void)ctx;
    if (sector > 1u || offset % CTL_FLASH_WORD != 0u || n % CTL_FLASH_WORD != 0u ||
        offset > STORE_SECTOR_BYTES || n > STORE_SECTOR_BYTES - offset) {
        return -1;
    }
    /* HAL_FLASH_Program reads the word as 32-bit values: copy into an aligned buffer. */
    uint32_t word[CTL_FLASH_WORD / 4u];
    int result = 0;
    HAL_FLASH_Unlock();
    for (uint32_t i = 0; i < n; i += CTL_FLASH_WORD) {
        memcpy(word, (const uint8_t *)src + i, CTL_FLASH_WORD);
        if (HAL_FLASH_Program(FLASH_TYPEPROGRAM_FLASHWORD, sector_address(sector) + offset + i,
                              (uint32_t)word) != HAL_OK) {
            result = -2;
            break;
        }
    }
    HAL_FLASH_Lock();
    invalidate(sector_address(sector) + offset, n);
    return result;
}

static int store_erase(void *ctx, uint32_t sector) {
    (void)ctx;
    if (sector > 1u) {
        return -1;
    }
    FLASH_EraseInitTypeDef erase = {0};
    erase.TypeErase = FLASH_TYPEERASE_SECTORS;
    erase.Banks = FLASH_BANK_2;
    erase.Sector = STORE_FIRST_SECTOR + sector;
    erase.NbSectors = 1u;
    erase.VoltageRange = FLASH_VOLTAGE_RANGE_3;
    uint32_t failed_sector = 0;
    HAL_FLASH_Unlock();
    const HAL_StatusTypeDef status = HAL_FLASHEx_Erase(&erase, &failed_sector);
    HAL_FLASH_Lock();
    invalidate(sector_address(sector), STORE_SECTOR_BYTES);
    return status == HAL_OK ? 0 : -2;
}

void flash_store_ops(CtlFlashOps *ops) {
    ops->ctx = NULL;
    ops->sector_bytes = STORE_SECTOR_BYTES;
    ops->read = store_read;
    ops->program = store_program;
    ops->erase = store_erase;
}
