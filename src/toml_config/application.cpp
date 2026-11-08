// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

module;

#include "util/os.h"

#include <cstdlib>
#include <filesystem>
#include <functional>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

module nom.toml_config;

namespace nom::config
{
    namespace
    {
        namespace fs = std::filesystem;

        std::optional<std::string> read_environment(
            const std::string& name, const std::function<std::optional<std::string>(const std::string&)>& environment)
        {
            if (environment)
                return environment(name);
            if (const auto* value = std::getenv(name.c_str()))
                return std::string(value);
            return std::nullopt;
        }

        std::vector<fs::path> split_paths(const std::string& paths)
        {
            constexpr char separator = ':';
            std::vector<fs::path> result;
            std::istringstream input(paths);
            std::string item;
            while (std::getline(input, item, separator))
                if (!item.empty())
                    result.emplace_back(item);
            return result;
        }

        located_config require_file(const fs::path& path, location_kind source)
        {
            if (path.string().find('\0') != std::string::npos)
                throw error("configuration paths cannot contain a NUL character");
            if (path.extension() != ".toml")
                throw error("C++ configuration requires a .toml file; generate it with cfggen.py");
            std::error_code ec;
            if (path.empty() || !fs::is_regular_file(path, ec))
                throw error("configuration file is not accessible: " + path.string());
            const auto canonical = fs::canonical(path, ec);
            if (ec)
                throw error("cannot resolve configuration file: " + path.string() + ": " + ec.message());
            return {canonical, source};
        }

        fs::path application_executable(const fs::path& configured)
        {
            std::error_code failure;
            const auto executable =
                configured.empty() ? detail::os::current_executable(failure) : fs::absolute(configured, failure);
            if (failure)
                throw error("cannot determine executable path: " + failure.message());
            return executable.lexically_normal();
        }
    } // namespace

    application_options parse_arguments(int argc, const char* const* argv)
    {
        if (argc < 1 || argv == nullptr || argv[0] == nullptr)
            throw error("an executable argument is required");
        application_options result;
        bool positional = false;
        for (int index = 1; index < argc; ++index)
        {
            if (argv[index] == nullptr)
                throw error("null command-line argument");
            const std::string argument(argv[index]);
            if (positional)
            {
                result.remaining_arguments.push_back(argument);
                continue;
            }
            if (argument == "--")
            {
                positional = true;
                continue;
            }
            if (argument == "--help" || argument == "-h")
                result.help = true;
            else if (argument == "--check-config")
                result.check_config = true;
            else if (argument == "--print-config")
                result.print_config = true;
            else
            {
                const auto equal = argument.find('=');
                const auto key = argument.substr(0, equal);
                if (key != "--config" && key != "-c" && key != "--config-dir")
                {
                    result.remaining_arguments.push_back(argument);
                    continue;
                }
                std::string value;
                if (equal != std::string::npos)
                    value = argument.substr(equal + 1);
                else
                {
                    if (index + 1 >= argc || argv[index + 1] == nullptr ||
                        std::string_view(argv[index + 1]).starts_with("--"))
                        throw error("missing value for " + key);
                    value = argv[++index];
                }
                if (value.empty())
                    throw error("empty value for " + key);
                if (key == "--config" || key == "-c")
                {
                    if (result.config_file)
                        throw error("--config may only be specified once");
                    result.config_file = value;
                }
                else
                    result.config_dirs.emplace_back(value);
            }
        }
        return result;
    }

    std::string argument_help()
    {
        return "  --config, -c FILE   Use this .toml file\n"
               "  --config-dir DIR   Search this directory (repeatable, executable-relative)\n"
               "  --check-config     Load and bind without starting application work\n"
               "  --print-config     Print TOML; may contain sensitive values\n"
               "  --help, -h         Show application help\n";
    }

    located_config locate_config(const application_options& options,
                                 const std::function<std::optional<std::string>(const std::string&)>& environment)
    {
        if (options.config_file)
            return require_file(*options.config_file, location_kind::explicit_file);
        if (const auto file = read_environment("TCFG_CONFIG", environment))
            return require_file(*file, location_kind::environment);

        const auto executable = application_executable(options.executable);
        const auto directory = executable.parent_path();
        const auto name = options.app_name.empty() ? executable.stem().string() : options.app_name;
        if (name.empty() || name == "." || name == ".." || name.find('/') != std::string::npos ||
            name.find('\\') != std::string::npos)
            throw error("app_name must be a single nonempty file name");
        std::vector<fs::path> attempted;
        const auto search = [&](const fs::path& root, location_kind source) -> std::optional<located_config>
        {
            const auto absolute = root.is_absolute() ? root : directory / root;
            const auto candidate = (absolute / (name + ".toml")).lexically_normal();
            attempted.push_back(candidate);
            std::error_code ec;
            if (fs::exists(candidate, ec))
                return require_file(candidate, source);
            if (ec)
                throw error("cannot search configuration: " + candidate.string() + ": " + ec.message());
            return std::nullopt;
        };

        auto directories = options.config_dirs;
        if (const auto configured = read_environment("TCFG_CONFIG_DIR", environment))
        {
            const auto entries = split_paths(*configured);
            directories.insert(directories.end(), entries.begin(), entries.end());
        }
        for (const auto& root : directories)
        {
            if (root.empty())
                throw error("empty configuration search directory");
            if (const auto found = search(root, location_kind::search_directory))
                return *found;
            if (const auto found = search(root / name, location_kind::search_directory))
                return *found;
        }
        if (const auto found = search(directory, location_kind::adjacent))
            return *found;
        for (const auto* folder : {"generated_config", "config"})
            if (const auto found = search(directory.parent_path() / folder / name, location_kind::packaged))
                return *found;

        std::string message = "no configuration found; checked --config, TCFG_CONFIG, and";
        for (const auto& path : attempted)
            message += "\n  " + path.string();
        throw error(message);
    }

    std::filesystem::path resolve_path(const located_config& location, const std::filesystem::path& value)
    {
        return (value.is_absolute() ? value : location.file.parent_path() / value).lexically_normal();
    }
} // namespace nom::config
