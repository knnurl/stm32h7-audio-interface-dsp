/* The Cortex-M4, parked. It puts its domain (D2) into stop mode and waits there for the
 * Cortex-M7 to release hardware semaphore 0, which the M7 does not do until batch 11 gives this
 * core work. No option bytes are involved: both cores boot, and this one goes to sleep.
 *
 * The sequence is ST's (the NUCLEO-H745ZI-Q BootCM4_CM7 template). While this core sleeps, the
 * D2 peripherals the M7 has enabled for itself keep running [Verify on the board: SPEC V10].
 */
#include "stm32h7xx_hal.h"

#define HSEM_ID_WAKE_CM4 0u

int main(void) {
    __HAL_RCC_HSEM_CLK_ENABLE();
    HAL_HSEM_ActivateNotification(__HAL_HSEM_SEMID_TO_MASK(HSEM_ID_WAKE_CM4));
    for (;;) {
        HAL_PWREx_ClearPendingEvent();
        HAL_PWREx_EnterSTOPMode(PWR_MAINREGULATOR_ON, PWR_STOPENTRY_WFE, PWR_D2_DOMAIN);
        __HAL_HSEM_CLEAR_FLAG(__HAL_HSEM_SEMID_TO_MASK(HSEM_ID_WAKE_CM4));
        /* Woken: nothing to do yet. Go back to sleep. */
    }
}
