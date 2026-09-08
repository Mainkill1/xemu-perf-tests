set(XBE_TITLE "Perf tests")

set(
        TIME_SPIRIT_XISO
        ""
        CACHE FILEPATH
        "Optional Time Spirit XISO to unpack into the combined test disc"
)
set(
        TIME_SPIRIT_XISO_SHA256
        "833207d56200e577e79da13ce229c4f240c6f3c05b3e966dd2e2fe5fe11f2c31"
        CACHE STRING
        "Approved SHA-256 for the Time Spirit XISO supplied for this disc"
)
option(
        TIME_SPIRIT_AUTOLAUNCH
        "Validation only: launch bundled Time Spirit as soon as the root menu is created"
        OFF
)

include(XBEUtils REQUIRED)

find_package(NXDK REQUIRED)

find_package(NXDK_SDL2 REQUIRED)
find_package(NXDK_SDL2_Image REQUIRED)
find_package(Threads REQUIRED)

include(FetchContent)

FetchContent_Declare(
        pbkitplusplus
        GIT_REPOSITORY https://github.com/abaire/pbkitplusplus
        GIT_TAG e91d509e4f75d6d815807d80443e4e56aab89772
)

set(NO_OPT ON CACHE INTERNAL "Force pbkitplusplus debug build")

FetchContent_MakeAvailable(pbkitplusplus)

configure_file(configure.h.in configure.h)

macro(set_opt_compile_and_link_options TARGET_NAME)
    target_compile_options(
            "${TARGET_NAME}"
            PRIVATE
            -O3
            -fno-strict-aliasing
            -Wall
            $<$<COMPILE_LANGUAGE:CXX>:-Wno-builtin-macro-redefined>   # Suppress warning from NXDK undef of __STDC_NO_THREADS__
            -D_USE_MATH_DEFINES
    )
    target_link_options(
            "${TARGET_NAME}"
            PRIVATE
            "/debug:none"
    )
endmacro()

macro(set_compile_and_link_options TARGET_NAME)
    if (CMAKE_BUILD_TYPE MATCHES Debug)
        target_compile_options(
                "${TARGET_NAME}"
                PRIVATE
                -g
                -gdwarf-4
                -O0
                -Wall
                -fstandalone-debug
                $<$<COMPILE_LANGUAGE:CXX>:-Wno-builtin-macro-redefined>   # Suppress warning from NXDK undef of __STDC_NO_THREADS__
                -D_USE_MATH_DEFINES
        )
        target_link_options(
                "${TARGET_NAME}"
                PRIVATE
                "/debug:full"
        )
    else ()
        set_opt_compile_and_link_options("${TARGET_NAME}")
    endif ()
endmacro()

# Vertex shaders compiled using https://pypi.org/project/nv2a-vsh/
include(NV2A_VSH REQUIRED)
generate_nv2a_vshinc_files(
        OUTPUT_VARIABLE _VERTEX_SHADER_FILES
        INCLUDE_DIRECTORIES_VARIABLE _VERTEX_SHADER_INCLUDE_DIRS
        GENERATION_TARGET_VARIABLE _VERTEX_SHADER_GEN_TARGET
        SOURCES
        shaders/diffuse_from_uniform.vsh
        shaders/passthrough.vsh
)

add_library(
        perf_tests
        tests/busy_pfifo_tests.cpp
        tests/busy_pfifo_tests.h
        tests/cpu_floating_point_tests.cpp
        tests/cpu_floating_point_tests.h
        tests/cpu_translation_block_tests.cpp
        tests/cpu_translation_block_tests.h
        tests/fill_rate_tests.cpp
        tests/fill_rate_tests.h
        tests/game_load_composite_tests.cpp
        tests/game_load_composite_tests.h
        tests/high_vertex_count_tests.cpp
        tests/high_vertex_count_tests.h
        tests/pfifo_array_element_tests.cpp
        tests/pfifo_array_element_tests.h
        tests/pipeline_texture_switch_tests.cpp
        tests/pipeline_texture_switch_tests.h
        tests/primitive_type_tests.cpp
        tests/primitive_type_tests.h
        tests/report_query_tests.cpp
        tests/report_query_tests.h
        tests/surface_rendering_tests.cpp
        tests/surface_rendering_tests.h
        tests/test_suite.cpp
        tests/test_suite.h
        tests/tiny_draw_tests.cpp
        tests/tiny_draw_tests.h
        tests/uniform_thrash_tests.cpp
        tests/uniform_thrash_tests.h
        tests/vertex_buffer_allocation_tests.cpp
        tests/vertex_buffer_allocation_tests.h
)

set_compile_and_link_options(perf_tests)

target_include_directories(
        perf_tests
        PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}"
        "${CMAKE_CURRENT_BINARY_DIR}"
        ${_VERTEX_SHADER_INCLUDE_DIRS}
        ${PRINTF_SOURCE_DIR}
)


target_link_libraries(
        perf_tests
        PRIVATE
        Printf::printf
        pbkitplusplus
        NXDK::NXDK
        NXDK::NXDK_CXX
        NXDK::SDL2
        NXDK::SDL2_Image
)

add_dependencies(
        perf_tests
        ${_VERTEX_SHADER_GEN_TARGET}
)

add_executable(
        ${PROJECT_NAME}
        main.cpp
        debug_output.cpp
        debug_output.h
        device_info.cpp
        device_info.h
        logger.cpp
        logger.h
        menu_item.cpp
        menu_item.h
        runtime_config.cpp
        runtime_config.h
        result_store.cpp
        result_store.h
        result_statistics.cpp
        result_statistics.h
        test_driver.cpp
        test_driver.h
        test_host.cpp
        test_host.h
        test_catalog.cpp
        test_catalog.h
        generated/test_catalog.inc
)

set(PERF_TEST_RESOURCE_ROOTS "${CMAKE_SOURCE_DIR}/resources")
set(PERF_TEST_RESOURCE_DIRS "${CMAKE_SOURCE_DIR}/resources")

if (TIME_SPIRIT_XISO)
    get_filename_component(TIME_SPIRIT_XISO "${TIME_SPIRIT_XISO}" ABSOLUTE)
    if (NOT EXISTS "${TIME_SPIRIT_XISO}")
        message(FATAL_ERROR "TIME_SPIRIT_XISO does not exist: ${TIME_SPIRIT_XISO}")
    endif ()

    file(SHA256 "${TIME_SPIRIT_XISO}" TIME_SPIRIT_XISO_ACTUAL_SHA256)
    if (NOT TIME_SPIRIT_XISO_ACTUAL_SHA256 STREQUAL TIME_SPIRIT_XISO_SHA256)
        message(
                FATAL_ERROR
                "Time Spirit XISO SHA-256 mismatch. Expected ${TIME_SPIRIT_XISO_SHA256}, got ${TIME_SPIRIT_XISO_ACTUAL_SHA256}"
        )
    endif ()

    set(TIME_SPIRIT_RESOURCE_ROOT "${CMAKE_CURRENT_BINARY_DIR}/combined_resources")
    set(TIME_SPIRIT_RESOURCE_DIR "${TIME_SPIRIT_RESOURCE_ROOT}/time_spirit")
    set(TIME_SPIRIT_RESOURCE_STAMP "${CMAKE_CURRENT_BINARY_DIR}/.time_spirit_resources.stamp")
    file(
            GLOB_RECURSE TIME_SPIRIT_STATIC_RESOURCES
            CONFIGURE_DEPENDS
            "${CMAKE_SOURCE_DIR}/resources/*"
    )
    add_custom_command(
            OUTPUT "${TIME_SPIRIT_RESOURCE_STAMP}"
            COMMAND "${CMAKE_COMMAND}" -E rm -rf "${TIME_SPIRIT_RESOURCE_ROOT}"
            COMMAND "${CMAKE_COMMAND}" -E make_directory "${TIME_SPIRIT_RESOURCE_ROOT}"
            COMMAND "${CMAKE_COMMAND}" -E copy_directory
                    "${CMAKE_SOURCE_DIR}/resources"
                    "${TIME_SPIRIT_RESOURCE_ROOT}"
            COMMAND "${CMAKE_COMMAND}" -E make_directory "${TIME_SPIRIT_RESOURCE_DIR}"
            COMMAND "${EXTRACT_XISO_TOOL_PATH}" -Q -x -d "${TIME_SPIRIT_RESOURCE_DIR}" "${TIME_SPIRIT_XISO}"
            COMMAND "${CMAKE_COMMAND}" -E touch "${TIME_SPIRIT_RESOURCE_STAMP}"
            DEPENDS
                    "${TIME_SPIRIT_XISO}"
                    "${EXTRACT_XISO_TOOL_PATH}"
                    ${TIME_SPIRIT_STATIC_RESOURCES}
            COMMENT "Extracting approved Time Spirit payload for the combined XISO"
            VERBATIM
    )
    add_custom_target(time_spirit_resources DEPENDS "${TIME_SPIRIT_RESOURCE_STAMP}")
    set(PERF_TEST_RESOURCE_ROOTS "${TIME_SPIRIT_RESOURCE_ROOT}")
    set(PERF_TEST_RESOURCE_DIRS "${TIME_SPIRIT_RESOURCE_ROOT}")
    target_compile_definitions(${PROJECT_NAME} PRIVATE XEMU_PERF_TESTS_HAS_TIME_SPIRIT=1)
    if (TIME_SPIRIT_AUTOLAUNCH)
        target_compile_definitions(${PROJECT_NAME} PRIVATE XEMU_PERF_TESTS_AUTOLAUNCH_TIME_SPIRIT=1)
    endif ()
elseif (TIME_SPIRIT_AUTOLAUNCH)
    message(FATAL_ERROR "TIME_SPIRIT_AUTOLAUNCH requires TIME_SPIRIT_XISO")
endif ()

# Pull debug info out of the binary into a host-side linked binary.
split_debug(${PROJECT_NAME})

set(EXECUTABLE_BINARY "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.exe")
set_compile_and_link_options(${PROJECT_NAME})
target_include_directories(
        ${PROJECT_NAME}
        PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}"
        "${CMAKE_CURRENT_BINARY_DIR}"
)

target_link_libraries(
        ${PROJECT_NAME}
        PRIVATE
        perf_tests
        Printf::printf
        TinyJSON::tinyjson
        pbkitplusplus
        NXDK::NXDK
        NXDK::NXDK_CXX
        NXDK::SDL2
        NXDK::SDL2_Image
)

add_xbe(
        xbe_file "${EXECUTABLE_BINARY}"
        TITLE "${XBE_TITLE}"
        RESOURCE_ROOTS
        ${PERF_TEST_RESOURCE_ROOTS}
        RESOURCE_DIRS
        ${PERF_TEST_RESOURCE_DIRS}
)
if (TARGET time_spirit_resources)
    add_dependencies(sync_resource_dirs time_spirit_resources)
endif ()
add_xiso(${PROJECT_NAME}_xiso xbe_file)
