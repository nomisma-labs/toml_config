# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

# Platform source selection stays at the OS boundary. Add a validated backend
# here when the shared build framework supports another operating system.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    set(os_source util/os_linux.cpp)
else()
    message(FATAL_ERROR "toml_config has no OS backend for ${CMAKE_SYSTEM_NAME}")
endif()

nom_lib(toml_config
    MODULES toml_config.cppm
    SOURCES toml.cpp application.cpp ${os_source}
    PUBLIC_DEPS toml11::toml11)
if(nom_install)
    nom_install_package(TARGETS toml_config DEPENDENCIES "toml11 4.4 CONFIG")
endif()
