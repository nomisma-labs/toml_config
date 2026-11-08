// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include "app_arguments.h"

#include <toml_config/config.h>

import std;

import nom.toml_config;

namespace example
{
    struct app_config
    {
        nom::cfg_defaulted<nom::cfg_string> greeting{"Hello"};

        std::expected<void, std::string> validate() const
        {
            if (greeting->empty())
            {
                return std::unexpected("greeting must not be empty");
            }
            return {};
        }
    };

    NOM_TCONFIG(app_config, greeting)
} // namespace example

int main(int argc, char** argv)
{
    try
    {
        const auto arguments = nom::tcfg::parse_config_arguments(argc, argv, NOM_CONFIG_KEY_VALUE);
        // TODO: think how to make this case simpler - there are too many questions to this workflow. I understand the
        // complexity of parsing extra argument, but this still looks too messy (e.g. --help handling)
        const auto app = example::parse_app_arguments(arguments.remaining_arguments, arguments.help);
        if (app.help)
        {
            return 0;
        }

        const auto config = nom::tcfg::load_config<example::app_config>(arguments.options);
        if (arguments.options.check_config)
        {
            nom::tcfg::print_config_check(std::cout, config, arguments.options.check_mode);
            return 0;
        }

        if (app.verbose)
        {
            std::cout << "Greeting count: " << app.count << '\n';
        }
        for (int index = 0; index < app.count; ++index)
        {
            std::cout << *config.value.greeting << ", " << app.name << "!\n";
        }
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
