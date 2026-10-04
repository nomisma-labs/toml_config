# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

cmake_minimum_required(VERSION 3.30)

# The version lives only here; releases are tagged v<version> (docs/build.md#versioning).
project(toml_config
    VERSION 0.1.0
    DESCRIPTION "Nomisma application configuration"
    LANGUAGES CXX)

include(cmake/kit/nom_kit.cmake)
nom_project_options()

# Dependencies come from external/ submodules (docs/howto.md#a-dependency). In a superbuild the
# outermost FetchContent_Declare wins, so every repo shares one copy.
nom_find_metal()

# Discover Catch2 before any code directory can register an inline test suite.
if(nom_build_tests)
    enable_testing()
    nom_find_catch2()
endif()

add_subdirectory(core)

if(nom_build_apps)
    add_subdirectory(apps)
endif()

if(nom_build_tests)
    add_subdirectory(tests)
endif()
