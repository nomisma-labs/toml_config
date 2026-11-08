// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <toml_config/config.h>

import std;

import nom.toml_config;

namespace example
{
    using namespace nom::cfg_types;

    struct app_config
    {
        cfg_defaulted<cfg_string> endpoint{"https://example.test/feed"};
        cfg_defaulted<cfg_int> timeout_s{10};
        cfg_defaulted<cfg_bool> enabled{true};
        cfg_optional<cfg_string> interface_name;

        std::expected<void, std::string> validate() const
        {
            if (endpoint->empty() || *timeout_s <= 0)
            {
                return std::unexpected("endpoint must be nonempty and timeout_s must be positive");
            }
            return {};
        }
    };

    NOM_TCONFIG(app_config, endpoint, timeout_s, enabled, interface_name)
} // namespace example

int main(int argc, char** argv)
{
    try
    {
        const auto arguments = nom::tcfg::parse_config_arguments(argc, argv, NOM_CONFIG_KEY_VALUE);
        if (arguments.help)
        {
            std::cout << "Usage: config_workflow_example [options]\n";
            nom::tcfg::print_config_help(std::cout);
            return 0;
        }
        if (!arguments.remaining_arguments.empty())
        {
            std::cerr << "Usage: config_workflow_example [options]\n";
            nom::tcfg::print_config_help(std::cerr);
            return 1;
        }
        const auto loaded = nom::tcfg::load_config<example::app_config>(arguments.options);
        if (arguments.options.check_config)
        {
            nom::tcfg::print_config_check(std::cout, loaded, arguments.options.check_mode);
            return 0;
        }
        std::cout << "Config OK (" << nom::tcfg::config_source_name(loaded.location.source) << ')';
        if (loaded.location.path)
        {
            std::cout << ": " << loaded.location.path->string();
        }
        std::cout << '\n';
        // Real application services would be initialized here using loaded.value.
        std::cout << "Application initialized; timeout: " << *loaded.value.timeout_s << " seconds\n";
        return 0;
    }
    catch (const nom::tcfg::config_error& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
