// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <system_error>
#include <toml_config/util/os.h>

TEST_CASE("OS discovery identifies the running executable and clears a previous error")
{
    std::error_code failure = std::make_error_code(std::errc::permission_denied);
    const std::filesystem::path executable = nom::config::detail::os::current_executable(failure);
    REQUIRE_FALSE(failure);
    REQUIRE(executable.is_absolute());
    REQUIRE(executable == std::filesystem::canonical(TOML_CONFIG_TEST_EXECUTABLE));
}
