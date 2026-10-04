# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

include(FetchContent)

# nom_require_submodule(<path>)
#
# Fails early, with the fix, when a submodule was not checked out: a plain `git clone` leaves
# external/ empty. Only checked for a standalone build; in a superbuild the outer project
# supplies the dependency.
function(nom_require_submodule path)
    if(NOT PROJECT_IS_TOP_LEVEL)
        return()
    endif()
    file(GLOB entries ${PROJECT_SOURCE_DIR}/${path}/*)
    if(NOT entries)
        message(FATAL_ERROR "${path} is empty. Run: git submodule update --init --recursive")
    endif()
endfunction()

# nom_find_metal()
#
# Provides nom::metal from the foundational submodule. The first declaration and target
# win in a superbuild. Metal's own project builds tools and tests, so only its headers
# are populated; their separate package is shared by every installed Nomisma library.
function(nom_find_metal)
    if(TARGET nom::metal)
        return()
    endif()
    nom_require_submodule(external/metal)
    FetchContent_Declare(metal
        SOURCE_DIR ${PROJECT_SOURCE_DIR}/external/metal
        SOURCE_SUBDIR nomisma_headers_only)
    FetchContent_MakeAvailable(metal)

    nom_lib(metal)
    target_include_directories(metal SYSTEM INTERFACE
        $<BUILD_INTERFACE:${metal_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

    if(nom_install)
        set(config_dir ${CMAKE_INSTALL_LIBDIR}/cmake/nom_metal)
        set(version_parts)
        foreach(component IN ITEMS MAJOR MINOR PATCH)
            file(STRINGS ${metal_SOURCE_DIR}/include/metal/config/version.hpp definition
                REGEX "^#define[ \t]+METAL_${component}[ \t]+[0-9]+" LIMIT_COUNT 1)
            string(REGEX MATCH "[0-9]+" version_component "${definition}")
            if(version_component STREQUAL "")
                message(FATAL_ERROR "Metal's version header does not define METAL_${component}")
            endif()
            list(APPEND version_parts ${version_component})
        endforeach()
        list(JOIN version_parts "." metal_version)

        install(TARGETS metal EXPORT nom_metal_targets)
        install(EXPORT nom_metal_targets
            NAMESPACE nom::
            FILE nom_metal-targets.cmake
            DESTINATION ${config_dir})
        install(DIRECTORY ${metal_SOURCE_DIR}/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
        install(FILES ${metal_SOURCE_DIR}/LICENSE
            DESTINATION ${CMAKE_INSTALL_DATADIR}/licenses/nom_metal)
        configure_package_config_file(${CMAKE_CURRENT_FUNCTION_LIST_DIR}/metal_config.cmake.in
            ${CMAKE_CURRENT_BINARY_DIR}/nom_metal-config.cmake
            INSTALL_DESTINATION ${config_dir})
        write_basic_package_version_file(${CMAKE_CURRENT_BINARY_DIR}/nom_metal-config-version.cmake
            VERSION ${metal_version}
            COMPATIBILITY SameMajorVersion
            ARCH_INDEPENDENT)
        install(FILES
            ${CMAKE_CURRENT_BINARY_DIR}/nom_metal-config.cmake
            ${CMAKE_CURRENT_BINARY_DIR}/nom_metal-config-version.cmake
            DESTINATION ${config_dir})
    endif()
endfunction()

# nom_find_catch2()
#
# The system Catch2 3 when installed, otherwise a pinned download.
macro(nom_find_catch2)
    FetchContent_Declare(Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG v3.16.0
        GIT_SHALLOW TRUE
        FIND_PACKAGE_ARGS 3 CONFIG)
    FetchContent_MakeAvailable(Catch2)
endmacro()
