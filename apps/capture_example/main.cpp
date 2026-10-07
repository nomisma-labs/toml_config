// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include "settings.h"

#include <exception>
#include <iostream>
#include <stdexcept>

import nom.toml_config;

int main(int argc, char* argv[])
{
    try
    {
        const auto options = nom::config::parse_arguments(argc, argv);
        if (options.help)
        {
            std::cout << "capture_example: configuration and binding demonstration\n" << nom::config::argument_help();
            return 0;
        }
        if (!options.remaining_arguments.empty())
            throw nom::config::error("unknown argument: " + options.remaining_arguments.front());
        const auto config = nom::config::initialize<capture_example::app_config>(options);
        const auto& feed = config.value.feed;
        if (feed.symbols.empty() || feed.timeout_ms <= 0 || feed.reconnect_delay_ms.value_or(1000) < 0)
            throw std::runtime_error("feed requires symbols, a positive timeout, and a nonnegative reconnect delay");
        if (options.print_config)
        {
            std::cout << nom::config::format(config.resolved);
            return 0;
        }
        if (options.check_config)
        {
            std::cout << "Configuration valid\n";
            return 0;
        }
        // All configuration and validation completes before application work starts.
        // This sample deliberately makes no network connections and creates no data files.
        std::cout << "Config: " << config.location.file << '\n'
                  << "Endpoint: " << feed.endpoint << '\n'
                  << "Symbols: " << feed.symbols.size() << '\n'
                  << "Timeout: " << feed.timeout_ms << " ms\n"
                  << "Reconnect delay: " << feed.reconnect_delay_ms.value_or(1000) << " ms\n"
                  << "Storage: " << nom::config::resolve_path(config.location, config.value.storage.directory) << '\n';
        return 0;
    }
    catch (const std::exception& exception)
    {
        std::cerr << "capture_example: " << exception.what() << '\n';
        return 2;
    }
}
