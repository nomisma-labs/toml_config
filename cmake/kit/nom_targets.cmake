# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

function(nom_set_warnings target)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    endif()
endfunction()

# Installed apps and shared libraries locate packaged libraries after prefix relocation.
function(nom_set_install_library_path target origin_directory)
    if(APPLE)
        set(origin "@loader_path")
    elseif(UNIX)
        set(origin "$ORIGIN")
    else()
        return()
    endif()
    file(RELATIVE_PATH relative_libdir "${origin_directory}" "${CMAKE_INSTALL_FULL_LIBDIR}")
    if(relative_libdir STREQUAL "")
        set(path "${origin}")
    else()
        set(path "${origin}/${relative_libdir}")
    endif()
    set_property(TARGET ${target} APPEND PROPERTY INSTALL_RPATH "${path}")
endfunction()

# nom_lib(<name> [STATIC | SHARED] [SOURCES <files>] [HEADERS <files>] [MODULES <files>] [BASE_DIR <dir>]
#                 [PUBLIC_DEPS <targets>] [PRIVATE_DEPS <targets>])
#
# Creates <name> and its alias nom::<name>. Nomisma library APIs are declared in MODULES.
# Without SOURCES or MODULES it is an INTERFACE target for macros or dependency adapters.
# STATIC/SHARED selects compiled linkage explicitly; otherwise
# BUILD_SHARED_LIBS supplies the default. HEADERS and MODULES become file sets rooted at BASE_DIR (default:
# <project>/core), so they install under the same path they are included by: <name>/file.h.
function(nom_lib name)
    cmake_parse_arguments(PARSE_ARGV 1 arg "STATIC;SHARED" "BASE_DIR" "SOURCES;HEADERS;MODULES;PUBLIC_DEPS;PRIVATE_DEPS")
    if(arg_STATIC AND arg_SHARED)
        message(FATAL_ERROR "nom_lib(${name}): STATIC and SHARED are mutually exclusive")
    endif()
    if((arg_STATIC OR arg_SHARED) AND NOT (arg_SOURCES OR arg_MODULES))
        message(FATAL_ERROR "nom_lib(${name}): STATIC/SHARED requires SOURCES or MODULES")
    endif()
    set(linkage)
    if(arg_STATIC)
        set(linkage STATIC)
    elseif(arg_SHARED)
        set(linkage SHARED)
    endif()
    if(NOT arg_BASE_DIR)
        set(arg_BASE_DIR ${PROJECT_SOURCE_DIR}/core)
    endif()

    if(arg_SOURCES OR arg_MODULES)
        add_library(${name} ${linkage})
        set(scope PUBLIC)
    else()
        add_library(${name} INTERFACE)
        set(scope INTERFACE)
    endif()
    add_library(nom::${name} ALIAS ${name})

    if(arg_SOURCES)
        target_sources(${name} PRIVATE ${arg_SOURCES})
    endif()
    if(arg_HEADERS)
        target_sources(${name} ${scope} FILE_SET HEADERS BASE_DIRS ${arg_BASE_DIR} FILES ${arg_HEADERS})
    endif()
    if(arg_MODULES)
        target_sources(${name} PUBLIC FILE_SET CXX_MODULES BASE_DIRS ${arg_BASE_DIR} FILES ${arg_MODULES})
    endif()

    target_compile_features(${name} ${scope} cxx_std_23)
    if(arg_PUBLIC_DEPS)
        target_link_libraries(${name} ${scope} ${arg_PUBLIC_DEPS})
    endif()
    if(scope STREQUAL "PUBLIC")
        if(arg_PRIVATE_DEPS)
            target_link_libraries(${name} PRIVATE ${arg_PRIVATE_DEPS})
        endif()
        set_target_properties(${name} PROPERTIES CXX_EXTENSIONS OFF)
        nom_set_warnings(${name})
        get_target_property(target_type ${name} TYPE)
        if(target_type STREQUAL "SHARED_LIBRARY" OR target_type STREQUAL "MODULE_LIBRARY")
            nom_set_install_library_path(${name} "${CMAKE_INSTALL_FULL_LIBDIR}")
        endif()
    endif()
endfunction()

# nom_app(<name> SOURCES <files> [DEPS <targets>] [BUILD_FOR <names>])
#
# Target <project>_<name>, because target names are global in a superbuild. The binary is
# bin/<name> in the project's build directory. If the app directory contains config/,
# collect it at <top-level build>/config/<app directory> on every build. When
# installation is enabled, install selected apps and their collected config. BUILD_FOR defaults
# to any; NOM_BUILD_PRESET=complete selects every app. Other apps remain explicitly buildable.
function(nom_app name)
    cmake_parse_arguments(PARSE_ARGV 1 arg "" "" "SOURCES;DEPS;BUILD_FOR")
    if(NOT arg_BUILD_FOR)
        set(arg_BUILD_FOR any)
    endif()
    set(selected FALSE)
    if(NOM_BUILD_PRESET STREQUAL "complete" OR "any" IN_LIST arg_BUILD_FOR OR NOM_BUILD_PRESET IN_LIST arg_BUILD_FOR)
        set(selected TRUE)
    endif()
    set(target ${PROJECT_NAME}_${name})
    add_executable(${target} ${arg_SOURCES})
    if(NOT selected)
        set_target_properties(${target} PROPERTIES EXCLUDE_FROM_ALL TRUE)
    endif()
    target_link_libraries(${target} PRIVATE ${arg_DEPS})
    target_compile_features(${target} PRIVATE cxx_std_23)
    set_target_properties(${target} PROPERTIES
        OUTPUT_NAME ${name}
        RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin
        CXX_EXTENSIONS OFF)
    nom_set_warnings(${target})
    nom_set_install_library_path(${target} "${CMAKE_INSTALL_FULL_BINDIR}")

    if(nom_install AND selected)
        install(TARGETS ${target} RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
    endif()

    set(config_source "${CMAKE_CURRENT_SOURCE_DIR}/config")
    if(IS_DIRECTORY "${config_source}")
        cmake_path(GET CMAKE_CURRENT_SOURCE_DIR FILENAME app_folder)
        set(config_target "${PROJECT_NAME}_copy_${app_folder}_config")
        set(config_destination "${CMAKE_BINARY_DIR}/config/${app_folder}")
        if(NOT TARGET ${config_target})
            add_custom_target(${config_target}
                COMMAND ${CMAKE_COMMAND} -E rm -rf "${config_destination}"
                COMMAND ${CMAKE_COMMAND} -E copy_directory "${config_source}" "${config_destination}"
                COMMENT "Collecting config for ${app_folder}"
                VERBATIM)
        endif()
        # The first app in a shared directory may be excluded while a later one is selected.
        get_property(config_install_registered TARGET ${config_target} PROPERTY NOM_CONFIG_INSTALL_REGISTERED)
        if(nom_install AND selected AND NOT config_install_registered)
            install(DIRECTORY "${config_destination}/" DESTINATION "config/${app_folder}")
            set_property(TARGET ${config_target} PROPERTY NOM_CONFIG_INSTALL_REGISTERED TRUE)
        endif()
        add_dependencies(${target} ${config_target})
    endif()
endfunction()

# nom_c2test(<suite> SOURCES <files> [DEPS <targets>])
#
# One Catch2 executable per test folder: target <project>_<suite>, registered with CTest.
# Call nom_find_catch2() first.
function(nom_c2test suite)
    cmake_parse_arguments(PARSE_ARGV 1 arg "" "" "SOURCES;DEPS")
    set(target ${PROJECT_NAME}_${suite})
    add_executable(${target} ${arg_SOURCES})
    target_link_libraries(${target} PRIVATE ${arg_DEPS} Catch2::Catch2WithMain)
    target_compile_features(${target} PRIVATE cxx_std_23)
    set_target_properties(${target} PROPERTIES CXX_EXTENSIONS OFF)
    nom_set_warnings(${target})
    add_test(NAME ${target} COMMAND ${target})
endfunction()

# nom_library_usage_tests(<dir> [OPTIONS <-Dname=value>...])
#
# Integration tests that build and run <dir>, a separate project using this library:
# once through find_package against an installation in the build tree, and once from source
# through FetchContent. The test project receives LIBRARY_USAGE_MODE (package
# or source), LIBRARY_USAGE_SOURCE_DIR, this build's compiler, build type and flags, and OPTIONS.
function(nom_library_usage_tests dir)
    cmake_parse_arguments(PARSE_ARGV 1 arg "" "" "OPTIONS")
    cmake_path(ABSOLUTE_PATH dir BASE_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR} OUTPUT_VARIABLE source_dir)
    set(work_dir ${PROJECT_BINARY_DIR}/tests/integration/library_usage)
    set(options
        -DCMAKE_CXX_COMPILER=${CMAKE_CXX_COMPILER}
        -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
        "-DCMAKE_CXX_FLAGS=${CMAKE_CXX_FLAGS}"
        ${arg_OPTIONS})

    add_test(NAME ${PROJECT_NAME}_library_usage_install
        COMMAND ${CMAKE_COMMAND} --install ${PROJECT_BINARY_DIR} --prefix ${work_dir}/install)
    set_tests_properties(${PROJECT_NAME}_library_usage_install PROPERTIES FIXTURES_SETUP ${PROJECT_NAME}_installed)

    add_test(NAME ${PROJECT_NAME}_library_usage_package
        COMMAND ${CMAKE_CTEST_COMMAND}
            --build-and-test ${source_dir} ${work_dir}/package
            --build-generator ${CMAKE_GENERATOR}
            --build-options ${options} -DLIBRARY_USAGE_MODE=package -DCMAKE_PREFIX_PATH=${work_dir}/install
            --test-command ${CMAKE_CTEST_COMMAND} --output-on-failure)
    set_tests_properties(${PROJECT_NAME}_library_usage_package PROPERTIES FIXTURES_REQUIRED ${PROJECT_NAME}_installed)

    add_test(NAME ${PROJECT_NAME}_library_usage_source
        COMMAND ${CMAKE_CTEST_COMMAND}
            --build-and-test ${source_dir} ${work_dir}/source
            --build-generator ${CMAKE_GENERATOR}
            --build-options ${options} -DLIBRARY_USAGE_MODE=source -DLIBRARY_USAGE_SOURCE_DIR=${PROJECT_SOURCE_DIR}
            --test-command ${CMAKE_CTEST_COMMAND} --output-on-failure)
    set_tests_properties(
        ${PROJECT_NAME}_library_usage_install
        ${PROJECT_NAME}_library_usage_package
        ${PROJECT_NAME}_library_usage_source
        PROPERTIES LABELS integration)
endfunction()
