/* Linker script for the Cortex-M7 of the STM32H755 (SPEC section 6.2).
 *
 *   Flash bank 1  code and constants
 *   ITCM          hot kernels (.itcm_text), copied from flash by board_init
 *   DTCM          stack, .data, .bss, the fault record
 *   AXI SRAM      large buffers (.axi_bss), not zeroed at start
 *   SRAM3         DMA buffers (.dma_buffers), made non-cacheable by the MPU
 *   SRAM4         the mailbox to the Cortex-M4 (.mailbox)
 *
 * Flash bank 2, SRAM1 and SRAM2 belong to the Cortex-M4 (fw/cm4/stm32h755_cm4.ld).
 */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1024K
    ITCM (xrw)  : ORIGIN = 0x00000000, LENGTH = 64K
    DTCM (xrw)  : ORIGIN = 0x20000000, LENGTH = 128K
    AXI (xrw)   : ORIGIN = 0x24000000, LENGTH = 512K
    SRAM3 (rw)  : ORIGIN = 0x30040000, LENGTH = 32K
    SRAM4 (rw)  : ORIGIN = 0x38000000, LENGTH = 64K
}

_estack = ORIGIN(DTCM) + LENGTH(DTCM);
_Min_Heap_Size = 0x1000;  /* newlib's stdio buffers only: nothing else allocates. */
_Min_Stack_Size = 0x4000;

SECTIONS
{
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } >FLASH

    .text :
    {
        . = ALIGN(4);
        /* The DSP library's code goes to ITCM instead (.itcm_text below). */
        EXCLUDE_FILE(*dsp/src/dsp_*.c.obj) *(.text .text*)
        *(.glue_7)
        *(.glue_7t)
        *(.eh_frame)
        KEEP(*(.init))
        KEEP(*(.fini))
        . = ALIGN(4);
        _etext = .;
    } >FLASH

    .rodata :
    {
        . = ALIGN(4);
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } >FLASH

    .ARM.extab (READONLY) : { *(.ARM.extab* .gnu.linkonce.armextab.*) } >FLASH
    .ARM (READONLY) :
    {
        __exidx_start = .;
        *(.ARM.exidx*)
        __exidx_end = .;
    } >FLASH

    .preinit_array (READONLY) :
    {
        PROVIDE_HIDDEN(__preinit_array_start = .);
        KEEP(*(.preinit_array*))
        PROVIDE_HIDDEN(__preinit_array_end = .);
    } >FLASH
    .init_array (READONLY) :
    {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT(.init_array.*)))
        KEEP(*(.init_array*))
        PROVIDE_HIDDEN(__init_array_end = .);
    } >FLASH
    .fini_array (READONLY) :
    {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*)))
        KEEP(*(.fini_array*))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } >FLASH

    /* Hot kernels: the whole DSP library (dsp/, about 35 KB of 64), so its loops fetch with zero
     * wait states instead of through the flash and the I-cache (budget work, 2026-11-17). The
     * first 32 bytes stay empty so that no function sits at address 0, where a pointer to it
     * would compare equal to NULL. Calls between flash and ITCM go through linker veneers. */
    _siitcm = LOADADDR(.itcm_text);
    .itcm_text :
    {
        . = . + 32;
        . = ALIGN(4);
        _sitcm = .;
        *dsp/src/dsp_*.c.obj(.text .text*)
        *(.itcm_text)
        *(.itcm_text*)
        . = ALIGN(4);
        _eitcm = .;
    } >ITCM AT>FLASH

    _sidata = LOADADDR(.data);
    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        *(.RamFunc)
        *(.RamFunc*)
        . = ALIGN(4);
        _edata = .;
    } >DTCM AT>FLASH

    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } >DTCM

    /* Kept across a reset (start-up neither zeroes nor loads it): the fault record. */
    .noinit (NOLOAD) :
    {
        . = ALIGN(4);
        *(.noinit)
        *(.noinit*)
        . = ALIGN(4);
    } >DTCM

    /* Generates a link error when heap and stack do not fit in what is left of DTCM. */
    ._user_heap_stack (NOLOAD) :
    {
        . = ALIGN(8);
        PROVIDE(end = .);
        PROVIDE(_end = .);
        . = . + _Min_Heap_Size;
        . = . + _Min_Stack_Size;
        . = ALIGN(8);
    } >DTCM

    /* Large buffers. Not zeroed at start: each block clears its own in its reset function. */
    .axi_bss (NOLOAD) :
    {
        . = ALIGN(32);
        *(.axi_bss)
        *(.axi_bss*)
        . = ALIGN(32);
    } >AXI

    /* DMA buffers, aligned to the cache line. The MPU makes this region non-cacheable. */
    .dma_buffers (NOLOAD) :
    {
        . = ALIGN(32);
        *(.dma_buffers)
        *(.dma_buffers*)
        . = ALIGN(32);
    } >SRAM3

    .mailbox (NOLOAD) :
    {
        . = ALIGN(4);
        *(.mailbox)
        *(.mailbox*)
        . = ALIGN(4);
    } >SRAM4

    /DISCARD/ :
    {
        libc.a(*)
        libm.a(*)
        libgcc.a(*)
    }

    .ARM.attributes 0 : { *(.ARM.attributes) }
}
