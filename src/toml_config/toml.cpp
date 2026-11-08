// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

module;

#include <exception>
#include <filesystem>
#include <string>
#include <toml.hpp>

module nom.toml_config;

namespace nom::config
{
    document load(const std::filesystem::path& input)
    {
        try
        {
            if (input.string().find('\0') != std::string::npos)
                throw error("configuration paths cannot contain a NUL character");
            if (input.extension() != ".toml")
                throw error("C++ configuration requires a .toml file; generate it with cfggen.py");
            return {toml::parse(input.string(), toml::spec::v(1, 0, 0))};
        }
        catch (const error&)
        {
            throw;
        }
        catch (const std::exception& failure)
        {
            throw error(failure.what());
        }
    }

    std::string format(const document& config)
    {
        return toml::format(config.value, toml::spec::v(1, 0, 0));
    }
} // namespace nom::config
