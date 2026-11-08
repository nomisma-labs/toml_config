// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#pragma once

#include <string>
#include <vector>

namespace example
{
    struct app_arguments
    {
        std::string name{"world"};
        int count{1};
        bool verbose{};
        bool help{};
    };

    app_arguments parse_app_arguments(const std::vector<std::string>& arguments, bool show_help = false);
} // namespace example
