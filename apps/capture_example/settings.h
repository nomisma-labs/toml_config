// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <toml.hpp>
#include <vector>

namespace capture_example
{
    struct log_config
    {
        std::string level;
    };

    struct feed_config
    {
        std::string endpoint;
        std::vector<std::string> symbols;
        std::int64_t timeout_ms;
        std::optional<std::int64_t> reconnect_delay_ms;
        std::optional<std::string> api_key;
    };

    struct storage_config
    {
        std::string directory;
    };

    struct app_config
    {
        log_config log;
        feed_config feed;
        storage_config storage;
    };
} // namespace capture_example

TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(capture_example::log_config, level)
TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(
    capture_example::feed_config, endpoint, symbols, timeout_ms, reconnect_delay_ms, api_key)
TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(capture_example::storage_config, directory)
TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(capture_example::app_config, log, feed, storage)
