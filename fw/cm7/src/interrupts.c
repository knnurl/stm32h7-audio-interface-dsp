/* Interrupt handlers of the Cortex-M7. Priorities are in board.h. */
#include "board.h"
#include "console.h"

/* Faults: pass the stacked frame (main or process stack, by bit 2 of the exception return
 * value) to fault_capture (fault.c), which records it and resets. */
__attribute__((naked)) void HardFault_Handler(void) {
    __asm volatile("tst lr, #4\n"
                   "ite eq\n"
                   "mrseq r0, msp\n"
                   "mrsne r0, psp\n"
                   "b fault_capture\n");
}

void NMI_Handler(void) __attribute__((alias("HardFault_Handler")));
void MemManage_Handler(void) __attribute__((alias("HardFault_Handler")));
void BusFault_Handler(void) __attribute__((alias("HardFault_Handler")));
void UsageFault_Handler(void) __attribute__((alias("HardFault_Handler")));

void SysTick_Handler(void) { HAL_IncTick(); }

void USART3_IRQHandler(void) { console_irq(); }

/* The deferred DSP level: long transforms requested by the audio interrupt. */
void PendSV_Handler(void) { deferred_dsp(); }
