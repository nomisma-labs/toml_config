# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

# nom_find_catch2()
#
# The system Catch2 3 when installed, otherwise a pinned download.
macro(nom_find_catch2)
    FetchContent_Declare(Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG v3.16.0
        GIT_SHALLOW TRUE
        FIND_PACKAGE_ARGS 3 CONFIG)
    FetchContent_MakeAvailable(Catch2)
endmacro()
