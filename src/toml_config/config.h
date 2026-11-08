// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#pragma once

#include <toml_config/toml11.h>
#include <type_traits>

// Evaluate the application's definition at its call site, outside compiled library code.
#define NOM_TCFG_STRINGIFY_IMPL(value) #value
#define NOM_TCFG_STRINGIFY(value) NOM_TCFG_STRINGIFY_IMPL(value)
#ifdef NOM_CONFIG_KEY
#define NOM_CONFIG_KEY_VALUE NOM_TCFG_STRINGIFY(NOM_CONFIG_KEY)
#else
#define NOM_CONFIG_KEY_VALUE ""
#endif

#define NOM_TCFG_READ_MEMBER(member)                                                                                   \
    static_assert(::nom::is_config_member<std::remove_cvref_t<decltype(nom_tcfg_destination.member)>>,                 \
                  "NOM_TCONFIG member type is not config-enabled");                                                    \
    ::nom::tcfg::detail::read_member(nom_tcfg_document, #member, nom_tcfg_destination.member);
#define NOM_TCFG_WRITE_MEMBER(member)                                                                                  \
    static_assert(::nom::is_config_member<std::remove_cvref_t<decltype(nom_tcfg_source.member)>>,                      \
                  "NOM_TCONFIG member type is not config-enabled");                                                    \
    ::nom::tcfg::detail::write_member(nom_tcfg_document, #member, nom_tcfg_source.member);

// Declare beside the type, in its namespace, after importing nom.toml_config.
#define NOM_TCONFIG(Type, ...)                                                                                         \
    inline std::true_type nom_config_type(Type*)                                                                       \
    {                                                                                                                  \
        return {};                                                                                                     \
    }                                                                                                                  \
    inline void from_toml(const ::toml::value& nom_tcfg_document, [[maybe_unused]] Type& nom_tcfg_destination)         \
    {                                                                                                                  \
        (void)nom_tcfg_document.as_table();                                                                            \
        __VA_OPT__(TOML11_FOR_EACH_VA_ARGS(NOM_TCFG_READ_MEMBER, __VA_ARGS__))                                         \
    }                                                                                                                  \
    inline void to_toml(::toml::value& nom_tcfg_document, [[maybe_unused]] const Type& nom_tcfg_source)                \
    {                                                                                                                  \
        nom_tcfg_document = ::toml::table{};                                                                           \
        __VA_OPT__(TOML11_FOR_EACH_VA_ARGS(NOM_TCFG_WRITE_MEMBER, __VA_ARGS__))                                        \
    }

// Declare in the enum's namespace with {{Type::value, "name"}, ...}.
// Matching is exact; the first name for a value is its serialized form.
#define NOM_TCONFIG_ENUM(Type, ...)                                                                                    \
    static_assert(std::is_enum_v<Type>, "NOM_TCONFIG_ENUM requires an enum type");                                     \
    inline std::true_type nom_config_type(Type*)                                                                       \
    {                                                                                                                  \
        return {};                                                                                                     \
    }                                                                                                                  \
    inline void from_toml(const ::toml::value& nom_tcfg_document, Type& nom_tcfg_destination)                          \
    {                                                                                                                  \
        static constexpr std::pair<Type, std::string_view> nom_tcfg_names[] = __VA_ARGS__;                             \
        const auto& nom_tcfg_name = nom_tcfg_document.as_string();                                                     \
        for (const auto& [nom_tcfg_value, nom_tcfg_text] : nom_tcfg_names)                                             \
        {                                                                                                              \
            if (nom_tcfg_name == nom_tcfg_text)                                                                        \
            {                                                                                                          \
                nom_tcfg_destination = nom_tcfg_value;                                                                 \
                return;                                                                                                \
            }                                                                                                          \
        }                                                                                                              \
        throw ::nom::tcfg::mapping_error(                                                                              \
            ::toml::format_error("unmapped " #Type " value " + nom_tcfg_document.as_string(),                          \
                                 nom_tcfg_document,                                                                    \
                                 "expected a registered enum name"));                                                  \
    }                                                                                                                  \
    inline void to_toml(::toml::value& nom_tcfg_document, Type nom_tcfg_source)                                        \
    {                                                                                                                  \
        static constexpr std::pair<Type, std::string_view> nom_tcfg_names[] = __VA_ARGS__;                             \
        for (const auto& [nom_tcfg_value, nom_tcfg_text] : nom_tcfg_names)                                             \
        {                                                                                                              \
            if (nom_tcfg_source == nom_tcfg_value)                                                                     \
            {                                                                                                          \
                nom_tcfg_document = std::string(nom_tcfg_text);                                                        \
                return;                                                                                                \
            }                                                                                                          \
        }                                                                                                              \
        throw ::nom::tcfg::mapping_error("unmapped " #Type " value " +                                                 \
                                         std::to_string(std::to_underlying(nom_tcfg_source)));                         \
    }
