# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT

nom_app(md_capture IMPORT_STD SOURCES main.cpp DEPS nom::toml_config
    COMPILE_OPTIONS -DNOM_CONFIG_KEY=md_capture)

nom_tcfg_generate(md_capture SOURCE md_capture_tcfg.toml BUILD_WITH_APP)
nom_tcfg_test(md_capture base)
nom_tcfg_test(md_capture ci)
nom_tcfg_test(md_capture prod)
nom_tcfg_test(md_capture prod-liquidation)
