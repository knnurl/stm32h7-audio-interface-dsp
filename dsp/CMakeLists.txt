# The hardware-free DSP library. On the PC it builds as a static library and as a DLL that the
# Python tests load through ctypes. The firmware compiles the same sources into the M7 image
# with the M7 flags (fw/CMakeLists.txt), so no library is built here when cross-compiling.
set(_sources
    src/dsp_abi.c src/dsp_biquad.c src/dsp_coef.c src/dsp_comp.c src/dsp_crc32.c src/dsp_crossfeed.c
    src/dsp_dcblock.c
    src/dsp_delayline.c src/dsp_env.c src/dsp_fastmath.c src/dsp_fx_colour.c src/dsp_fx_common.c
    src/dsp_fx_echo.c src/dsp_fx_mod.c src/dsp_fx_tremolo.c src/dsp_fxslot.c src/dsp_gain.c
    src/dsp_gate.c src/dsp_kweight.c src/dsp_lfo.c src/dsp_limiter.c src/dsp_meter.c src/dsp_mixer.c
    src/dsp_oversample.c src/dsp_peq.c
    src/dsp_reverb.c src/dsp_saturate.c src/dsp_selftest.c src/dsp_svf.c src/dsp_testsig.c
    src/dsp_tone.c)

set(_absolute)
foreach(_source ${_sources})
    list(APPEND _absolute ${CMAKE_CURRENT_SOURCE_DIR}/${_source})
endforeach()
set(DSP_SOURCES ${_absolute} PARENT_SCOPE)
set(DSP_INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/include PARENT_SCOPE)

if(CMAKE_CROSSCOMPILING)
    return()
endif()

# Float policy: no fused multiply-add contraction on either side until batch 3 decides
# (SPEC section 7). /fp:precise does not contract; GCC and Clang need telling.
if(MSVC)
    set(_flags /W4 /WX /fp:precise)
else()
    set(_flags -Wall -Wextra -Werror -ffp-contract=off)
endif()

add_library(dsp STATIC ${_sources})
target_include_directories(dsp PUBLIC include)
target_compile_options(dsp PRIVATE ${_flags})

add_library(dsp_host SHARED ${_sources})
target_include_directories(dsp_host PUBLIC include)
target_compile_options(dsp_host PRIVATE ${_flags})
set_target_properties(dsp_host PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
if(NOT MSVC)
    target_link_libraries(dsp PUBLIC m)
    target_link_libraries(dsp_host PUBLIC m)
endif()
