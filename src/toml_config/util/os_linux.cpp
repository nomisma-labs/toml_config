// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include "os.h"

#include <filesystem>
#include <system_error>

namespace nom::config::detail::os
{
    std::filesystem::path current_executable(std::error_code& failure)
    {
        return std::filesystem::canonical("/proc/self/exe", failure);
    }
} // namespace nom::config::detail::os
