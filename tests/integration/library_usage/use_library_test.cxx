// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <toml_config/config.h>

import std;

import consumer.config_model;
import nom.toml_config;

namespace consumer
{
    NOM_TCONFIG(connection_config, address, timeout_s, interface_name)
    NOM_TCONFIG(app_config, connection, enabled, annotation)

    int check_generated_config(int argc, char** argv)
    {
        const auto arguments = nom::tcfg::parse_config_arguments(argc, argv);
        const bool expect_validation_error =
            arguments.remaining_arguments == std::vector<std::string>{"--expect-validation-error"};
        if (!arguments.options.check_config || !arguments.options.config_file ||
            (!arguments.remaining_arguments.empty() && !expect_validation_error))
        {
            std::cerr << "Expected --config FILE --check-config [--expect-validation-error]\n";
            return 1;
        }

        try
        {
            const auto loaded = nom::tcfg::load_config<app_config>(
                arguments.options, [](std::string_view) -> std::optional<std::string> { return std::nullopt; });
            if (expect_validation_error)
            {
                std::cerr << "Generated config unexpectedly passed validation\n";
                return 1;
            }
            if (loaded.location.source != nom::tcfg::config_source::command_line ||
                loaded.location.path != arguments.options.config_file ||
                loaded.value.connection->address != "wss://example.test/generated" ||
                *loaded.value.connection->timeout_s != 30 || loaded.value.connection->interface_name != "loopback" ||
                loaded.value.enabled || loaded.value.annotation != "inherited")
            {
                std::cerr << "Generated config lost inherited values, child overrides or C++ defaults\n";
                return 1;
            }
            std::ostringstream view;
            nom::tcfg::print_config_check(view, loaded, nom::tcfg::config_check_mode::view);
            if (nom::tcfg::parse_config(view.str()) != toml::value(loaded.value) ||
                !loaded.location.search_details.contains("Selected candidate:"))
            {
                std::cerr << "Config check did not report the loaded configuration\n";
                return 1;
            }
        }
        catch (const nom::tcfg::config_error& error)
        {
            if (!expect_validation_error || error.stage != nom::tcfg::config_stage::validation ||
                error.file != arguments.options.config_file ||
                !std::string_view(error.what()).contains("connection requires an address and a positive timeout"))
            {
                std::cerr << error.what() << '\n';
                return 1;
            }
        }
        return 0;
    }
} // namespace consumer

int main(int argc, char** argv)
{
    if (argc > 1)
    {
        return consumer::check_generated_config(argc, argv);
    }

    const auto document = nom::tcfg::parse_config("[connection]\naddress = 'wss://example.test/feed'");
    const auto config = toml::get<consumer::app_config>(document);
    const consumer::connection_config& connection = config.connection;
    if (!config.validate() || *connection.timeout_s != 42 || connection.interface_name != "loopback" || !config.enabled)
    {
        return 1;
    }

    const toml::value serialized = config;
    if (serialized.at("connection").at("timeout_s").as_integer() != 42 || serialized.contains("annotation"))
    {
        return 2;
    }
    const auto restored = toml::get<consumer::app_config>(serialized);
    if (!restored.validate() || restored.connection->address != config.connection->address)
    {
        return 3;
    }

    auto existing = config;
    consumer::connection_config& existing_connection = existing.connection;
    existing_connection.timeout_s->value = 90;
    nom::tcfg::get_to(document, existing);
    if (*existing.connection->timeout_s != 90)
    {
        return 4;
    }

    auto malformed = document;
    malformed["connection"]["timeout_s"] = "bad";
    try
    {
        nom::tcfg::get_to(malformed, existing);
        return 5;
    }
    catch (const nom::tcfg::mapping_error& error)
    {
        const std::string message = error.what();
        if (error.pointer != "/connection/timeout_s" || !message.contains("bad"))
        {
            return 6;
        }
    }

    nom::tcfg::config_options options;
    options.executable_path = nom::tcfg::current_executable_path();
    options.config_key = "nom_library_usage_hard_wired";
    options.overrides = {{"/connection/address", "wss://example.test/runtime"}, {"/connection/timeout_s", "15"}};
    const auto loaded = nom::tcfg::load_config<consumer::app_config>(
        options, [](std::string_view) -> std::optional<std::string> { return std::nullopt; });
    if (loaded.location.source != nom::tcfg::config_source::hard_wired || loaded.location.path ||
        loaded.value.connection->address != "wss://example.test/runtime" || *loaded.value.connection->timeout_s != 15)
    {
        return 7;
    }
    const char* arguments[] = {"consumer", "--set=/connection/timeout_s=15", "--verbose", "--check-config"};
    const auto parsed = nom::tcfg::parse_config_arguments(4, arguments);
    if (!parsed.options.check_config || parsed.options.overrides.size() != 1 ||
        parsed.options.overrides.front().pointer != "/connection/timeout_s" ||
        parsed.options.overrides.front().value != "15" ||
        parsed.remaining_arguments != std::vector<std::string>{"--verbose"})
    {
        return 8;
    }
    std::ostringstream help;
    nom::tcfg::print_config_help(help);
    if (!help.str().contains("--check-config") || !help.str().contains("silent"))
    {
        return 9;
    }
    return 0;
}
