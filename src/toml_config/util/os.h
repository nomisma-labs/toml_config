// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#pragma once

#include <filesystem>

namespace nom::tcfg::os
{
    // Private platform boundary; a future common OS utility can own this operation.
    std::filesystem::path executable_path();
} // namespace nom::tcfg::os
