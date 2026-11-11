# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

if(TARGET config_args_example)
    find_package(Python 3.10 REQUIRED COMPONENTS Interpreter)
    add_test(NAME ${PROJECT_NAME}_config_args_example_cli
        COMMAND ${CMAKE_COMMAND} -E env
            "TCFG_APP_TEST_EXECUTABLE=$<TARGET_FILE:config_args_example>"
            ${Python_EXECUTABLE} -m unittest discover
            -s "${CMAKE_CURRENT_SOURCE_DIR}"
            -p "*_test.py"
            -v)
    set_tests_properties(${PROJECT_NAME}_config_args_example_cli PROPERTIES
        WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
        LABELS integration)
endif()
