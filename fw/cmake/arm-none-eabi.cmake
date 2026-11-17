# Cross-compiling for the STM32H755 (Cortex-M7 and Cortex-M4) with GNU Arm Embedded.
# The compiler comes from ARM_TOOLCHAIN_DIR (a -D or an environment variable: the folder holding
# arm-none-eabi-gcc, for example the Arm GNU Toolchain 13.3.rel1), else the one bundled with
# STM32CubeIDE. The CPU flags are set per target in fw/CMakeLists.txt, because the two cores
# need different ones.
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

if(NOT ARM_TOOLCHAIN_DIR AND DEFINED ENV{ARM_TOOLCHAIN_DIR})
    set(ARM_TOOLCHAIN_DIR "$ENV{ARM_TOOLCHAIN_DIR}")
endif()
if(NOT ARM_TOOLCHAIN_DIR)
    file(GLOB _cubeide_gcc
         "C:/ST/STM32CubeIDE_*/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin")
    if(_cubeide_gcc)
        list(SORT _cubeide_gcc)
        list(REVERSE _cubeide_gcc)
        list(GET _cubeide_gcc 0 ARM_TOOLCHAIN_DIR)
    endif()
endif()
if(ARM_TOOLCHAIN_DIR)
    set(ARM_TOOLCHAIN_DIR "${ARM_TOOLCHAIN_DIR}" CACHE PATH "Folder holding arm-none-eabi-gcc")
    set(_prefix "${ARM_TOOLCHAIN_DIR}/arm-none-eabi-")
else()
    set(_prefix "arm-none-eabi-") # On the PATH (CI).
endif()
# CMake checks the compiler in try_compile projects, which see only the variables listed here.
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES ARM_TOOLCHAIN_DIR)

if(CMAKE_HOST_WIN32)
    set(_exe ".exe")
endif()
set(CMAKE_C_COMPILER "${_prefix}gcc${_exe}")
set(CMAKE_ASM_COMPILER "${_prefix}gcc${_exe}")
set(CMAKE_OBJCOPY "${_prefix}objcopy${_exe}" CACHE FILEPATH "")
set(CMAKE_SIZE "${_prefix}size${_exe}" CACHE FILEPATH "")

# Do not try to link a host test program while probing the compiler.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CMAKE_C_FLAGS_INIT "-ffunction-sections -fdata-sections")
set(CMAKE_ASM_FLAGS_INIT "-x assembler-with-cpp")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--gc-sections --specs=nano.specs --specs=nosys.specs")
