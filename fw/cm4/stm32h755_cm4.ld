/* Linker script for the Cortex-M4 of the STM32H755 (SPEC section 6.2): flash bank 2, and SRAM1
 * with SRAM2 through their alias at 0x10000000. SRAM3 (0x10040000 in this alias) is left out: it
 * holds the Cortex-M7's DMA buffers. */
ENTRY(Reset_Handler)

MEMORY
{
    /* Bank 2 less sectors 6 and 7 (0x081C0000 on): the M7's preset store. */
    FLASH (rx)  : ORIGIN = 0x08100000, LENGTH = 768K
    RAM (xrw)   : ORIGIN = 0x10000000, LENGTH = 256K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Heap_Size = 0x200;
_Min_Stack_Size = 0x400;

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
        /* The DSP library, the split's block code and libgcc run from SRAM instead (see .data). */
        EXCLUDE_FILE(*dsp/src/dsp_*.c.obj *common/split_dsp.c.obj *libgcc.a:*) *(.text .text*)
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
        EXCLUDE_FILE(*dsp/src/dsp_*.c.obj *common/split_dsp.c.obj *libgcc.a:*) *(.rodata .rodata*)
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

    _sidata = LOADADDR(.data);
    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        /* The DSP library's code and constants, copied to SRAM with .data by the start-up code:
         * this core has no cache, and from flash its loops ran about 4.5 times the M7's cycles
         * (measured with m4bench, 2026-11-18). The SRAM alias at 0x10000000 is the one meant for
         * this core's code. libgcc too: this core has no double-precision FPU, so the meters'
         * double sums call its soft-float routines (8c split, 2026-11-18). */
        *dsp/src/dsp_*.c.obj(.text .text* .rodata .rodata*)
        *common/split_dsp.c.obj(.text .text* .rodata .rodata*)
        *libgcc.a:*(.text .text* .rodata .rodata*)
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } >RAM AT>FLASH

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
    } >RAM

    ._user_heap_stack (NOLOAD) :
    {
        . = ALIGN(8);
        PROVIDE(end = .);
        PROVIDE(_end = .);
        . = . + _Min_Heap_Size;
        . = . + _Min_Stack_Size;
        . = ALIGN(8);
    } >RAM

    /DISCARD/ :
    {
        libc.a(*)
        libm.a(*)
        libgcc.a(*)
    }

    .ARM.attributes 0 : { *(.ARM.attributes) }
}
