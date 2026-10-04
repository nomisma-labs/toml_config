# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

# Integration checks for library usage and installation (docs/howto.md#library-usage-integration-tests).

# template-only:begin
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
add_test(NAME ${PROJECT_NAME}_app_presets
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/app_presets/check.py
        --cmake ${CMAKE_COMMAND}
        --compiler ${CMAKE_CXX_COMPILER}
        --generator "${CMAKE_GENERATOR}"
        --kit ${PROJECT_SOURCE_DIR}/cmake/kit)
set_tests_properties(${PROJECT_NAME}_app_presets PROPERTIES LABELS integration)

if(UNIX)
    add_test(NAME ${PROJECT_NAME}_relocation
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/relocation/check.py
            --cmake ${CMAKE_COMMAND} --compiler ${CMAKE_CXX_COMPILER}
            --generator "${CMAKE_GENERATOR}" --kit ${PROJECT_SOURCE_DIR}/cmake/kit)
    set_tests_properties(${PROJECT_NAME}_relocation PROPERTIES LABELS integration)
endif()

if(nom_install)
    nom_library_usage_tests(library_usage)
endif()
# The app build must collect its source config into the common build/config tree.
if(TARGET ${PROJECT_NAME}_hello)
    add_test(NAME ${PROJECT_NAME}_collected_config
        COMMAND ${CMAKE_COMMAND} -E compare_files
            ${PROJECT_SOURCE_DIR}/apps/hello/config/settings.json
            ${CMAKE_BINARY_DIR}/config/hello/settings.json)
    set_tests_properties(${PROJECT_NAME}_collected_config PROPERTIES LABELS integration)
    if(nom_install)
        add_test(NAME ${PROJECT_NAME}_installed_config
            COMMAND ${CMAKE_COMMAND} -E compare_files
                ${CMAKE_BINARY_DIR}/config/hello/settings.json
                ${PROJECT_BINARY_DIR}/tests/integration/library_usage/install/config/hello/settings.json)
        set_tests_properties(${PROJECT_NAME}_installed_config PROPERTIES
            FIXTURES_REQUIRED ${PROJECT_NAME}_installed LABELS integration)
    endif()
endif()
# template-only:end
