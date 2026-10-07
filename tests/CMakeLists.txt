# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

# Tests are grouped by what they verify (docs/howto.md).
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
add_subdirectory(unit)
add_subdirectory(integration)

add_test(NAME toml_config_python
    COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${PROJECT_SOURCE_DIR}/python"
        ${Python3_EXECUTABLE} -B -m unittest discover -s ${CMAKE_CURRENT_SOURCE_DIR}/python -v)
set_tests_properties(toml_config_python PROPERTIES LABELS unit)
