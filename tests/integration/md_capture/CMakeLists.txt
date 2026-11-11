# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

if(TARGET md_capture)
    find_package(Python 3.10 REQUIRED COMPONENTS Interpreter)
    add_test(NAME ${PROJECT_NAME}_md_capture_cli
        COMMAND ${CMAKE_COMMAND} -E env
            "TCFG_MD_CAPTURE_TEST_EXECUTABLE=$<TARGET_FILE:md_capture>"
            "TCFG_MD_CAPTURE_TEST_CONFIG_DIR=${NOM_COLLECTION_CONFIG_DIR}/md_capture"
            "TCFG_MD_CAPTURE_TEST_GENCONFIG_DIR=${NOM_GEN_CONFIG_DIR}"
            ${Python_EXECUTABLE} -m unittest discover
            -s "${CMAKE_CURRENT_SOURCE_DIR}"
            -p "*_test.py"
            -v)
    set_tests_properties(${PROJECT_NAME}_md_capture_cli PROPERTIES
        WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
        LABELS integration)
endif()
