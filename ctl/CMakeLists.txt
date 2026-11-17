# The hardware-free control library (batch 8a): parameter registry, knob ownership, control
# protocol, MIDI, presets. Same rules as dsp/. The firmware compiles CTL_SOURCES into the M7
# image; on the PC it builds as a DLL the Python tests load (ctl_host), plus a fuzz driver built
# with the address sanitiser on MSVC (ctl_fuzz).
set(_sources
    src/ctl_core.c src/ctl_midi.c src/ctl_midi_cc14.c src/ctl_param_table.c src/ctl_params.c
    src/ctl_preset.c src/ctl_proto.c src/ctl_queue.c src/ctl_text.c)

set(_absolute)
foreach(_source ${_sources})
    list(APPEND _absolute ${CMAKE_CURRENT_SOURCE_DIR}/${_source})
endforeach()
set(CTL_SOURCES ${_absolute} PARENT_SCOPE)
set(CTL_INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/include PARENT_SCOPE)

if(CMAKE_CROSSCOMPILING)
    return()
endif()

if(MSVC)
    set(_flags /W4 /WX /fp:precise)
else()
    set(_flags -Wall -Wextra -Werror -ffp-contract=off)
endif()

# The PC-only parts: the flash simulator, the whole-stack object, and the CRC from dsp/.
set(_host_sources ${_sources} src/ctl_flash_sim.c src/ctl_host.c
    ${CMAKE_SOURCE_DIR}/dsp/src/dsp_crc32.c)

add_library(ctl_host SHARED ${_host_sources})
target_include_directories(ctl_host PRIVATE include ${CMAKE_SOURCE_DIR}/dsp/include)
target_compile_options(ctl_host PRIVATE ${_flags})
set_target_properties(ctl_host PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
if(NOT MSVC)
    target_link_libraries(ctl_host PUBLIC m)
endif()

add_executable(ctl_fuzz fuzz/ctl_fuzz.c ${_host_sources})
target_include_directories(ctl_fuzz PRIVATE include ${CMAKE_SOURCE_DIR}/dsp/include)
target_compile_options(ctl_fuzz PRIVATE ${_flags})
if(MSVC)
    # The address sanitiser. Its runtime DLL sits beside cl.exe; copy it next to the program so
    # the tests can run it from any shell.
    target_compile_options(ctl_fuzz PRIVATE /fsanitize=address /Zi)
    target_link_options(ctl_fuzz PRIVATE /INCREMENTAL:NO /DEBUG)
    get_filename_component(_cl_dir ${CMAKE_C_COMPILER} DIRECTORY)
    if(EXISTS ${_cl_dir}/clang_rt.asan_dynamic-x86_64.dll)
        add_custom_command(TARGET ctl_fuzz POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    ${_cl_dir}/clang_rt.asan_dynamic-x86_64.dll $<TARGET_FILE_DIR:ctl_fuzz>
            VERBATIM)
    endif()
else()
    target_compile_options(ctl_fuzz PRIVATE -fsanitize=address -g)
    target_link_options(ctl_fuzz PRIVATE -fsanitize=address)
    target_link_libraries(ctl_fuzz PRIVATE m)
endif()
