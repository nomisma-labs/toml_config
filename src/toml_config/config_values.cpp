// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

module;
#include "toml11.h"
module nom.toml_config;
import std;

namespace nom::tcfg
{
    namespace detail
    {
        void validate_utf8(std::string_view text)
        {
            for (std::size_t i = 0; i < text.size();)
            {
                const auto first = static_cast<unsigned char>(text[i++]);
                if (first < 0x80)
                    continue;
                unsigned length;
                unsigned code;
                unsigned minimum;
                if (first >= 0xc2 && first <= 0xdf)
                {
                    length = 1;
                    code = first & 0x1f;
                    minimum = 0x80;
                }
                else if (first >= 0xe0 && first <= 0xef)
                {
                    length = 2;
                    code = first & 0x0f;
                    minimum = 0x800;
                }
                else if (first >= 0xf0 && first <= 0xf4)
                {
                    length = 3;
                    code = first & 7;
                    minimum = 0x10000;
                }
                else
                    throw std::runtime_error("invalid UTF-8");
                for (unsigned n = 0; n < length; ++n)
                {
                    if (i == text.size())
                        throw std::runtime_error("truncated UTF-8");
                    const auto c = static_cast<unsigned char>(text[i++]);
                    if ((c & 0xc0) != 0x80)
                        throw std::runtime_error("invalid UTF-8 continuation");
                    code = (code << 6) | (c & 0x3f);
                }
                if (code < minimum || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff))
                    throw std::runtime_error("invalid Unicode scalar");
            }
        }
    } // namespace detail

    namespace
    {
        void validate_date(const toml::local_date& date)
        {
            const std::chrono::year_month_day value{
                std::chrono::year(date.year), std::chrono::month(unsigned(date.month) + 1), std::chrono::day(date.day)};
            if (date.year < 1 || date.year > 9999 || !value.ok())
                throw std::runtime_error("invalid calendar date; supported years are 1 through 9999");
        }
        void normalize_time(toml::local_time& time)
        {
            if (time.hour > 23 || time.minute > 59 || time.second > 59 || time.millisecond > 999 ||
                time.microsecond > 999 || time.nanosecond > 999)
                throw std::runtime_error("invalid local time; leap seconds are unsupported");
            time.nanosecond = 0;
        }
        void normalize_values(toml::value& document)
        {
            if (document.is_string())
                detail::validate_utf8(document.as_string());
            else if (document.is_table())
                for (auto& [key, value] : document.as_table())
                {
                    detail::validate_utf8(key);
                    detail::at_member(key, [&] { normalize_values(value); });
                }
            else if (document.is_array())
                for (std::size_t i = 0; i < document.size(); ++i)
                    detail::at_member(std::to_string(i), [&] { normalize_values(document.at(i)); });
            else if (document.is_local_date())
                validate_date(document.as_local_date());
            else if (document.is_local_time())
                normalize_time(document.as_local_time());
            else if (document.is_local_datetime())
            {
                auto& value = document.as_local_datetime();
                validate_date(value.date);
                normalize_time(value.time);
            }
            else if (document.is_offset_datetime())
            {
                auto& value = document.as_offset_datetime();
                validate_date(value.date);
                normalize_time(value.time);
                if (std::abs(value.offset.hour) > 23 || std::abs(value.offset.minute) > 59 ||
                    value.offset.hour * value.offset.minute < 0)
                    throw std::runtime_error("invalid timezone offset");
            }
            else if (document.is_empty())
                throw std::runtime_error("TOML has no null value");
        }
    } // namespace
    toml::value parse_config(std::string_view source, std::string_view label)
    {
        detail::validate_utf8(source);
        if (source.starts_with("\xef\xbb\xbf"))
            throw std::runtime_error("TOML source must not contain a BOM");
        for (std::size_t i = 0; i < source.size(); ++i)
            if (source[i] == '\r' && (i + 1 == source.size() || source[i + 1] != '\n'))
                throw std::runtime_error("bare carriage return in TOML source");
        std::istringstream input{std::string(source)};
        auto result = toml::parse(input, std::string(label), toml::spec::v(1, 0, 0));
        normalize_values(result);
        return result;
    }
    std::string format_config(toml::value document)
    {
        normalize_values(document);
        const auto result = toml::format(document, toml::spec::v(1, 0, 0));
        // Validate custom converters and native formatting against the same input profile.
        (void)parse_config(result);
        return result;
    }
} // namespace nom::tcfg
