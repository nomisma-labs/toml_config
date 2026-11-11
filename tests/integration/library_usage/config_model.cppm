// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

export module consumer.config_model;

import std;

import nom.config_types;

export namespace consumer
{
    using namespace nom::cfg_types;

    struct connection_config
    {
        cfg_string address;
        cfg_defaulted<cfg_int> timeout_s{5};
        cfg_optional<cfg_string> interface_name;
    };

    struct app_config
    {
        cfg_defaulted<connection_config> connection{{"", {42}, "loopback"}};
        cfg_defaulted<cfg_bool> enabled{true};
        cfg_optional<cfg_string> annotation;

        std::expected<void, std::string> validate() const
        {
            if (connection->address.empty() || *connection->timeout_s <= 0)
            {
                return std::unexpected("connection requires an address and a positive timeout");
            }
            return {};
        }
    };
} // namespace consumer
