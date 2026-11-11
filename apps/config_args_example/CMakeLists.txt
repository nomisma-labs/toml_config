# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

nom_app(config_args_example IMPORT_STD
    SOURCES main.cpp app_arguments.cpp
    DEPS nom::toml_config Boost::program_options
    COMPILE_OPTIONS -DNOM_CONFIG_KEY=config_args_example)
