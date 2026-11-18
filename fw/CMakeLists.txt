# Firmware for both cores of the STM32H755 on the Nucleo-H755ZI-Q.
#   dsp_cm7.elf  the application: audio DSP, console, benchmarks (flash bank 1)
#   dsp_cm4.elf  parks the Cortex-M4 in stop mode, wakes for m4bench (flash bank 2, less its last two sectors,
#                which hold the presets)
# Configure from the repository root after fw/fetch_deps.ps1:  cmake --preset fw
enable_language(ASM)

# The Nucleo-H755ZI-Q is wired for direct SMPS supply. An image built for any other supply leaves
# the board unable to start (docs/PROGRESS.md has the recovery procedure). There is no option
# for it on purpose.
set(SUPPLY_DEFINE USE_PWR_DIRECT_SMPS_SUPPLY)

set(TP ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
if(NOT EXISTS ${TP}/stm32h7xx_hal_driver/Src/stm32h7xx_hal.c)
    message(FATAL_ERROR "Run fw/fetch_deps.ps1 first: ${TP} is missing the ST sources")
endif()
set(HAL ${TP}/stm32h7xx_hal_driver/Src)
set(DEVICE ${TP}/cmsis_device_h7/Source/Templates)

set(HAL_SOURCES
    ${HAL}/stm32h7xx_hal.c ${HAL}/stm32h7xx_hal_cortex.c ${HAL}/stm32h7xx_hal_dma.c
    ${HAL}/stm32h7xx_hal_dma_ex.c ${HAL}/stm32h7xx_hal_flash.c ${HAL}/stm32h7xx_hal_flash_ex.c
    ${HAL}/stm32h7xx_hal_gpio.c ${HAL}/stm32h7xx_hal_hsem.c
    ${HAL}/stm32h7xx_hal_pwr.c ${HAL}/stm32h7xx_hal_pwr_ex.c ${HAL}/stm32h7xx_hal_rcc.c
    ${HAL}/stm32h7xx_hal_rcc_ex.c ${HAL}/stm32h7xx_hal_uart.c ${HAL}/stm32h7xx_hal_uart_ex.c)
# ST's start-up and system files for the dual-core parts, as shipped. Start-up calls
# ExitRun0Mode (which applies the supply setting), then SystemInit, then main.
set(ST_BOOT_SOURCES
    ${DEVICE}/gcc/startup_stm32h755xx.s
    ${DEVICE}/system_stm32h7xx_dualcore_boot_cm4_cm7.c)
set(ST_INCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${TP}/cmsis_core/Core/Include
    ${TP}/cmsis_device_h7/Include
    ${TP}/stm32h7xx_hal_driver/Inc)

set(OWN_WARNINGS "-Wall;-Wextra;-Werror;-Wno-unused-parameter")

function(dsp_firmware target core_define cpu_flags linker_script)
    target_compile_definitions(${target} PRIVATE
        STM32H755xx USE_HAL_DRIVER ${core_define} ${SUPPLY_DEFINE})
    target_compile_options(${target} PRIVATE ${cpu_flags})
    target_include_directories(${target} PRIVATE ${ST_INCLUDES})
    target_link_options(${target} PRIVATE
        ${cpu_flags}
        -T${linker_script}
        -Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/${target}.map
        -Wl,--print-memory-usage
        -Wl,--no-warn-rwx-segments) # No MMU: RAM being executable means nothing here.
    set_target_properties(${target} PROPERTIES SUFFIX .elf LINK_DEPENDS ${linker_script})
    target_link_libraries(${target} PRIVATE m)
    add_custom_command(TARGET ${target} POST_BUILD
        COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${target}>
                $<TARGET_FILE_DIR:${target}>/${target}.bin
        COMMAND ${CMAKE_SIZE} $<TARGET_FILE:${target}>
        VERBATIM)
endfunction()

# ---- Cortex-M7: the application -------------------------------------------------------------
set(CM7_SOURCES
    cm7/src/main.c cm7/src/board.c cm7/src/bench.c cm7/src/console.c cm7/src/fault.c
    cm7/src/flash_store.c cm7/src/interrupts.c cm7/src/syscalls.c)
add_executable(dsp_cm7 ${CM7_SOURCES} ${DSP_SOURCES} ${CTL_SOURCES} ${ST_BOOT_SOURCES}
    ${HAL_SOURCES})
target_include_directories(dsp_cm7 PRIVATE cm7/src ${DSP_INCLUDE_DIR} ${CTL_INCLUDE_DIR})
# The self-test's large pool goes to AXI SRAM on this core only (dsp_selftest.c).
target_compile_definitions(dsp_cm7 PRIVATE DSP_HAS_AXI_BSS)
# Float policy (SPEC section 7): no fused multiply-add contraction until batch 3 decides, so the
# target computes what the PC library computes.
set_source_files_properties(${DSP_SOURCES} ${CTL_SOURCES}
    PROPERTIES COMPILE_OPTIONS "${OWN_WARNINGS};-O2;-ffp-contract=off")
set_source_files_properties(${CM7_SOURCES} PROPERTIES COMPILE_OPTIONS "${OWN_WARNINGS}")
dsp_firmware(dsp_cm7 CORE_CM7
    "-mcpu=cortex-m7;-mthumb;-mfpu=fpv5-d16;-mfloat-abi=hard"
    ${CMAKE_CURRENT_SOURCE_DIR}/cm7/stm32h755_cm7.ld)

# ---- Cortex-M4: parked ----------------------------------------------------------------------
# It carries the DSP library too, to measure the self-test cases on this core (m4bench).
add_executable(dsp_cm4 cm4/src/main.c ${DSP_SOURCES} ${ST_BOOT_SOURCES} ${HAL_SOURCES})
target_include_directories(dsp_cm4 PRIVATE ${DSP_INCLUDE_DIR})
set_source_files_properties(cm4/src/main.c PROPERTIES COMPILE_OPTIONS "${OWN_WARNINGS}")
dsp_firmware(dsp_cm4 CORE_CM4
    "-mcpu=cortex-m4;-mthumb;-mfpu=fpv4-sp-d16;-mfloat-abi=hard"
    ${CMAKE_CURRENT_SOURCE_DIR}/cm4/stm32h755_cm4.ld)
