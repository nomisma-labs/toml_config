# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

include(FetchContent)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

# Upstream's precompiled mode keeps parser implementation details out of module interfaces
# and avoids GCC module/header interoperability failures in header-only mode. The adapter
# also installs the dependency; upstream disables installation when used as a subproject.
# Like the shared kit dependencies, an existing target or outer FetchContent declaration wins.
function(toml_config_find_toml11)
    if(TARGET toml11::toml11)
        return()
    endif()

    nom_require_submodule(external/toml11)
    FetchContent_Declare(toml11
        SOURCE_DIR ${PROJECT_SOURCE_DIR}/external/toml11
        SOURCE_SUBDIR nomisma_compiled_adapter)
    FetchContent_MakeAvailable(toml11)
    if(TARGET toml11::toml11)
        return()
    endif()

    set(source_files)
    foreach(source IN ITEMS color comments context datetime error_info format literal location
            parser region scanner serializer skip source_location syntax types value_t)
        list(APPEND source_files "${toml11_SOURCE_DIR}/src/${source}.cpp")
    endforeach()
    nom_lib(toml_config_toml11 STATIC SOURCES ${source_files})
    add_library(toml11::toml11 ALIAS toml_config_toml11)
    set_target_properties(toml_config_toml11 PROPERTIES
        EXPORT_NAME toml11
        POSITION_INDEPENDENT_CODE ON
        CXX_SCAN_FOR_MODULES OFF)
    target_compile_definitions(toml_config_toml11 PUBLIC TOML11_COMPILE_SOURCES)
    target_include_directories(toml_config_toml11 SYSTEM PUBLIC
        $<BUILD_INTERFACE:${toml11_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
    if(MSVC)
        target_compile_options(toml_config_toml11 PUBLIC /utf-8 /Zc:preprocessor)
    endif()

    if(nom_install)
        set(config_dir ${CMAKE_INSTALL_LIBDIR}/cmake/toml11)
        set(version_parts)
        foreach(component IN ITEMS MAJOR MINOR PATCH)
            file(STRINGS ${toml11_SOURCE_DIR}/include/toml11/version.hpp definition
                REGEX "^#define[ \t]+TOML11_VERSION_${component}[ \t]+[0-9]+" LIMIT_COUNT 1)
            string(REGEX MATCH "[0-9]+$" version_component "${definition}")
            if(version_component STREQUAL "")
                message(FATAL_ERROR "toml11 does not define TOML11_VERSION_${component}")
            endif()
            list(APPEND version_parts ${version_component})
        endforeach()
        list(JOIN version_parts "." toml11_version)

        install(TARGETS toml_config_toml11 EXPORT toml_config_toml11_targets)
        install(EXPORT toml_config_toml11_targets
            NAMESPACE toml11::
            FILE toml11-targets.cmake
            DESTINATION ${config_dir})
        install(DIRECTORY ${toml11_SOURCE_DIR}/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
        install(FILES ${toml11_SOURCE_DIR}/LICENSE
            DESTINATION ${CMAKE_INSTALL_DATADIR}/licenses/toml11)
        configure_package_config_file(${CMAKE_CURRENT_FUNCTION_LIST_DIR}/toml11_config.cmake.in
            ${CMAKE_CURRENT_BINARY_DIR}/toml11-config.cmake
            INSTALL_DESTINATION ${config_dir})
        write_basic_package_version_file(${CMAKE_CURRENT_BINARY_DIR}/toml11-config-version.cmake
            VERSION ${toml11_version}
            COMPATIBILITY SameMajorVersion)
        install(FILES
            ${CMAKE_CURRENT_BINARY_DIR}/toml11-config.cmake
            ${CMAKE_CURRENT_BINARY_DIR}/toml11-config-version.cmake
            DESTINATION ${config_dir})
    endif()
endfunction()
