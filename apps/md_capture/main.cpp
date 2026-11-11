// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

#include <toml_config/config.h>

import std;

import nom.toml_config;

namespace md_capture
{
    using namespace nom::cfg_types;

    struct log_config
    {
        cfg_string level;
        cfg_optional<cfg_string> file;

        std::expected<void, std::string> validate() const
        {
            static constexpr std::array<std::string_view, 7> levels{
                "trace", "debug", "info", "warn", "error", "critical", "off"};
            if (std::ranges::find(levels, level) == levels.end())
            {
                return std::unexpected("/level must be trace, debug, info, warn, error, critical or off");
            }
            if (file && file->empty())
            {
                return std::unexpected("/file must be nonempty when provided");
            }
            return {};
        }
    };

    NOM_TCONFIG(log_config, level, file)

    struct snapshot_config
    {
        cfg_string address;

        std::expected<void, std::string> validate() const
        {
            if (address.empty())
            {
                return std::unexpected("/address must be nonempty");
            }
            return {};
        }
    };

    NOM_TCONFIG(snapshot_config, address)

    struct connection_config
    {
        snapshot_config snapshot;
        cfg_string address;
        cfg_defaulted<cfg_int> timeout_s{5};

        std::expected<void, std::string> validate() const
        {
            if (address.empty())
            {
                return std::unexpected("/address must be nonempty");
            }
            if (const auto result = snapshot.validate(); !result)
            {
                return std::unexpected("/snapshot" + result.error());
            }
            if (*timeout_s <= 0)
            {
                return std::unexpected("/timeout_s must be positive");
            }
            return {};
        }
    };

    NOM_TCONFIG(connection_config, snapshot, address, timeout_s)

    struct subscription_config
    {
        cfg_vector<cfg_string> symbols;
        cfg_vector<cfg_string> channels;

        std::expected<void, std::string> validate() const
        {
            const auto empty = [](const cfg_string& value) { return value.empty(); };
            if (symbols.empty() || std::ranges::any_of(symbols, empty))
            {
                return std::unexpected("/symbols must contain nonempty symbols");
            }
            if (channels.empty() || std::ranges::any_of(channels, empty))
            {
                return std::unexpected("/channels must contain nonempty channels");
            }
            return {};
        }
    };

    NOM_TCONFIG(subscription_config, symbols, channels)

    struct md_log_config
    {
        cfg_string file;

        std::expected<void, std::string> validate() const
        {
            if (file.empty())
            {
                return std::unexpected("/file must be nonempty");
            }
            return {};
        }
    };

    NOM_TCONFIG(md_log_config, file)

    struct app_config
    {
        log_config log;
        connection_config connection;
        subscription_config subscription;
        md_log_config md_log;

        std::expected<void, std::string> validate() const
        {
            if (const auto result = connection.validate(); !result)
            {
                return std::unexpected("/connection" + result.error());
            }
            if (const auto result = subscription.validate(); !result)
            {
                return std::unexpected("/subscription" + result.error());
            }
            if (const auto result = log.validate(); !result)
            {
                return std::unexpected("/log" + result.error());
            }
            if (const auto result = md_log.validate(); !result)
            {
                return std::unexpected("/md_log" + result.error());
            }
            return {};
        }
    };

    NOM_TCONFIG(app_config, log, connection, subscription, md_log)

    void print_capture_settings(const app_config& config)
    {
        std::cout << "Stream: " << config.connection.address << '\n'
                  << "Snapshot: " << config.connection.snapshot.address << '\n'
                  << "Timeout: " << *config.connection.timeout_s << " seconds\n"
                  << "Symbols:";
        for (const auto& symbol : config.subscription.symbols)
        {
            std::cout << ' ' << symbol;
        }
        std::cout << "\nChannels:";
        for (const auto& channel : config.subscription.channels)
        {
            std::cout << ' ' << channel;
        }
        std::cout << "\nLog: " << config.log.level << '\n'
                  << "Log file: " << config.log.file.value_or("(console)") << '\n'
                  << "Market data file: " << config.md_log.file << '\n';
    }
} // namespace md_capture

int main(int argc, char** argv)
{
    try
    {
        const auto arguments = nom::tcfg::parse_config_arguments(argc, argv, NOM_CONFIG_KEY_VALUE);
        if (arguments.help)
        {
            std::cout << "Usage: md_capture [options]\n";
            nom::tcfg::print_config_help(std::cout);
            return 0;
        }
        if (!arguments.remaining_arguments.empty())
        {
            std::cerr << "Usage: md_capture [options]\n";
            nom::tcfg::print_config_help(std::cerr);
            return 1;
        }
        const auto loaded = nom::tcfg::load_config<md_capture::app_config>(arguments.options);
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
        // Show the settings that capture services would receive during initialization.
        std::cout << "Capture initialized\n";
        md_capture::print_capture_settings(loaded.value);
        return 0;
    }
    catch (const nom::tcfg::config_error& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
