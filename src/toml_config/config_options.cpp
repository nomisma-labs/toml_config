// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

module;

#include <boost/program_options.hpp>

module nom.toml_config;

import std;

namespace nom::tcfg
{
    std::string_view config_stage_name(config_stage stage) noexcept
    {
        switch (stage)
        {
        case config_stage::arguments:
            return "arguments";
        case config_stage::location:
            return "location";
        case config_stage::reading:
            return "reading";
        case config_stage::parsing:
            return "parsing";
        case config_stage::substitution:
            return "runtime substitution";
        case config_stage::overrides:
            return "overrides";
        case config_stage::mapping:
            return "mapping";
        case config_stage::validation:
            return "validation";
        }
        return "unknown";
    }

    std::string_view config_source_name(config_source source) noexcept
    {
        switch (source)
        {
        case config_source::command_line:
            return "command line";
        case config_source::environment_file:
            return "NOM_CONFIG";
        case config_source::executable_directory:
            return "executable directory";
        case config_source::search_directory:
            return "NOM_CONFIG_DIR";
        case config_source::hard_wired:
            return "hard-wired";
        }
        return "unknown";
    }

    namespace
    {
        std::string error_message(config_stage stage,
                                  const std::string& message,
                                  const std::optional<std::filesystem::path>& file,
                                  const std::string& pointer)
        {
            std::string result = "Config " + std::string(config_stage_name(stage));
            if (file)
            {
                result += " [" + file->string() + "]";
            }
            if (!pointer.empty())
            {
                result += " at " + pointer;
            }
            return result + ": " + message;
        }

        boost::program_options::options_description config_description()
        {
            namespace po = boost::program_options;
            po::options_description description("Config options");
            description.add_options()("help,h", "Show application and configuration help without loading a config")(
                "config,c",
                po::value<std::string>()->value_name("FILE"),
                "Select a TOML file (relative to the working directory); overrides environment lookup")(
                "set",
                po::value<std::string>()->value_name("POINTER=value"),
                "Override an existing TOML value after runtime substitution; repeatable, applied in order")(
                "check-config,k",
                po::value<std::string>()->implicit_value("full")->value_name("MODE"),
                "Validate and exit: full = lookup details and final TOML (default), view = final TOML only, "
                "silent = OK only. Use --check-config=MODE or -k MODE");
            return description;
        }

        bool is_check_mode(std::string_view value)
        {
            return value == "full" || value == "view" || value == "silent";
        }

        bool is_config_option(std::string_view token, const boost::program_options::options_description& description)
        {
            if (token.starts_with("--"))
            {
                const auto name = token.substr(2);
                const std::string key(name.substr(0, name.find('=')));
                return !key.empty() && description.find_nothrow(key, false) != nullptr;
            }
            return token.size() >= 2 && token.front() == '-' && (token[1] == 'c' || token[1] == 'k' || token[1] == 'h');
        }
    } // namespace

    void print_config_help(std::ostream& output)
    {
        output << config_description();
    }

    config_error::config_error(config_stage stage,
                               std::string message,
                               std::optional<std::filesystem::path> file,
                               std::string pointer)
        : std::runtime_error(error_message(stage, message, file, pointer)), stage(stage), file(std::move(file)),
          pointer(std::move(pointer))
    {
    }

    std::optional<std::string> process_environment(std::string_view name)
    {
        if (name.empty() || name.find('\0') != std::string_view::npos || name.find('=') != std::string_view::npos)
        {
            return std::nullopt;
        }
        const std::string key(name);
        if (const char* value = std::getenv(key.c_str()))
        {
            return std::string(value);
        }
        return std::nullopt;
    }

    parsed_config_arguments parse_config_arguments(std::span<const std::string_view> arguments, std::string config_key)
    {
        namespace po = boost::program_options;
        parsed_config_arguments result;
        result.options.config_key = std::move(config_key);

        // Boost does not retain the terminator in parsed_options; preserve the app's tail ourselves.
        const auto boundary = std::find(arguments.begin(), arguments.end(), "--");
        const std::vector<std::string> tokens(arguments.begin(), boundary);
        const auto description = config_description();

        try
        {
            const auto parsed =
                po::command_line_parser(tokens)
                    .options(description)
                    .style(po::command_line_style::allow_long | po::command_line_style::long_allow_adjacent |
                           po::command_line_style::long_allow_next | po::command_line_style::allow_short |
                           po::command_line_style::allow_dash_for_short | po::command_line_style::short_allow_adjacent |
                           po::command_line_style::short_allow_next)
                    .allow_unregistered()
                    .extra_style_parser(
                        [&description](std::vector<std::string>& remaining) -> std::vector<po::option>
                        {
                            const auto& token = remaining.front();
                            // An optional mode must not consume an unrelated application positional argument.
                            if ((token == "--check-config" || token == "-k") &&
                                (remaining.size() == 1 || !is_check_mode(remaining[1])))
                            {
                                po::option option;
                                option.string_key = "check-config";
                                option.value.push_back("full");
                                option.original_tokens.push_back(token);
                                remaining.erase(remaining.begin());
                                return {std::move(option)};
                            }
                            // Preserve app-owned options verbatim, including short groups and --label=.
                            if (token.starts_with('-') && !is_config_option(token, description))
                            {
                                po::option option;
                                option.string_key = token;
                                option.unregistered = true;
                                option.original_tokens.push_back(token);
                                remaining.erase(remaining.begin());
                                return {std::move(option)};
                            }
                            return {};
                        })
                    .run();

            // Read occurrences directly to preserve override order; the last check mode wins.
            for (const auto& option : parsed.options)
            {
                if (option.unregistered || option.string_key.empty())
                {
                    continue;
                }
                if (option.string_key == "help")
                {
                    result.help = true;
                    continue;
                }
                if (option.string_key == "check-config")
                {
                    const auto& mode = option.value.front();
                    if (!is_check_mode(mode))
                    {
                        throw config_error(config_stage::arguments,
                                           "--check-config mode must be full, view, or silent");
                    }
                    result.options.check_config = true;
                    result.options.check_mode = mode == "view"     ? config_check_mode::view
                                                : mode == "silent" ? config_check_mode::silent
                                                                   : config_check_mode::full;
                    continue;
                }
                const auto& value = option.value.front();
                if (option.original_tokens.size() > 1 && is_config_option(value, description))
                {
                    throw config_error(config_stage::arguments, "--" + option.string_key + " requires a value");
                }
                if (option.string_key == "config")
                {
                    if (value.empty())
                    {
                        throw config_error(config_stage::arguments, "--config filename must not be empty");
                    }
                    if (result.options.config_file)
                    {
                        throw config_error(config_stage::arguments, "--config may only be specified once");
                    }
                    result.options.config_file = value;
                }
                else
                {
                    const auto separator = value.find('=');
                    if (separator == std::string::npos)
                    {
                        throw config_error(config_stage::arguments, "--set requires <TOML-pointer>=<value>");
                    }
                    result.options.overrides.push_back({value.substr(0, separator), value.substr(separator + 1)});
                }
            }
            result.remaining_arguments = po::collect_unrecognized(parsed.options, po::include_positional);
        }
        catch (const po::error& error)
        {
            throw config_error(config_stage::arguments, error.what());
        }
        result.remaining_arguments.insert(result.remaining_arguments.end(), boundary, arguments.end());
        return result;
    }

    parsed_config_arguments parse_config_arguments(int argc, const char* const* argv, std::string config_key)
    {
        if (argc < 0 || (argc > 0 && argv == nullptr))
        {
            throw config_error(config_stage::arguments, "invalid argument array");
        }
        std::vector<std::string_view> arguments;
        for (int index = 1; index < argc; ++index)
        {
            if (argv[index] == nullptr)
            {
                throw config_error(config_stage::arguments, "null command-line argument");
            }
            arguments.emplace_back(argv[index]);
        }
        return parse_config_arguments(arguments, std::move(config_key));
    }
} // namespace nom::tcfg
