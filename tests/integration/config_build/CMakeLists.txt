# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

find_package(Python 3.11 REQUIRED COMPONENTS Interpreter)
add_test(NAME ${PROJECT_NAME}_config_build
    COMMAND ${CMAKE_COMMAND} -E env
        "TCFG_TEST_CMAKE=${CMAKE_COMMAND}"
        "TCFG_TEST_CTEST=${CMAKE_CTEST_COMMAND}"
        "TCFG_TEST_CXX=${CMAKE_CXX_COMPILER}"
        ${Python_EXECUTABLE} -m unittest discover
        -s "${CMAKE_CURRENT_SOURCE_DIR}"
        -p "*_test.py"
        -v)
set_tests_properties(${PROJECT_NAME}_config_build PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    LABELS integration)
