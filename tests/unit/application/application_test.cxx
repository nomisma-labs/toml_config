// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <catch2/catch_test_macros.hpp>

#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <system_error>
#include <toml.hpp>
#include <utility>
#include <vector>

import nom.toml_config;

struct application_settings
{
    std::string host;
    int port;
    std::optional<int> timeout_ms;
};

TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(application_settings, host, port, timeout_ms)

namespace
{
    class temporary_directory
    {
    public:
        temporary_directory()
        {
            static std::atomic<unsigned int> sequence{0};
            const auto timestamp = std::chrono::steady_clock::now().time_since_epoch().count();
            root_ = std::filesystem::temp_directory_path() /
                    ("toml_application_" + std::to_string(timestamp) + "_" + std::to_string(sequence.fetch_add(1)));
            std::filesystem::create_directory(root_);
        }

        ~temporary_directory()
        {
            std::error_code ignored;
            std::filesystem::remove_all(root_, ignored);
        }

        std::filesystem::path write(const std::string& name, const std::string& content = "value=1\n") const
        {
            const auto target = file(name);
            std::filesystem::create_directories(target.parent_path());
            std::ofstream stream(target);
            stream << content;
            return std::filesystem::canonical(target);
        }

        std::filesystem::path file(const std::string& name) const
        {
            return root_ / name;
        }

        nom::config::application_options options() const
        {
            nom::config::application_options result;
            result.executable = file("bin/capture");
            result.app_name = "capture";
            return result;
        }

    private:
        std::filesystem::path root_;
    };

    auto environment(std::map<std::string, std::string> variables = {})
    {
        return [variables = std::move(variables)](const std::string& name) -> std::optional<std::string>
        {
            const auto found = variables.find(name);
            if (found == variables.end())
            {
                return std::nullopt;
            }
            return found->second;
        };
    }

    nom::config::application_options parse(std::initializer_list<const char*> arguments)
    {
        const std::vector<const char*> argv(arguments);
        return nom::config::parse_arguments(static_cast<int>(argv.size()), argv.data());
    }
} // namespace

TEST_CASE("explicit and environment configuration overrides are authoritative")
{
    temporary_directory temp;
    auto options = temp.options();
    const auto explicit_file = temp.write("explicit.toml");
    const auto environment_file = temp.write("environment.toml");
    temp.write("bin/capture.toml");
    const auto variables = environment({{"TCFG_CONFIG", environment_file.string()}});
    options.config_file = explicit_file;
    const auto explicit_result = nom::config::locate_config(options, variables);
    REQUIRE(explicit_result.file == explicit_file);
    REQUIRE(explicit_result.source == nom::config::location_kind::explicit_file);
    options.config_file.reset();
    const auto environment_result = nom::config::locate_config(options, variables);
    REQUIRE(environment_result.file == environment_file);
    REQUIRE(environment_result.source == nom::config::location_kind::environment);
    options.config_file = temp.file("missing.toml");
    REQUIRE_THROWS_AS(nom::config::locate_config(options, variables), nom::config::error);
    options.config_file.reset();
    REQUIRE_THROWS_AS(nom::config::locate_config(options, environment({{"TCFG_CONFIG", ""}})), nom::config::error);
    REQUIRE_THROWS_AS(
        nom::config::locate_config(options, environment({{"TCFG_CONFIG", temp.file("missing.toml").string()}})),
        nom::config::error);
}

TEST_CASE("explicit configuration selection does not require executable discovery")
{
    temporary_directory temp;
    const std::filesystem::path selected = temp.write("selected.toml");
    nom::config::application_options options;
    options.config_file = selected;
    REQUIRE(nom::config::locate_config(options, environment()).file == selected);
    options.executable = temp.file("unavailable/executable");
    REQUIRE(nom::config::locate_config(options, environment()).file == selected);
    options.config_file.reset();
    options.executable.clear();
    REQUIRE(nom::config::locate_config(options, environment({{"TCFG_CONFIG", selected.string()}})).file == selected);
}

TEST_CASE("ordered search directories are executable relative and discover only TOML")
{
    temporary_directory temp;
    auto options = temp.options();
    const auto first = temp.write("etc/first/capture.toml");
    temp.write("etc/first/capture.tcfg", "[tcfg]\nversion=1\n");
    const auto second = temp.write("etc/second/capture.toml");
    temp.write("bin/capture.toml");
    options.config_dirs = {"../etc/missing", "../etc/first", "../etc/second"};
    auto resolved = nom::config::locate_config(options, environment());
    REQUIRE(resolved.file == first);
    REQUIRE(resolved.source == nom::config::location_kind::search_directory);
    std::filesystem::remove(first);
    REQUIRE(nom::config::locate_config(options, environment()).file == second);
}

TEST_CASE("environment search directories follow command line directories and support app subfolders")
{
    temporary_directory temp;
    auto options = temp.options();
    const auto explicit_directory = temp.write("etc/capture/capture.toml");
    const auto from_environment = temp.write("env/capture.toml");
    temp.write("bin/capture.toml");
    options.config_dirs = {temp.file("etc")};
    const auto variables = environment({{"TCFG_CONFIG_DIR", temp.file("env").string()}});
    REQUIRE(nom::config::locate_config(options, variables).file == explicit_directory);
    options.config_dirs.clear();
    REQUIRE(nom::config::locate_config(options, variables).file == from_environment);
}

TEST_CASE("adjacent configuration precedes packaged generated and source configuration")
{
    temporary_directory temp;
    auto options = temp.options();
    const auto adjacent = temp.write("bin/capture.toml");
    const auto generated = temp.write("generated_config/capture/capture.toml");
    const auto packaged = temp.write("config/capture/capture.toml");
    auto result = nom::config::locate_config(options, environment());
    REQUIRE(result.file == adjacent);
    REQUIRE(result.source == nom::config::location_kind::adjacent);
    std::filesystem::remove(adjacent);
    result = nom::config::locate_config(options, environment());
    REQUIRE(result.file == generated);
    REQUIRE(result.source == nom::config::location_kind::packaged);
    std::filesystem::remove(generated);
    REQUIRE(nom::config::locate_config(options, environment()).file == packaged);
    std::filesystem::remove(packaged);
    REQUIRE_THROWS_AS(nom::config::locate_config(options, environment()), nom::config::error);
}

TEST_CASE("discovery rejects invalid application names and empty search directories")
{
    temporary_directory temp;
    auto options = temp.options();
    for (const auto* name : {"..", ".", "../escape", "nested/app", "nested\\app"})
    {
        options.app_name = name;
        REQUIRE_THROWS_AS(nom::config::locate_config(options, environment()), nom::config::error);
    }
    options = temp.options();
    options.config_dirs = {""};
    REQUIRE_THROWS_AS(nom::config::locate_config(options, environment()), nom::config::error);
}

TEST_CASE("argument parsing preserves application arguments and supports equals and repeats")
{
    const auto options = parse({"capture",
                                "--config=app.toml",
                                "--config-dir",
                                "one",
                                "--config-dir=two",
                                "--check-config",
                                "--print-config",
                                "-h",
                                "--application-flag",
                                "argument",
                                "--",
                                "--config",
                                "literal"});
    REQUIRE(options.config_file == "app.toml");
    REQUIRE(options.config_dirs == std::vector<std::filesystem::path>{"one", "two"});
    REQUIRE(options.remaining_arguments ==
            std::vector<std::string>{"--application-flag", "argument", "--config", "literal"});
    REQUIRE(options.check_config);
    REQUIRE(options.print_config);
    REQUIRE(options.help);
    REQUIRE(options.executable.empty());
    REQUIRE(options.app_name.empty());
    REQUIRE(parse({"capture", "-c", "app.toml"}).config_file == "app.toml");
}

TEST_CASE("former composition arguments are returned as unknown application arguments")
{
    const nom::config::application_options options = parse({"capture", "--overlay", "extra.toml", "--set=port=42"});
    REQUIRE(options.remaining_arguments == std::vector<std::string>{"--overlay", "extra.toml", "--set=port=42"});
}

TEST_CASE("argument parsing accepts an unavailable or empty invocation name without discovery")
{
    for (const char* invocation : {"/unavailable/directory/capture", ""})
    {
        const nom::config::application_options help = parse({invocation, "--help"});
        REQUIRE(help.help);
        REQUIRE(help.executable.empty());
        const nom::config::application_options explicit_file = parse({invocation, "--config", "app.toml"});
        REQUIRE(explicit_file.config_file == "app.toml");
        REQUIRE(explicit_file.executable.empty());
    }
}

TEST_CASE("argument parsing rejects missing empty and duplicate configuration values")
{
    REQUIRE_THROWS_AS(parse({"capture", "--config"}), nom::config::error);
    REQUIRE_THROWS_AS(parse({"capture", "--config", "--help"}), nom::config::error);
    REQUIRE_THROWS_AS(parse({"capture", "--config-dir="}), nom::config::error);
    REQUIRE_THROWS_AS(parse({"capture", "--config=a.toml", "-c", "b.toml"}), nom::config::error);
    REQUIRE_THROWS_AS(parse({"capture", "--config-dir", nullptr}), nom::config::error);
    REQUIRE_THROWS_AS(parse({"capture", nullptr}), nom::config::error);
    REQUIRE_THROWS_AS(nom::config::parse_arguments(0, nullptr), nom::config::error);
}

TEST_CASE("ordinary TOML loads and formats without interpreting application tables")
{
    temporary_directory temp;
    const std::filesystem::path input =
        temp.write("plain.toml", "host='example'\nport=42\n[tcfg]\nversion=1\nextends=['unavailable.tcfg']\n");
    const nom::config::document loaded = nom::config::load(input);
    const application_settings settings = nom::config::bind<application_settings>(loaded);
    REQUIRE(settings.host == "example");
    REQUIRE(settings.port == 42);
    REQUIRE(toml::find<int>(loaded.value, "tcfg", "version") == 1);
    std::istringstream formatted(nom::config::format(loaded));
    const toml::value parsed = toml::parse(formatted, "formatted", toml::spec::v(1, 0, 0));
    REQUIRE(toml::find<std::string>(parsed, "host") == "example");
    REQUIRE(toml::find(parsed, "tcfg", "extends").as_array().front().as_string() == "unavailable.tcfg");
}

TEST_CASE("C++ loading rejects tcfg missing files and malformed TOML")
{
    temporary_directory temp;
    const std::filesystem::path tcfg = temp.write("input.tcfg", "[tcfg]\nversion=1\n");
    const std::filesystem::path invalid = temp.write("invalid.toml", "value = unquoted\n");
    REQUIRE_THROWS_AS(nom::config::load(tcfg), nom::config::error);
    REQUIRE_THROWS_AS(nom::config::load(temp.file("missing.toml")), nom::config::error);
    REQUIRE_THROWS_AS(nom::config::load(invalid), nom::config::error);
    nom::config::application_options options = temp.options();
    options.config_file = tcfg;
    REQUIRE_THROWS_AS(nom::config::locate_config(options, environment()), nom::config::error);
    options.config_file.reset();
    REQUIRE_THROWS_AS(nom::config::locate_config(options, environment({{"TCFG_CONFIG", tcfg.string()}})),
                      nom::config::error);
}

TEST_CASE("file paths containing NUL are rejected before filesystem access")
{
    temporary_directory temp;
    const std::filesystem::path input = temp.write("valid.toml");
    const std::filesystem::path invalid = input.string() + '\0' + "suffix.toml";
    REQUIRE_THROWS_AS(nom::config::load(invalid), nom::config::error);
    nom::config::application_options options = temp.options();
    options.config_file = invalid;
    REQUIRE_THROWS_AS(nom::config::locate_config(options, environment()), nom::config::error);
}

TEST_CASE("typed initialization loads TOML and preserves optional defaults")
{
    temporary_directory temp;
    auto app = temp.options();
    app.config_file = temp.write("app.toml", "host='initial'\nport=5\n");
    const nom::config::initialized<application_settings> initialized =
        nom::config::initialize<application_settings>(app);
    REQUIRE(initialized.value.host == "initial");
    REQUIRE(initialized.value.port == 5);
    REQUIRE(initialized.value.timeout_ms.value_or(1000) == 1000);
    REQUIRE(initialized.location.source == nom::config::location_kind::explicit_file);
    REQUIRE(nom::config::resolve_path(initialized.location, "data/../records") == temp.file("records"));
    REQUIRE(nom::config::resolve_path(initialized.location, temp.file("absolute")) == temp.file("absolute"));
    app.config_file = temp.write("wrong_type.toml", "host='initial'\nport='invalid'\n");
    REQUIRE_THROWS_AS(nom::config::initialize<application_settings>(app), nom::config::error);
    app.config_file = temp.write("incomplete.toml", "port=1\n");
    REQUIRE_THROWS_AS(nom::config::initialize<application_settings>(app), nom::config::error);
}
