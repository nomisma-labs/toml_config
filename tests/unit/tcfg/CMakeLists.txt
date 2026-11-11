# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

find_package(Python 3.11 REQUIRED COMPONENTS Interpreter)
add_test(NAME ${PROJECT_NAME}_tcfg_engine
    COMMAND ${Python_EXECUTABLE} -m unittest discover
        -s "${CMAKE_CURRENT_SOURCE_DIR}"
        -p "*_test.py"
        -v)
set_tests_properties(${PROJECT_NAME}_tcfg_engine PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    LABELS unit)
