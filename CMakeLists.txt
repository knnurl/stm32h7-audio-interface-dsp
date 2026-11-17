# DSP audio interface. Two builds from this one tree:
#   cmake --preset host   the DSP library for the PC (tests load it through ctypes)
#   cmake --preset fw     the firmware for both cores of the STM32H755
cmake_minimum_required(VERSION 3.25)
project(dsp_interface VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_subdirectory(dsp)
if(CMAKE_CROSSCOMPILING)
    add_subdirectory(fw)
endif()
