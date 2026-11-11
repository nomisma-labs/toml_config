# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

nom_c2test(runtime_tests IMPORT_STD SOURCES runtime_test.cxx DEPS nom::toml_config)
target_compile_definitions(${PROJECT_NAME}_runtime_tests PRIVATE NOM_CONFIG_KEY=runtime_config)
