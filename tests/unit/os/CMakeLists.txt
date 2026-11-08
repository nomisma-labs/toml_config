# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

nom_c2test(os_tests SOURCES os_test.cxx DEPS nom::toml_config)
target_include_directories(toml_config_os_tests PRIVATE "${PROJECT_SOURCE_DIR}/src")
target_compile_definitions(toml_config_os_tests PRIVATE
    TOML_CONFIG_TEST_EXECUTABLE="$<TARGET_FILE:toml_config_os_tests>")
set_tests_properties(toml_config_os_tests PROPERTIES LABELS unit)
