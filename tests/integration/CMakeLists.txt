# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

# Integration checks for library usage and installation (docs/kit/howto.md#library-usage-integration-tests).
if(nom_install)
    nom_library_usage_tests(library_usage)
endif()
add_test(NAME toml_config_generation
    COMMAND ${Python3_EXECUTABLE} -B ${CMAKE_CURRENT_SOURCE_DIR}/generation/generation_test.py
        --cmake ${CMAKE_COMMAND} --source ${PROJECT_SOURCE_DIR})
set_tests_properties(toml_config_generation PROPERTIES LABELS integration)
if(TARGET toml_config_capture_example)
    add_test(NAME toml_config_application_integration
        COMMAND ${Python3_EXECUTABLE} -B ${CMAKE_CURRENT_SOURCE_DIR}/application/application_test.py
            --app $<TARGET_FILE:toml_config_capture_example> --source ${PROJECT_SOURCE_DIR})
    set_tests_properties(toml_config_application_integration PROPERTIES LABELS integration)
endif()
