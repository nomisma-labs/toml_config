// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

module;
#include "toml11.h"

export module nom.toml_config:mapping;
import std;
import nom.config_types;

export namespace nom::tcfg
{
    class mapping_error : public std::runtime_error
    {
    public:
        explicit mapping_error(std::string message, std::string pointer = {})
            : std::runtime_error(std::move(message)), pointer(std::move(pointer))
        {
        }
        std::string pointer;
    };

    template <typename Value> void get_to(const toml::value& document, Value& destination);
    template <typename Value> toml::value to_value(const Value& source);

    namespace detail
    {
        inline std::string pointer_token(std::string_view token)
        {
            std::string result = "/";
            for (const char c : token)
            {
                if (c == '~')
                    result += "~0";
                else if (c == '/')
                    result += "~1";
                else
                    result += c;
            }
            return result;
        }
        template <typename Operation> decltype(auto) at_member(std::string_view token, Operation&& operation)
        {
            try
            {
                return operation();
            }
            catch (const std::bad_alloc&)
            {
                throw;
            }
            catch (const mapping_error& error)
            {
                throw mapping_error(error.what(), pointer_token(token) + error.pointer);
            }
            catch (const std::exception& error)
            {
                throw mapping_error(error.what(), pointer_token(token));
            }
        }
        template <typename T> inline constexpr bool is_vector = false;
        template <typename T, typename Allocator> inline constexpr bool is_vector<std::vector<T, Allocator>> = true;
        template <typename T> inline constexpr bool is_map = false;
        template <typename T, typename Compare, typename Allocator>
        inline constexpr bool is_map<std::map<std::string, T, Compare, Allocator>> = true;
        template <typename T, typename Hash, typename Equal, typename Allocator>
        inline constexpr bool is_map<std::unordered_map<std::string, T, Hash, Equal, Allocator>> = true;
    } // namespace detail
} // namespace nom::tcfg

export namespace nom::detail
{
    template <typename Value> void from_toml(const toml::value& document, config_number<Value>& destination)
    {
        if constexpr (std::same_as<Value, double>)
        {
            const double value =
                document.is_integer() ? static_cast<double>(document.as_integer()) : document.as_floating();
            if (!std::isfinite(value))
                throw tcfg::mapping_error(toml::format_error("expected a finite number", document, "nonfinite number"));
            destination.value = value;
        }
        else
        {
            const auto value = document.as_integer();
            if constexpr (std::same_as<Value, std::uint64_t>)
                if (value < 0)
                    throw tcfg::mapping_error(
                        toml::format_error("expected a nonnegative integer", document, "negative integer"));
            destination.value = static_cast<Value>(value);
        }
    }
    template <typename Value> void to_toml(toml::value& document, const config_number<Value>& source)
    {
        if constexpr (std::same_as<Value, double>)
        {
            if (!std::isfinite(source.value))
                throw tcfg::mapping_error("expected a finite number");
            document = source.value;
        }
        else
        {
            if constexpr (std::same_as<Value, std::uint64_t>)
                if (source.value > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
                    throw tcfg::mapping_error("integer exceeds the signed 64-bit TOML range");
            document = static_cast<std::int64_t>(source.value);
        }
    }
} // namespace nom::detail
export namespace nom
{
    template <typename Value> void from_toml(const toml::value& document, cfg_defaulted<Value>& destination)
    {
        tcfg::get_to(document, destination.value);
    }
    template <typename Value> void to_toml(toml::value& document, const cfg_defaulted<Value>& source)
    {
        document = tcfg::to_value(source.value);
    }
} // namespace nom

// Only explicitly enabled ADL mappings participate in the native conversion bridge.
export namespace nom::tcfg::detail
{
    template <typename T>
    concept adl_from = nom::is_config_value<T> && requires(const toml::value& v, T& t) { from_toml(v, t); };
    template <typename T>
    concept adl_into = nom::is_config_value<T> && requires(toml::value& v, const T& t) { to_toml(v, t); };
    template <typename T> void read_adl(const toml::value& v, T& t)
    {
        from_toml(v, t);
    }
    template <typename T> toml::value write_adl(const T& t)
    {
        toml::value v;
        to_toml(v, t);
        return v;
    }
} // namespace nom::tcfg::detail
export namespace toml
{
    template <typename T>
        requires nom::tcfg::detail::adl_from<T>
    struct from<T>
    {
        static T from_toml(const value& document)
        {
            T result{};
            nom::tcfg::detail::read_adl(document, result);
            return result;
        }
    };
    template <typename T>
        requires nom::tcfg::detail::adl_into<T>
    struct into<T>
    {
        template <typename TC = type_config> static basic_value<TC> into_toml(const T& source)
        {
            return basic_value<TC>(nom::tcfg::detail::write_adl(source));
        }
    };
} // namespace toml

export namespace nom::tcfg
{
    template <typename Value> void get_to(const toml::value& document, Value& destination)
    {
        if constexpr (detail::adl_from<Value>)
            detail::read_adl(document, destination);
        else if constexpr (detail::is_vector<Value>)
        {
            const auto& values = document.as_array();
            Value result;
            result.reserve(values.size());
            for (std::size_t i = 0; i < values.size(); ++i)
                detail::at_member(std::to_string(i),
                                  [&]
                                  {
                                      typename Value::value_type value{};
                                      get_to(values[i], value);
                                      result.push_back(std::move(value));
                                  });
            destination = std::move(result);
        }
        else if constexpr (detail::is_map<Value>)
        {
            Value result;
            for (const auto& [key, item] : document.as_table())
                detail::at_member(key, [&] { get_to(item, result[key]); });
            destination = std::move(result);
        }
        else
            destination = toml::get<Value>(document);
    }

    template <typename Value> toml::value to_value(const Value& source)
    {
        if constexpr (detail::adl_into<Value>)
            return detail::write_adl(source);
        else if constexpr (detail::is_vector<Value>)
        {
            toml::array result;
            for (std::size_t i = 0; i < source.size(); ++i)
                result.push_back(detail::at_member(std::to_string(i),
                                                   [&]
                                                   {
                                                       const typename Value::value_type& value = source[i];
                                                       return to_value(value);
                                                   }));
            return toml::value(std::move(result));
        }
        else if constexpr (detail::is_map<Value>)
        {
            toml::table result;
            for (const auto& [key, value] : source)
                result.emplace(key, detail::at_member(key, [&] { return to_value(value); }));
            return toml::value(std::move(result));
        }
        else
            return toml::value(source);
    }
    namespace detail
    {
        template <typename Value> void read_member(const toml::value& document, const char* name, Value& destination)
        {
            at_member(name, [&] { get_to(document.at(name), destination); });
        }
        template <typename Value>
        void read_member(const toml::value& document, const char* name, cfg_defaulted<Value>& destination)
        {
            if (document.contains(name))
                read_member(document, name, destination.value);
        }
        template <typename Value>
        void read_member(const toml::value& document, const char* name, std::optional<Value>& destination)
        {
            if (document.contains(name))
            {
                if (!destination)
                    destination.emplace();
                read_member(document, name, *destination);
            }
        }
        template <typename Value> void write_member(toml::value& document, const char* name, const Value& source)
        {
            document[name] = at_member(name, [&] { return to_value(source); });
        }
        template <typename Value>
        void write_member(toml::value& document, const char* name, const std::optional<Value>& source)
        {
            if (source)
                write_member(document, name, *source);
        }
    } // namespace detail
} // namespace nom::tcfg
