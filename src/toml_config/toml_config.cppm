// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

module;

#include <exception>
#include <filesystem>
#include <functional>
#include <optional>
#include <stdexcept>
#include <string>
#include <toml.hpp>
#include <utility>
#include <vector>

export module nom.toml_config;

export namespace nom::config
{
    class error : public std::runtime_error
    {
    public:
        using std::runtime_error::runtime_error;
    };

    struct document
    {
        toml::value value;
    };

    document load(const std::filesystem::path& input);
    std::string format(const document& config);

    enum class location_kind
    {
        explicit_file,
        environment,
        search_directory,
        adjacent,
        packaged
    };

    struct located_config
    {
        std::filesystem::path file;
        location_kind source;
    };

    struct application_options
    {
        // Empty selects the running executable lazily, only for directory discovery.
        std::filesystem::path executable;
        std::string app_name;
        std::optional<std::filesystem::path> config_file;
        std::vector<std::filesystem::path> config_dirs;
        std::vector<std::string> remaining_arguments;
        bool check_config{false};
        bool print_config{false};
        bool help{false};
    };

    // Parsing does no filesystem or OS discovery, and never exits or prints.
    // Unknown arguments are returned to the application.
    application_options parse_arguments(int argc, const char* const* argv);
    std::string argument_help();
    located_config locate_config(const application_options& options,
                                 const std::function<std::optional<std::string>(const std::string&)>& environment = {});
    std::filesystem::path resolve_path(const located_config& location, const std::filesystem::path& value);

    template <typename Config> Config bind(const document& input)
    {
        try
        {
            return toml::get<Config>(input.value);
        }
        catch (const std::exception& exception)
        {
            throw error(std::string("configuration binding failed: ") + exception.what());
        }
    }

    template <typename Config> struct initialized
    {
        Config value;
        document resolved;
        located_config location;
    };

    template <typename Config> initialized<Config> initialize(const application_options& app)
    {
        auto location = locate_config(app);
        auto resolved = load(location.file);
        auto value = bind<Config>(resolved);
        return {std::move(value), std::move(resolved), std::move(location)};
    }
} // namespace nom::config
