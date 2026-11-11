// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT
#include <catch2/catch_test_macros.hpp>
#include <toml_config/config.h>
import std;
import nom.toml_config;

TEST_CASE("TOML profile preserves categories and truncates submicrosecond precision")
{
    auto document = nom::tcfg::parse_config(R"(
integer = 9223372036854775807
floating = 1.2345678901234567
small = 5e-324
mixed = [1, true, 'text', {}, []]
date = 2026-11-08
time = 12:34:56.123456789
local = 2026-11-08T12:34:56.987654321
offset = 2026-11-08T12:34:56.123456789+23:59
positive = inf
negative = -inf
nan = nan
empty = {}
)");
    CHECK(document.at("integer").as_integer() == std::numeric_limits<std::int64_t>::max());
    CHECK(document.at("floating").is_floating());
    CHECK(document.at("date").is_local_date());
    CHECK(document.at("time").as_local_time().nanosecond == 0);
    CHECK(document.at("time").as_local_time().microsecond == 456);
    CHECK(document.at("local").as_local_datetime().time.nanosecond == 0);
    CHECK(document.at("offset").as_offset_datetime().time.nanosecond == 0);
    CHECK(document.at("offset").as_offset_datetime().offset.hour == 23);
    const auto restored = nom::tcfg::parse_config(nom::tcfg::format_config(document));
    for (const std::string key :
         {"integer", "floating", "small", "mixed", "date", "time", "local", "offset", "positive", "negative", "empty"})
    {
        CAPTURE(key);
        CHECK(restored.at(key) == document.at(key));
    }
    CHECK(std::isnan(restored.at("nan").as_floating()));
    CHECK(std::signbit(restored.at("negative").as_floating()));
    CHECK(nom::tcfg::format_config(nom::tcfg::parse_config("")).empty());
}

TEST_CASE("TOML profile rejects unsupported syntax and values before mapping")
{
    for (const std::string source : {"a = 9223372036854775808",
                                     "a = -9223372036854775809",
                                     "a = 1e999",
                                     "a = -1e999",
                                     "a = 0000-01-01",
                                     "a = 2026-02-30",
                                     "a = 23:59:60",
                                     "a = 2026-01-01T23:59:60Z",
                                     "a = 2026-01-01T12:00:00+00:60",
                                     "a = 2026-01-01T12:00:00+24:00",
                                     "a = 1\ra = 2",
                                     "a = 1\na = 2",
                                     "a = { b = 1 }\n[a]\nc = 2",
                                     "a = null",
                                     "a = '\xff'",
                                     "a = '\xed\xa0\x80'",
                                     "\xef\xbb\xbfvalue = 1",
                                     "a = '\xf0\x80\x80\x80'"})
    {
        CAPTURE(source);
        REQUIRE_THROWS(nom::tcfg::parse_config(source));
    }
    REQUIRE_NOTHROW(nom::tcfg::parse_config("a = 1\r\nb = '日本語'\r\n"));
}

TEST_CASE("formatting rejects invalid values from custom native converters")
{
    for (const auto& value : {toml::value(toml::local_date(0, toml::month_t::Jan, 1)),
                              toml::value(toml::local_time(0, 0, 60)),
                              toml::value(std::string("\xff")),
                              toml::value()})
        REQUIRE_THROWS(nom::tcfg::format_config(toml::value(toml::table{{"value", value}})));
}

TEST_CASE("runtime substitution is recursive single pass and preserves keys and scalar types")
{
    auto doc = nom::tcfg::parse_config(R"(
'{tcfg:run-var KEY}' = 'unchanged'
array = ['prefix {tcfg:run-var A}', '{tcfg:run-var EMPTY}']
nested = { value = '{tcfg:run-var A}' }
integer = 20
)");
    auto lookup = [](std::string_view name) -> std::optional<std::string>
    {
        if (name == "A")
            return "{tcfg:run-var OTHER}";
        if (name == "EMPTY")
            return "";
        return {};
    };
    nom::tcfg::substitute_runtime_variables(doc, lookup);
    CHECK(doc.at("{tcfg:run-var KEY}").as_string() == "unchanged");
    CHECK(doc.at("array").at(0).as_string() == "prefix {tcfg:run-var OTHER}");
    CHECK(doc.at("array").at(1).as_string().empty());
    CHECK(doc.at("nested").at("value").as_string() == "{tcfg:run-var OTHER}");
    CHECK(doc.at("integer").is_integer());
    for (const std::string value :
         {"{tcfg:run-var}", "{tcfg:run-var X }", "{tcfg:run-var X", "{tcfg:run-var }", "{tcfg:run-var MISSING}"})
    {
        toml::value candidate(toml::table{{"a/b~c", toml::array{toml::value(value)}}});
        try
        {
            nom::tcfg::substitute_runtime_variables(candidate, lookup);
            FAIL("expected substitution failure");
        }
        catch (const nom::tcfg::config_error& e)
        {
            CHECK(e.stage == nom::tcfg::config_stage::substitution);
            CHECK(e.pointer == "/a~1b~0c/0");
        }
    }
}

namespace override_fixture
{
    struct config
    {
        nom::cfg_int count;
        nom::cfg_string text;
        nom::cfg_vector<nom::cfg_int> items;
        nom::cfg_map<nom::cfg_int> named;
    };
    NOM_TCONFIG(config, count, text, items, named)
} // namespace override_fixture
TEST_CASE("overrides are string first then typed TOML and only replace existing targets")
{
    auto doc = nom::tcfg::parse_config("count = 1\ntext = 'one'\nitems = [1, 2]\nnamed = { 'a/b~c' = 3 }");
    auto probe = [](const toml::value& value) { (void)toml::get<override_fixture::config>(value); };
    const std::vector<nom::tcfg::config_override> values{
        {"/text", "20"}, {"/count", "0x20"}, {"/items/1", "4"}, {"/named/a~1b~0c", "5"}};
    nom::tcfg::apply_config_overrides(doc, values, probe);
    CHECK(doc.at("text").as_string() == "20");
    CHECK(doc.at("count").as_integer() == 32);
    CHECK(doc.at("items").at(1).as_integer() == 4);
    CHECK(doc.at("named").at("a/b~c").as_integer() == 5);
    for (const auto& [pointer, value] : std::vector<std::pair<std::string, std::string>>{{"/count", "1.0"},
                                                                                         {"/count", "1\nextra = 2"},
                                                                                         {"/missing", "1"},
                                                                                         {"/items/-", "1"},
                                                                                         {"/items/01", "1"},
                                                                                         {"/items/+1", "1"},
                                                                                         {"/items/2", "1"},
                                                                                         {"/items/", "1"},
                                                                                         {"/named/a~2b", "1"},
                                                                                         {"count", "1"},
                                                                                         {"/count/subkey", "1"},
                                                                                         {"/count", "null"}})
    {
        CAPTURE(pointer, value);
        const auto original = doc;
        const std::array changes{nom::tcfg::config_override{pointer, value}};
        REQUIRE_THROWS_AS(nom::tcfg::apply_config_overrides(doc, changes, probe), nom::tcfg::config_error);
        CHECK(doc == original);
    }
    const std::array root{nom::tcfg::config_override{"", "{ count = 9, text = 'root', items = [], named = {} }"}};
    nom::tcfg::apply_config_overrides(doc, root, probe);
    CHECK(doc.at("count").as_integer() == 9);
}

TEST_CASE("runtime environment and string overrides reject invalid UTF-8")
{
    auto document = nom::tcfg::parse_config("value = '{tcfg:run-var INVALID}'");
    try
    {
        nom::tcfg::substitute_runtime_variables(document,
                                                [](std::string_view) -> std::optional<std::string> { return "\xff"; });
        FAIL("invalid environment text accepted");
    }
    catch (const nom::tcfg::config_error& e)
    {
        CHECK(e.stage == nom::tcfg::config_stage::substitution);
        CHECK(e.pointer == "/value");
    }
    document["value"] = "valid";
    const std::array changes{nom::tcfg::config_override{"/value", "\xff"}};
    REQUIRE_THROWS_AS(nom::tcfg::apply_config_overrides(document, changes, [](const toml::value&) {}),
                      nom::tcfg::config_error);
    CHECK(document.at("value").as_string() == "valid");
}
