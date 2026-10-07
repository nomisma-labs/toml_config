// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <cstdint>
#include <exception>
#include <iostream>
#include <optional>
#include <string>
#include <toml.hpp>

struct consumer_config
{
    std::string name;
    std::int64_t count;
    std::optional<std::string> absent;
};
TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(consumer_config, name, count, absent)

import nom.toml_config;

int main(int argc, char* argv[])
{
    try
    {
        if (argc != 2)
            return 1;
        nom::config::application_options options;
        options.config_file = argv[1];
        const auto result = nom::config::initialize<consumer_config>(options);
        if (result.value.name != "consumer" || result.value.count != 42 || result.value.absent ||
            nom::config::format(result.resolved).empty())
            return 1;
        return 0;
    }
    catch (const std::exception& exception)
    {
        std::cerr << exception.what() << '\n';
        return 1;
    }
}
