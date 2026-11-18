#include "board.h"

#include "console.h"

#include <stdio.h>
#include <string.h>

static bool s_cm4_parked;
static uint32_t s_cm4_park_polls;

/* Region 0: SRAM3 (32 KB at 0x30040000), the DMA buffers. Normal memory, not cacheable, so DMA
 * and the core always see the same data. Everything else keeps the default map. */
static void mpu_init(void) {
    MPU_Region_InitTypeDef region = {0};
    HAL_MPU_Disable();
    region.Enable = MPU_REGION_ENABLE;
    region.Number = MPU_REGION_NUMBER0;
    region.BaseAddress = 0x30040000u;
    region.Size = MPU_REGION_SIZE_32KB;
    region.SubRegionDisable = 0x00;
    region.TypeExtField = MPU_TEX_LEVEL1;
    region.AccessPermission = MPU_REGION_FULL_ACCESS;
    region.DisableExec = MPU_INSTRUCTION_ACCESS_DISABLE;
    region.IsShareable = MPU_ACCESS_SHAREABLE;
    region.IsCacheable = MPU_ACCESS_NOT_CACHEABLE;
    region.IsBufferable = MPU_ACCESS_NOT_BUFFERABLE;
    HAL_MPU_ConfigRegion(&region);
    HAL_MPU_Enable(MPU_PRIVILEGED_DEFAULT);
}

/* Hot kernels live in ITCM (.itcm_text) and are copied there from flash. Nothing placed in
 * that section may run before this. */
static void itcm_load(void) {
    extern uint32_t _sitcm, _eitcm, _siitcm;
    const size_t bytes = (size_t)((uint8_t *)&_eitcm - (uint8_t *)&_sitcm);
    /* The load address follows the 32 empty bytes that keep address 0 unused. */
    memcpy(&_sitcm, (const uint8_t *)&_siitcm + ((uint8_t *)&_sitcm - (uint8_t *)0), bytes);
}

static void clock_init(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);
    while (!__HAL_PWR_GET_FLAG(PWR_FLAG_VOSRDY)) {
    }

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_BYPASS; /* 8 MHz from the ST-LINK's MCO, not a crystal. */
    osc.HSIState = RCC_HSI_OFF;
    osc.CSIState = RCC_CSI_OFF;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 4;   /* 2 MHz into the VCO. */
    osc.PLL.PLLN = 400; /* 800 MHz VCO. */
    osc.PLL.PLLFRACN = 0;
    osc.PLL.PLLP = 2; /* 400 MHz SYSCLK. */
    osc.PLL.PLLQ = 4;
    osc.PLL.PLLR = 2;
    osc.PLL.PLLVCOSEL = RCC_PLL1VCOWIDE;
    osc.PLL.PLLRGE = RCC_PLL1VCIRANGE_1;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        board_error("oscillator");
    }

    clk.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_D1PCLK1 |
                    RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2 | RCC_CLOCKTYPE_D3PCLK1;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.SYSCLKDivider = RCC_SYSCLK_DIV1; /* CPU 400 MHz. */
    clk.AHBCLKDivider = RCC_HCLK_DIV2;   /* 200 MHz: the buses and the Cortex-M4. */
    clk.APB3CLKDivider = RCC_APB3_DIV2;  /* 100 MHz each. */
    clk.APB1CLKDivider = RCC_APB1_DIV2;
    clk.APB2CLKDivider = RCC_APB2_DIV2;
    clk.APB4CLKDivider = RCC_APB4_DIV2;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4) != HAL_OK) {
        board_error("clock");
    }
}

static void led_init(void) {
    GPIO_InitTypeDef pin = {0};
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOE_CLK_ENABLE();
    pin.Mode = GPIO_MODE_OUTPUT_PP;
    pin.Speed = GPIO_SPEED_FREQ_LOW;
    pin.Pin = GPIO_PIN_0 | GPIO_PIN_14;
    HAL_GPIO_Init(GPIOB, &pin);
    pin.Pin = GPIO_PIN_1;
    HAL_GPIO_Init(GPIOE, &pin);
}

/* The Cortex-M4 image puts its domain (D2) into stop mode as the first act of its main(). Wait
 * for that, as ST's template does, before the clocks change, but carry on if it never happens
 * (an empty or old M4 image): the M7 does not depend on it, and the banner reports which it was
 * and how many polls it took. Since the M4 carries the DSP library, its start-up code copies the
 * library to SRAM and zeroes about 250 KB of .bss first, which outlasted the old limit of 65535
 * polls (2026-11-18: cm4_parked=0 although the M4 then answered m4bench). */
static bool wait_for_cm4_to_park(void) {
    for (uint32_t polls = 0; polls < 0x80000u; ++polls) {
        if (__HAL_RCC_GET_FLAG(RCC_FLAG_D2CKRDY) == RESET) {
            s_cm4_park_polls = polls;
            return true;
        }
    }
    s_cm4_park_polls = 0x80000u;
    return false;
}

void board_init(void) {
    mpu_init();
    itcm_load();
    SCB_EnableICache();
    SCB_EnableDCache();
    s_cm4_parked = wait_for_cm4_to_park();
    HAL_Init(); /* SysTick at 1 kHz (priority 6, from the HAL configuration). */
    clock_init();
    led_init();
    console_init();

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->LAR = 0xC5ACCE55; /* Unlock the DWT on the M7. */
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    HAL_NVIC_SetPriority(PendSV_IRQn, kPriorityDeferred, 0);
}

bool board_cm4_parked(void) { return s_cm4_parked; }

uint32_t board_cm4_park_polls(void) { return s_cm4_park_polls; }

void board_led(BoardLed led, bool on) {
    const GPIO_PinState state = on ? GPIO_PIN_SET : GPIO_PIN_RESET;
    switch (led) {
    case kLedGreen:
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, state);
        break;
    case kLedYellow:
        HAL_GPIO_WritePin(GPIOE, GPIO_PIN_1, state);
        break;
    case kLedRed:
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, state);
        break;
    }
}

void board_led_toggle(BoardLed led) {
    switch (led) {
    case kLedGreen:
        HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_0);
        break;
    case kLedYellow:
        HAL_GPIO_TogglePin(GPIOE, GPIO_PIN_1);
        break;
    case kLedRed:
        HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
        break;
    }
}

uint32_t board_cycles(void) { return DWT->CYCCNT; }

uint32_t board_measure_cycles_per_ms(uint32_t ms) {
    uint32_t tick = HAL_GetTick();
    while (HAL_GetTick() == tick) { /* Align to a tick edge. */
    }
    tick = HAL_GetTick();
    const uint32_t start = board_cycles();
    while (HAL_GetTick() - tick < ms) {
    }
    return (board_cycles() - start) / ms;
}

void board_deferred_request(void) { SCB->ICSR = SCB_ICSR_PENDSVSET_Msk; }

__attribute__((weak)) void deferred_dsp(void) {}

void board_error(const char *what) {
    printf("fatal: %s\r\n", what);
    console_flush();
    __disable_irq();
    board_led(kLedRed, true);
    for (;;) {
    }
}
