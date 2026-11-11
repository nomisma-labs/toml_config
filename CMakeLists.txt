# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 4.4)

# The version lives only here; releases are tagged v<version> (docs/kit/build.md#versioning).
include(cmake/kit/std_modules.cmake)

project(toml_config
    VERSION 0.2.1
    DESCRIPTION "Nomisma application configuration"
    LANGUAGES CXX)

include(cmake/kit/nom_kit.cmake)
nom_project_options()

if(nom_install)
    include(GNUInstallDirs)
    install(FILES ${PROJECT_SOURCE_DIR}/LICENSE
        DESTINATION ${CMAKE_INSTALL_DATADIR}/licenses/${PROJECT_NAME})
endif()

# Dependencies come from external/ submodules (docs/kit/howto.md#a-dependency). In a superbuild the
# outermost FetchContent_Declare wins, so every repo shares one copy.
include(cmake/toml_config/toml_dependency.cmake)
toml_config_find_toml11()
include(cmake/toml_config/config.cmake)
nom_require_submodule(external/base)
FetchContent_Declare(base SOURCE_DIR ${PROJECT_SOURCE_DIR}/external/base)
FetchContent_MakeAvailable(base)
nom_find_boost()

# Discover Catch2 before any code directory can register an inline test suite.
if(nom_build_tests)
    enable_testing()
    nom_find_catch2()
endif()

add_subdirectory(src)

if(nom_build_apps)
    add_subdirectory(apps)
endif()

if(nom_build_tests)
    add_subdirectory(tests)
endif()
