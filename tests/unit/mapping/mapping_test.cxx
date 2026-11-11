// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

#include <catch2/catch_test_macros.hpp>
#include <toml_config/config.h>
import std;
import nom.toml_config;

namespace fixture
{
    using namespace nom::cfg_types;
    enum class level
    {
        debug,
        info,
        warn,
        invalid
    };
    NOM_TCONFIG_ENUM(level,
                     {{level::debug, "debug"}, {level::info, "info"}, {level::warn, "warn"}, {level::info, "INFO"}})
    struct connection
    {
        cfg_string address;
        cfg_defaulted<cfg_int> timeout{5};
        cfg_optional<cfg_string> interface;
    };
    NOM_TCONFIG(connection, address, timeout, interface)
    struct settings
    {
        connection required{{}, {42}, "loopback"};
        cfg_defaulted<connection> defaults{{"localhost", {75}, {}}};
        cfg_optional<connection> optional{connection{"optional", {90}, "eth0"}};
        cfg_defaulted<level> severity{level::info};
        cfg_defaulted<cfg_vector<level>> levels;
        cfg_defaulted<cfg_map<level>> named;
        cfg_defaulted<cfg_unordered_map<cfg_int>> numbers;
        cfg_defaulted<cfg_vector<cfg_bool>> flags;
    };
    NOM_TCONFIG(settings, required, defaults, optional, severity, levels, named, numbers, flags)
    struct empty
    {
    };
    NOM_TCONFIG(empty)
    struct native
    {
        cfg_int count;
    };
    struct custom
    {
        std::string value;
    };
    void from_toml(const toml::value& v, custom& c)
    {
        c.value = v.as_string();
    }
    void to_toml(toml::value& v, const custom& c)
    {
        v = c.value;
    }
    struct native_custom
    {
        std::string value;
    };
} // namespace fixture
TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(fixture::native, count)
template <> inline constexpr bool nom::enable_config_type<fixture::custom> = true;
template <> inline constexpr bool nom::enable_config_type<fixture::native_custom> = true;
namespace toml
{
    template <> struct from<fixture::native_custom>
    {
        static fixture::native_custom from_toml(const value& v)
        {
            return {v.as_string()};
        }
    };
    template <> struct into<fixture::native_custom>
    {
        template <typename TC> static basic_value<TC> into_toml(const fixture::native_custom& v)
        {
            return basic_value<TC>(v.value);
        }
    };
} // namespace toml
namespace fixture
{
    struct move_only
    {
        std::string text;
        move_only() = default;
        move_only(move_only&&) = default;
        move_only& operator=(move_only&&) = default;
        move_only(const move_only&) = delete;
        move_only& operator=(const move_only&) = delete;
    };
    NOM_TCONFIG(move_only, text)
    struct move_only_list
    {
        cfg_vector<move_only> items;
    };
    NOM_TCONFIG(move_only_list, items)
    struct domains
    {
        custom a;
        native_custom b;
    };
    NOM_TCONFIG(domains, a, b)
} // namespace fixture
static_assert(!nom::is_config_member<int>);
static_assert(!nom::is_config_member<std::vector<std::optional<nom::cfg_int>>>);
static_assert(!nom::is_config_member<nom::cfg_defaulted<std::optional<nom::cfg_int>>>);

TEST_CASE("nested member policies preserve initialized defaults")
{
    const auto doc = nom::tcfg::parse_config("required = { address = 'remote' }\noptional = { address = 'changed' }");
    auto value = toml::get<fixture::settings>(doc);
    REQUIRE(*value.required.timeout == 42);
    REQUIRE(value.required.interface == "loopback");
    REQUIRE(*value.defaults->timeout == 75);
    REQUIRE(*value.optional->timeout == 90);
    REQUIRE(value.optional->interface == "eth0");
    value.required.timeout = {123};
    nom::tcfg::get_to(doc, value);
    REQUIRE(*value.required.timeout == 123);
    REQUIRE_THROWS(toml::get<fixture::settings>(nom::tcfg::parse_config("")));
    REQUIRE_THROWS(toml::get<fixture::settings>(nom::tcfg::parse_config("required = {}")));
    REQUIRE_THROWS(toml::get<fixture::settings>(toml::value(toml::array{})));
    REQUIRE_NOTHROW(toml::get<fixture::empty>(nom::tcfg::parse_config("ignored = 1")));
    REQUIRE_THROWS(toml::get<fixture::empty>(toml::value(42)));
}

TEST_CASE("serialization omits empty optionals and round trips active values")
{
    auto value = toml::get<fixture::settings>(nom::tcfg::parse_config("required = { address = 'remote' }"));
    value.optional.reset();
    value.required.interface.reset();
    const toml::value serialized(value);
    REQUIRE_FALSE(serialized.contains("optional"));
    REQUIRE_FALSE(serialized.at("required").contains("interface"));
    REQUIRE(serialized.at("required").at("timeout").as_integer() == 42);
    REQUIRE(serialized.at("severity").as_string() == "info");
    const auto restored = toml::get<fixture::settings>(serialized);
    REQUIRE(restored.optional->address == "optional");
    REQUIRE(restored.required.interface == "loopback");
}

TEST_CASE("checked numeric conversions reject lossy or unsupported values")
{
    for (const toml::value& v : {toml::value(1.0), toml::value(true), toml::value("1"), toml::value(toml::array{})})
    {
        REQUIRE_THROWS(toml::get<nom::cfg_int>(v));
        REQUIRE_THROWS(toml::get<nom::cfg_uint>(v));
    }
    REQUIRE(toml::get<nom::cfg_int>(toml::value(std::numeric_limits<std::int64_t>::min())).value ==
            std::numeric_limits<std::int64_t>::min());
    REQUIRE(toml::get<nom::cfg_uint>(toml::value(std::numeric_limits<std::int64_t>::max())).value ==
            std::numeric_limits<std::int64_t>::max());
    REQUIRE_THROWS(toml::get<nom::cfg_uint>(toml::value(-1)));
    REQUIRE_THROWS(toml::value(nom::cfg_uint{std::numeric_limits<std::uint64_t>::max()}));
    REQUIRE(toml::get<nom::cfg_double>(toml::value(2)).value == 2.0);
    for (double v : {std::numeric_limits<double>::infinity(),
                     -std::numeric_limits<double>::infinity(),
                     std::numeric_limits<double>::quiet_NaN()})
    {
        REQUIRE_THROWS(toml::get<nom::cfg_double>(toml::value(v)));
        REQUIRE_THROWS(toml::value(nom::cfg_double{v}));
    }
    REQUIRE_THROWS(toml::get<nom::cfg_double>(toml::value(true)));
}

TEST_CASE("native macros and both custom converter routes compose")
{
    REQUIRE(toml::get<fixture::native>(nom::tcfg::parse_config("count = 2")).count == 2);
    REQUIRE_THROWS(toml::get<fixture::native>(nom::tcfg::parse_config("count = 2.0")));
    const auto doc = nom::tcfg::parse_config("a = 'one'\nb = 'two'");
    auto result = toml::get<fixture::domains>(doc);
    REQUIRE(result.a.value == "one");
    REQUIRE(result.b.value == "two");
    REQUIRE(toml::value(result) == doc);
}

TEST_CASE("enum aliases canonicalize and failures leave the enum unchanged")
{
    using fixture::level;
    REQUIRE(toml::get<level>(toml::value("INFO")) == level::info);
    REQUIRE(toml::value(level::info).as_string() == "info");
    for (const auto& v : {toml::value("Info"),
                          toml::value("unknown"),
                          toml::value(1),
                          toml::value(1.0),
                          toml::value(true),
                          toml::value(toml::array{}),
                          toml::value(toml::table{}),
                          toml::value(toml::local_date(2026, toml::month_t::Nov, 8))})
    {
        auto result = level::warn;
        REQUIRE_THROWS(nom::tcfg::get_to(v, result));
        REQUIRE(result == level::warn);
    }
    toml::value output("unchanged");
    REQUIRE_THROWS(fixture::to_toml(output, level::invalid));
    REQUIRE(output.as_string() == "unchanged");
    REQUIRE_THROWS(toml::value(static_cast<level>(100)));
}

TEST_CASE("containers retain nested error pointers and replace their contents")
{
    for (const auto& [text, pointer] :
         std::vector<std::pair<std::string, std::string>>{{"severity = 'typo'", "/severity"},
                                                          {"levels = ['info', 'typo']", "/levels/1"},
                                                          {"named = { 'a/b~c' = 'typo' }", "/named/a~1b~0c"},
                                                          {"optional = {address = 10}", "/optional/address"}})
    {
        const auto doc = nom::tcfg::parse_config("required = { address = 'remote' }\n" + text);
        try
        {
            (void)toml::get<fixture::settings>(doc);
            FAIL("expected conversion failure");
        }
        catch (const nom::tcfg::mapping_error& e)
        {
            REQUIRE(e.pointer == pointer);
        }
    }
    const auto doc = nom::tcfg::parse_config("required = { address = 'remote' }\nlevels = ['warn']\nnamed = { a = "
                                             "'debug' }\nnumbers = { a = 4 }\nflags = [true, false]");
    auto result = toml::get<fixture::settings>(doc);
    REQUIRE(result.levels->at(0) == fixture::level::warn);
    REQUIRE(result.named->at("a") == fixture::level::debug);
    REQUIRE(result.numbers->at("a") == 4);
    REQUIRE(result.flags->at(0));
    REQUIRE(toml::value(result).at("flags").at(1).as_boolean() == false);
    auto empty = doc;
    empty["levels"] = toml::array{};
    nom::tcfg::get_to(empty, result);
    REQUIRE(result.levels->empty());
}

TEST_CASE("container serialization does not require copyable config values")
{
    const auto document = nom::tcfg::parse_config("items = [{text = 'hello'}]");
    const auto value = toml::get<fixture::move_only_list>(document);
    REQUIRE(value.items.front().text == "hello");
    REQUIRE(toml::value(value) == document);
}
