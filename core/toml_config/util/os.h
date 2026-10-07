// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#pragma once

#include <filesystem>
#include <system_error>

// Private OS boundary. Keep configuration policy and configuration types out of it.
namespace nom::config::detail::os
{
    // Returns the absolute path to the running executable, resolving launch symlinks.
    // On an OS lookup failure, returns an empty path and sets failure.
    std::filesystem::path current_executable(std::error_code& failure);
} // namespace nom::config::detail::os
