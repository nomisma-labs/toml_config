// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

module;

#include "toml11.h"

module nom.toml_config;

import std;

namespace nom::tcfg
{
    namespace
    {
        std::string append_pointer(const std::string& pointer, std::string_view token)
        {
            std::string result = pointer + '/';
            for (const char character : token)
            {
                if (character == '~')
                {
                    result += "~0";
                }
                else if (character == '/')
                {
                    result += "~1";
                }
                else
                {
                    result += character;
                }
            }
            return result;
        }

        bool is_placeholder_space(char character)
        {
            return character == ' ' || character == '\t' || character == '\n' || character == '\r' ||
                   character == '\f' || character == '\v';
        }

        std::string substitute_string(const std::string& text,
                                      const environment_lookup& environment,
                                      const config_location& location,
                                      const std::string& pointer)
        {
            constexpr std::string_view prefix = "{tcfg:run-var";
            std::string result;
            std::size_t consumed = 0;
            while (true)
            {
                const auto start = text.find(prefix, consumed);
                if (start == std::string::npos)
                {
                    result.append(text, consumed, std::string::npos);
                    return result;
                }
                result.append(text, consumed, start - consumed);
                auto name_start = start + prefix.size();
                if (name_start == text.size() || !is_placeholder_space(text[name_start]))
                {
                    throw config_error(
                        config_stage::substitution, "malformed runtime placeholder", location.path, pointer);
                }
                while (name_start < text.size() && is_placeholder_space(text[name_start]))
                {
                    ++name_start;
                }
                auto end = name_start;
                while (end < text.size() && text[end] != '}' && text[end] != '{' && !is_placeholder_space(text[end]))
                {
                    ++end;
                }
                if (end == name_start || end == text.size() || text[end] != '}')
                {
                    throw config_error(
                        config_stage::substitution, "malformed runtime placeholder", location.path, pointer);
                }
                const auto name = std::string_view(text).substr(name_start, end - name_start);
                const auto value = environment(name);
                if (!value)
                {
                    throw config_error(config_stage::substitution,
                                       "unset runtime environment variable '" + std::string(name) + "'",
                                       location.path,
                                       pointer);
                }
                try
                {
                    detail::validate_utf8(*value);
                }
                catch (const std::bad_alloc&)
                {
                    throw;
                }
                catch (const std::exception& error)
                {
                    throw config_error(config_stage::substitution, error.what(), location.path, pointer);
                }
                result += *value;
                consumed = end + 1;
            }
        }

        void substitute_values(toml::value& document,
                               const environment_lookup& environment,
                               const config_location& location,
                               const std::string& pointer)
        {
            if (document.is_string())
            {
                document = substitute_string(document.as_string(), environment, location, pointer);
            }
            else if (document.is_table())
            {
                for (auto& [key, value] : document.as_table())
                {
                    substitute_values(value, environment, location, append_pointer(pointer, key));
                }
            }
            else if (document.is_array())
            {
                for (std::size_t index = 0; index < document.size(); ++index)
                {
                    substitute_values(
                        document.at(index), environment, location, append_pointer(pointer, std::to_string(index)));
                }
            }
        }

        toml::value& resolve_pointer(toml::value& document, std::string_view pointer)
        {
            auto* current = &document;
            if (pointer.empty())
                return *current;
            if (pointer.front() != '/')
                throw std::runtime_error("config pointer must begin with '/'");
            std::size_t begin = 1;
            while (true)
            {
                const auto end = pointer.find('/', begin);
                const auto raw = pointer.substr(begin, end == std::string_view::npos ? end : end - begin);
                std::string token;
                for (std::size_t i = 0; i < raw.size(); ++i)
                {
                    if (raw[i] != '~')
                        token += raw[i];
                    else
                    {
                        if (++i == raw.size() || (raw[i] != '0' && raw[i] != '1'))
                            throw std::runtime_error("invalid pointer escape");
                        token += raw[i] == '0' ? '~' : '/';
                    }
                }
                if (current->is_table())
                    current = &current->at(token);
                else if (current->is_array())
                {
                    std::size_t index{};
                    auto [last, error] = std::from_chars(token.data(), token.data() + token.size(), index);
                    if (token.empty() || (token.size() > 1 && token.front() == '0') || error != std::errc{} ||
                        last != token.data() + token.size())
                        throw std::runtime_error("invalid array index in config pointer");
                    current = &current->at(index);
                }
                else
                    throw std::runtime_error("config pointer traverses a scalar");
                if (end == std::string_view::npos)
                    return *current;
                begin = end + 1;
            }
        }

        std::optional<std::string> try_override(toml::value& document,
                                                const std::string& pointer,
                                                const toml::value& replacement,
                                                const mapping_probe& probe)
        {
            auto candidate = document;
            resolve_pointer(candidate, pointer) = replacement;
            try
            {
                probe(candidate);
            }
            catch (const std::bad_alloc&)
            {
                throw;
            }
            catch (const std::exception& error)
            {
                return error.what();
            }
            document = std::move(candidate);
            return std::nullopt;
        }
    } // namespace

    toml::value read_config(const config_location& location)
    {
        if (!location.path)
        {
            if (location.source != config_source::hard_wired)
            {
                throw config_error(config_stage::reading, "selected config has no file path");
            }
            return toml::value(toml::table{});
        }
        if (location.path->empty() || location.path->native().find('\0') != std::string::npos)
        {
            throw config_error(
                config_stage::reading, "config path must be nonempty and contain no null characters", location.path);
        }

        std::error_code error;
        if (!std::filesystem::is_regular_file(*location.path, error))
        {
            throw config_error(config_stage::reading,
                               error ? "cannot access config file: " + error.message() : "config is not a regular file",
                               location.path);
        }
        std::ifstream input(*location.path, std::ios::binary);
        if (!input)
        {
            throw config_error(config_stage::reading, "cannot open config file", location.path);
        }

        std::string contents;
        std::array<char, 8192> buffer{};
        while (input)
        {
            input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
            contents.append(buffer.data(), static_cast<std::size_t>(input.gcount()));
        }
        if (input.bad() || !input.eof())
        {
            throw config_error(config_stage::reading, "cannot read config file", location.path);
        }

        toml::value document;
        try
        {
            document = parse_config(contents, location.path->string());
        }
        catch (const std::bad_alloc&)
        {
            throw;
        }
        catch (const mapping_error& error)
        {
            throw config_error(config_stage::parsing, error.what(), location.path, error.pointer);
        }
        catch (const std::exception& parse_error)
        {
            throw config_error(config_stage::parsing, parse_error.what(), location.path);
        }
        if (!document.is_table())
        {
            throw config_error(config_stage::parsing, "config root must be a TOML table", location.path);
        }
        return document;
    }

    void substitute_runtime_variables(toml::value& document,
                                      const environment_lookup& environment,
                                      const config_location& location)
    {
        substitute_values(document, environment, location, {});
    }

    void apply_config_overrides(toml::value& document,
                                std::span<const config_override> overrides,
                                const mapping_probe& probe,
                                const config_location& location)
    {
        for (const auto& override : overrides)
        {
            std::string pointer = override.pointer;
            try
            {
                detail::validate_utf8(override.value);
                static_cast<void>(resolve_pointer(document, pointer));
            }
            catch (const std::exception& error)
            {
                throw config_error(config_stage::overrides, error.what(), location.path, override.pointer);
            }

            const auto string_error = try_override(document, pointer, override.value, probe);
            if (!string_error)
            {
                continue;
            }

            toml::value replacement;
            try
            {
                auto parsed = parse_config("value = " + override.value);
                if (parsed.size() != 1 || !parsed.contains("value"))
                    throw std::runtime_error("override must contain exactly one TOML value");
                replacement = parsed.at("value");
            }
            catch (const std::exception& error)
            {
                throw config_error(config_stage::overrides,
                                   "override is neither a mapped string nor a TOML value; string mapping: " +
                                       *string_error + "; TOML parsing: " + error.what(),
                                   location.path,
                                   override.pointer);
            }
            if (const auto value_error = try_override(document, pointer, replacement, probe))
            {
                throw config_error(config_stage::overrides,
                                   "override does not map to the config; string mapping: " + *string_error +
                                       "; TOML mapping: " + *value_error,
                                   location.path,
                                   override.pointer);
            }
        }
    }
} // namespace nom::tcfg
