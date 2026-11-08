# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
add_subdirectory(unit)
add_subdirectory(integration)
