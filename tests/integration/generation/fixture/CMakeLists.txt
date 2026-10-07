# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

cmake_minimum_required(VERSION 3.30)
project(tcfg_generation LANGUAGES NONE)
# This fixture builds no compiled library from which GNUInstallDirs could infer an ABI.
set(CMAKE_INSTALL_LIBDIR lib CACHE PATH "Unused library destination for this script-only fixture")

include("${TCFG_HELPER}")
add_custom_target(generated_configs ALL)
set(optional_assignment)
if(TCFG_EXTRA_SET)
    list(APPEND optional_assignment "application.extra=true")
endif()
tcfg_generate(TARGET generated_configs
    INPUT "input.tcfg"
    OUTPUT "result config.toml"
    SET "application.name=\"from CMake\"" "application.labels=[\"a;b\"]" ${optional_assignment}
    INSTALL_DESTINATION config/demo)

add_custom_target(excluded_configs)
set_target_properties(excluded_configs PROPERTIES EXCLUDE_FROM_ALL TRUE)
tcfg_generate(TARGET excluded_configs
    INPUT "input.tcfg"
    OUTPUT "excluded config.toml"
    INSTALL_DESTINATION config/excluded)

if(DEFINED TCFG_DUPLICATE_OUTPUT)
    add_custom_target(other_configs)
    tcfg_generate(TARGET other_configs
        INPUT "input.tcfg"
        OUTPUT "${TCFG_DUPLICATE_OUTPUT}")
endif()

toml_config_install_tooling()
