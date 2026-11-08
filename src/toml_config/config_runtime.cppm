// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

module;

#include "toml11.h"

export module nom.toml_config:runtime;

import std;

export namespace nom::tcfg
{
    enum class config_stage
    {
        arguments,
        location,
        reading,
        parsing,
        substitution,
        overrides,
        mapping,
        validation
    };

    enum class config_source
    {
        command_line,
        environment_file,
        executable_directory,
        search_directory,
        hard_wired
    };

    std::string_view config_stage_name(config_stage stage) noexcept;
    std::string_view config_source_name(config_source source) noexcept;

    class config_error : public std::runtime_error
    {
    public:
        config_error(config_stage stage,
                     std::string message,
                     std::optional<std::filesystem::path> file = {},
                     std::string pointer = {});

        config_stage stage;
        std::optional<std::filesystem::path> file;
        std::string pointer;
    };

    struct config_override
    {
        std::string pointer;
        std::string value;
    };

    enum class config_check_mode
    {
        full,
        view,
        silent
    };

    struct config_options
    {
        std::filesystem::path executable_path;
        std::string config_key;
        std::optional<std::filesystem::path> config_file;
        std::vector<config_override> overrides;
        bool check_config{};
        config_check_mode check_mode{config_check_mode::full};
    };

    struct config_location
    {
        std::optional<std::filesystem::path> path;
        config_source source{config_source::hard_wired};
        std::string search_details{};
    };

    struct parsed_config_arguments
    {
        config_options options;
        std::vector<std::string> remaining_arguments;
        bool help{};
    };

    using environment_lookup = std::function<std::optional<std::string>(std::string_view)>;
    using mapping_probe = std::function<void(const toml::value&)>;

    namespace detail
    {
        void validate_utf8(std::string_view text);
    }

    std::optional<std::string> process_environment(std::string_view name);

    // The span contains arguments after argv[0]; unrecognized arguments are retained.
    parsed_config_arguments parse_config_arguments(std::span<const std::string_view> arguments,
                                                   std::string config_key = {});
    parsed_config_arguments parse_config_arguments(int argc, const char* const* argv, std::string config_key = {});
    void print_config_help(std::ostream& output);

    std::filesystem::path current_executable_path();
    config_location locate_config(const config_options& options,
                                  const environment_lookup& environment = process_environment);

    toml::value parse_config(std::string_view source, std::string_view label = "TOML");
    std::string format_config(toml::value document);

    toml::value read_config(const config_location& location);
    void substitute_runtime_variables(toml::value& document,
                                      const environment_lookup& environment = process_environment,
                                      const config_location& location = {});
    void apply_config_overrides(toml::value& document,
                                std::span<const config_override> overrides,
                                const mapping_probe& probe,
                                const config_location& location = {});
} // namespace nom::tcfg
