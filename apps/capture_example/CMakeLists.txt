# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

nom_app(capture_example SOURCES main.cpp DEPS nom::toml_config)
option(TOML_CONFIG_GENERATE_EXAMPLE "Generate the example TOML during the build" ON)
if(TOML_CONFIG_GENERATE_EXAMPLE)
    tcfg_generate(TARGET toml_config_capture_example
        INPUT "${CMAKE_CURRENT_SOURCE_DIR}/config/capture_example.tcfg"
        OUTPUT "${PROJECT_BINARY_DIR}/generated_config/capture_example/capture_example.toml"
        INSTALL_DESTINATION "generated_config/capture_example")
endif()
