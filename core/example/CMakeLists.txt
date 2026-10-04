# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

nom_lib(example
    SOURCES
        counter.cpp
        settings.cpp
    HEADERS
        macros.h
    MODULES
        example.cppm
        counter.cppm
        join.cppm
        settings.cppm
        types.cppm
    PUBLIC_DEPS nom::metal
    PRIVATE_DEPS nlohmann_json::nlohmann_json)

if(nom_install)
    nom_install_package(TARGETS example DEPENDENCIES nlohmann_json nom_metal)
endif()
