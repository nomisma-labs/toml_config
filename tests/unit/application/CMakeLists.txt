# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

nom_c2test(application_tests SOURCES application_test.cxx DEPS nom::toml_config)
set_tests_properties(toml_config_application_tests PROPERTIES LABELS unit)
