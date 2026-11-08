# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    set(toml_config_os_source util/os_linux.cpp)
else()
    message(FATAL_ERROR "toml_config executable discovery is not implemented for ${CMAKE_SYSTEM_NAME}")
endif()

nom_lib(toml_config IMPORT_STD
    MODULES toml_config.cppm config_mapping.cppm config_runtime.cppm
    SOURCES config_options.cpp config_locator.cpp config_loader.cpp config_values.cpp ${toml_config_os_source}
    HEADERS config.h toml11.h
    PUBLIC_DEPS nom::config_types toml11::toml11
    PRIVATE_DEPS Boost::program_options)

nom_install_package(TARGETS toml_config DEPENDENCIES base "toml11 4.4 CONFIG" Boost)
