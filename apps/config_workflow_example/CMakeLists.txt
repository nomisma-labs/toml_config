# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

nom_app(config_workflow_example IMPORT_STD SOURCES main.cpp DEPS nom::toml_config
    COMPILE_OPTIONS -DNOM_CONFIG_KEY=config_workflow_example)

nom_tcfg_generate(config_workflow_example SOURCE config_workflow_example_tcfg.toml BUILD_WITH_APP)
nom_tcfg_test(config_workflow_example dev)
nom_tcfg_test(config_workflow_example prod)

if(nom_build_tests AND nom_build_apps)
    add_test(NAME ${PROJECT_NAME}_config_workflow_example_check
        COMMAND $<TARGET_FILE:config_workflow_example>
            --config "${NOM_COLLECTION_CONFIG_DIR}/config_workflow_example/config_workflow_example.toml"
            --set /timeout_s=20 --check-config)
    set_tests_properties(${PROJECT_NAME}_config_workflow_example_check PROPERTIES LABELS integration)
endif()
