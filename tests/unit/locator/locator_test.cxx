// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <catch2/catch_test_macros.hpp>

import std;

import nom.toml_config;

namespace
{
    namespace fs = std::filesystem;
    using namespace nom::tcfg;

    struct temporary_directory
    {
        fs::path path;

        temporary_directory()
        {
            static std::atomic<unsigned> sequence{};
            const auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
            path = fs::temp_directory_path() /
                   ("nom_tcfg_locator_" + std::to_string(tick) + "_" + std::to_string(sequence.fetch_add(1)));
            fs::create_directory(path);
        }

        ~temporary_directory()
        {
            std::error_code ignored;
            fs::remove_all(path, ignored);
        }

        fs::path file(const fs::path& relative)
        {
            const auto result = path / relative;
            fs::create_directories(result.parent_path());
            std::ofstream(result) << "{}";
            return result;
        }

        config_options options()
        {
            config_options result;
            result.executable_path = file("bin/example");
            return result;
        }
    };

    environment_lookup environment(std::map<std::string, std::string, std::less<>> entries = {})
    {
        return [entries = std::move(entries)](std::string_view name) -> std::optional<std::string>
        {
            if (const auto found = entries.find(name); found != entries.end())
            {
                return found->second;
            }
            return std::nullopt;
        };
    }

    void require_location_error(const config_options& options, const environment_lookup& lookup)
    {
        try
        {
            (void)locate_config(options, lookup);
            FAIL("expected config location to fail");
        }
        catch (const config_error& error)
        {
            CHECK(error.stage == config_stage::location);
        }
    }
} // namespace

TEST_CASE("Explicit config selection wins without consulting lower priorities", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    options.config_file = temporary.file("selected.toml");
    options.executable_path.clear();
    options.config_key = "invalid/key";
    const auto result = locate_config(options,
                                      [](std::string_view) -> std::optional<std::string>
                                      {
                                          FAIL("explicit selection must not read the environment");
                                          return std::nullopt;
                                      });
    CHECK(result.path == options.config_file);
    CHECK(result.source == config_source::command_line);
}

TEST_CASE("Environment file precedes automatic config lookup", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    temporary.file("bin/example.toml");
    const auto selected = temporary.file("selected.toml");
    const auto result =
        locate_config(options, environment({{"NOM_CONFIG", selected.string()}, {"NOM_CONFIG_DIR", ""}}));
    CHECK(result.path == selected);
    CHECK(result.source == config_source::environment_file);
}

TEST_CASE("Explicit config failures never fall through", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    temporary.file("bin/example.toml");

    SECTION("Missing command line selection")
    {
        options.config_file = temporary.path / "missing.toml";
        require_location_error(options, environment());
    }
    SECTION("Empty command line selection")
    {
        options.config_file = fs::path{};
        require_location_error(options, environment());
    }
    SECTION("Missing environment selection")
    {
        require_location_error(options, environment({{"NOM_CONFIG", (temporary.path / "missing.toml").string()}}));
    }
    SECTION("Empty environment selection")
    {
        require_location_error(options, environment({{"NOM_CONFIG", ""}}));
    }
    SECTION("Selected directory")
    {
        options.config_file = temporary.path;
        require_location_error(options, environment());
    }
}

TEST_CASE("Relative explicit filenames use the working directory", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    const auto selected = temporary.file("selected.toml");
    const auto relative = fs::relative(selected, fs::current_path());

    SECTION("Command line filename")
    {
        options.config_file = relative;
        const auto result = locate_config(options, environment());
        REQUIRE(result.path);
        CHECK(fs::equivalent(*result.path, selected));
        CHECK(result.source == config_source::command_line);
    }
    SECTION("Environment filename")
    {
        const auto result = locate_config(options, environment({{"NOM_CONFIG", relative.string()}}));
        REQUIRE(result.path);
        CHECK(fs::equivalent(*result.path, selected));
        CHECK(result.source == config_source::environment_file);
    }
}

TEST_CASE("Executable basename selects a bundled config before search directories", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    const auto selected = temporary.file("bin/example.toml");
    const auto result = locate_config(options, environment({{"NOM_CONFIG_DIR", ""}}));
    CHECK(result.path == selected);
    CHECK(result.source == config_source::executable_directory);
}

TEST_CASE("The config key can select a shared config independently of executable name", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    options.config_key = "shared";
    temporary.file("bin/example.toml");
    const auto selected = temporary.file("bin/shared.toml");
    const auto result = locate_config(options, environment());
    CHECK(result.path == selected);
    CHECK(result.source == config_source::executable_directory);
}

TEST_CASE("A usable symbolic link can select a config", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    temporary.file("selected.toml");
    const auto link = temporary.path / "bin/example.toml";
    fs::create_symlink("../selected.toml", link);
    const auto result = locate_config(options, environment());
    CHECK(result.path == link);
    CHECK(result.source == config_source::executable_directory);
}

TEST_CASE("Search directories support generated and collected config layouts", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    fs::path selected;

    SECTION("Flat config wins over nested config in the same directory")
    {
        selected = temporary.file("config/example.toml");
        temporary.file("config/example/example.toml");
    }
    SECTION("Nested collected config is found")
    {
        selected = temporary.file("config/example/example.toml");
    }
    const auto result = locate_config(options, environment({{"NOM_CONFIG_DIR", (temporary.path / "config").string()}}));
    CHECK(result.path == selected);
    CHECK(result.source == config_source::search_directory);
}

TEST_CASE("Relative search paths are based on the executable directory", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    const auto selected = temporary.file("config/example/example.toml");
    const auto result = locate_config(options, environment({{"NOM_CONFIG_DIR", "../config"}}));
    REQUIRE(result.path);
    CHECK(fs::equivalent(*result.path, selected));
    CHECK(result.source == config_source::search_directory);
}

TEST_CASE("Search directories retain order and skip missing candidates", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    const auto selected = temporary.file("first/example/example.toml");
    temporary.file("second/example.toml");
    const auto paths = (temporary.path / "missing").string() + ":" + (temporary.path / "first").string() + ":" +
                       (temporary.path / "second").string();
    const auto result = locate_config(options, environment({{"NOM_CONFIG_DIR", paths}}));
    CHECK(result.path == selected);
}

TEST_CASE("Empty search directory components are invalid", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    for (const std::string value : {"", ":missing", "missing:", "one::two"})
    {
        INFO(value);
        require_location_error(options, environment({{"NOM_CONFIG_DIR", value}}));
    }
}

TEST_CASE("Existing unusable candidates stop automatic search", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    temporary.file("second/example.toml");

    SECTION("Directory in place of a config")
    {
        fs::create_directories(temporary.path / "first/example.toml");
    }
    SECTION("Dangling symlink in place of a config")
    {
        fs::create_directories(temporary.path / "first");
        fs::create_symlink("missing.toml", temporary.path / "first/example.toml");
    }
    const auto paths = (temporary.path / "first").string() + ":" + (temporary.path / "second").string();
    require_location_error(options, environment({{"NOM_CONFIG_DIR", paths}}));
}

TEST_CASE("An unusable bundled config prevents later search", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    fs::create_directories(temporary.path / "bin/example.toml");
    temporary.file("config/example.toml");
    require_location_error(options, environment({{"NOM_CONFIG_DIR", "../config"}}));
}

TEST_CASE("Hard-wired config is selected only after clean lookup exhaustion", "[locator]")
{
    temporary_directory temporary;
    const auto options = temporary.options();
    const auto result = locate_config(options, environment({{"NOM_CONFIG_DIR", "../missing:../also_missing"}}));
    CHECK_FALSE(result.path);
    CHECK(result.source == config_source::hard_wired);
}

TEST_CASE("Unreadable config files are errors rather than missing candidates", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    const auto unreadable = temporary.file("bin/example.toml");
    fs::permissions(unreadable, fs::perms::none);
    if (std::ifstream(unreadable).is_open())
    {
        SKIP("process privileges bypass file read permissions");
    }
    SECTION("Explicit selection")
    {
        options.config_file = unreadable;
    }
    SECTION("Automatic selection")
    {
        temporary.file("other/example.toml");
    }
    require_location_error(options, environment({{"NOM_CONFIG_DIR", "../other"}}));
}

TEST_CASE("Automatic config keys are single filename components", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    for (const std::string key : {".", "..", "../shared", "directory/key"})
    {
        INFO(key);
        options.config_key = key;
        require_location_error(options, environment());
    }
}

TEST_CASE("The local OS utility discovers the executable without argv zero", "[locator]")
{
    const auto executable = current_executable_path();
    CHECK(executable.is_absolute());
    CHECK(fs::is_regular_file(executable));
    CHECK_FALSE(executable.filename().empty());
}

TEST_CASE("Full checks report actual lookup order and stop at the selected file", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    options.check_config = true;
    const auto selected = temporary.file("first/example/example.toml");
    const auto later = temporary.file("later/example.toml");
    const auto first_directory = (temporary.path / "first").string();
    const auto later_directory = later.parent_path().string();
    const auto result =
        locate_config(options, environment({{"NOM_CONFIG_DIR", first_directory + ':' + later_directory}}));
    CHECK(result.path == selected);
    const auto& details = result.search_details;
    const auto bundled = details.find("Missing candidate: " + (temporary.path / "bin/example.toml").string());
    const auto flat = details.find("Missing candidate: " + (temporary.path / "first/example.toml").string());
    const auto nested = details.find("Selected candidate: " + selected.string());
    REQUIRE(bundled != std::string::npos);
    REQUIRE(flat != std::string::npos);
    REQUIRE(nested != std::string::npos);
    CHECK(bundled < flat);
    CHECK(flat < nested);
    CHECK(details.contains("Executable: " + options.executable_path.string()));
    CHECK(details.contains("Config key: example\n"));
    CHECK_FALSE(details.contains("Search directory: " + later_directory));
}

TEST_CASE("Check diagnostics retain explicit-selection precedence", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    options.config_file = temporary.file("selected.toml");
    options.config_key = "invalid/key";
    options.check_config = true;
    const auto result =
        locate_config(options,
                      [](std::string_view) -> std::optional<std::string>
                      {
                          FAIL("full output must not consult environment sources overridden by --config");
                          return std::nullopt;
                      });
    CHECK(result.search_details.contains("--config: " + options.config_file->string()));
    CHECK(result.search_details.contains("Remaining locations: not searched after selection"));
}

TEST_CASE("Lookup detail collection is limited to full checks", "[locator]")
{
    temporary_directory temporary;
    auto options = temporary.options();
    temporary.file("bin/example.toml");
    CHECK(locate_config(options, environment()).search_details.empty());
    options.check_config = true;
    for (const auto mode : {config_check_mode::view, config_check_mode::silent})
    {
        options.check_mode = mode;
        CHECK(locate_config(options, environment()).search_details.empty());
    }
}
