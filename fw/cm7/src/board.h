/* Nucleo-H755ZI-Q board support for the Cortex-M7: clocks, caches, the MPU, LEDs, the cycle
 * counter and the three execution levels.
 *
 * Supply: direct SMPS, applied by ST's start-up code (ExitRun0Mode) from the build's
 * USE_PWR_DIRECT_SMPS_SUPPLY. Voltage scale 1. That caps the core at 400 MHz.
 * Clocks: 8 MHz HSE bypass (ST-LINK MCO) -> PLL1 (M 4, N 400, P 2) -> 400 MHz SYSCLK and CPU
 * clock; AHB 200 MHz; APB1 to APB4 100 MHz. Flash latency 4. Values from ST's
 * NUCLEO-H745ZI-Q template (same board, MB1363).
 * Caches: both on. SRAM3 (the DMA buffers) is made non-cacheable by MPU region 0, so the audio
 * path needs no cache maintenance.
 *
 * Execution levels (SPEC 6.1), by interrupt priority, lower number first:
 *   1  audio (SAI DMA, from batch 2)     4  USB (batch 4)      6  SysTick
 *   8  console (USART3)                  14 deferred DSP (PendSV)   main loop: everything else
 */
#ifndef BOARD_H
#define BOARD_H

#include "stm32h7xx_hal.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum {
    kPriorityAudio = 1,
    kPriorityUsb = 4,
    kPriorityConsole = 8,
    kPriorityDeferred = 14,
};

typedef enum { kLedGreen, kLedYellow, kLedRed } BoardLed; /* LD1 PB0, LD2 PE1, LD3 PB14. */

void board_init(void); /* MPU, caches, HAL, clocks, LEDs, cycle counter, deferred level. */
void board_led(BoardLed led, bool on);
void board_led_toggle(BoardLed led);
void board_error(const char *what); /* Prints, lights red, stops. */

uint32_t board_cycles(void); /* DWT cycle counter: 400 counts per microsecond. */
/* Cycles counted over `ms` SysTick milliseconds, divided by ms: 400000 at 400 MHz. A check of
 * the clock tree against the HSE that does not rely on what the HAL believes. */
uint32_t board_measure_cycles_per_ms(uint32_t ms);
/* True when the Cortex-M4's domain went to stop mode at start-up (the M4 image parked it). */
bool board_cm4_parked(void);

/* Deferred DSP level: the audio interrupt calls board_deferred_request(); the handler then runs
 * deferred_dsp() at PendSV priority, pre-empted by audio, USB and the tick. */
void board_deferred_request(void);
void deferred_dsp(void); /* Weak and empty until batch 9. */

#endif
