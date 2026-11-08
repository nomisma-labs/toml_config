// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

#include <toml_config/config.h>

import std;

import nom.toml_config;

namespace rejected_fixture
{
    struct unregistered_type
    {
        int value{};
    };

    inline void from_toml(const toml::value& document, unregistered_type& destination)
    {
        destination.value = toml::get<int>(document);
    }

    inline void to_toml(toml::value& document, const unregistered_type& source)
    {
        document = source.value;
    }

    struct config
    {
#if defined(NOM_TEST_INTEGER_MEMBER)
        int value{};
#elif defined(NOM_TEST_INTEGER_CONTAINER)
        std::vector<int> value;
#elif defined(NOM_TEST_UNREGISTERED_TYPE)
        unregistered_type value;
#else
#error Select a disabled config type test
#endif
    };

    NOM_TCONFIG(config, value)
} // namespace rejected_fixture

int main()
{
    const toml::value document(toml::table{{"value", toml::value(1)}});
    const auto config = toml::get<rejected_fixture::config>(document);
    const toml::value serialized = config;
    return serialized.is_empty();
}
