# TOML/C++ mapping

> **Documentation review draft — implementation pending.** This page defines the
> target contract. Commands and APIs below are implementation acceptance criteria,
> not claims that this checkout already supports them. See [status](../../TODO.md).

Mapping connects TOML values to application-owned C++ config structures. The
[loader](app_config_binding.md#loading-and-overrides) handles config resolution,
reading, environment substitution, and runtime overrides. The mapping layer knows
the C++ types; the loader and generator do not need to know individual config members.

## Declaring a config

Import `nom.toml_config` for TOML mapping and the common config types in `nom`.
It re-exports `nom.config_types`; data-only code can import that module directly.
The `nom::cfg_types` namespace provides aliases for a convenient scoped using-directive.
Include `<toml_config/config.h>` for `NOM_TCONFIG` and the toml11 dependency.

The Nomisma macro `NOM_TCONFIG` declares which members participate in TOML/C++
mapping and checks that their types are enabled for config use. TOML keys have
the same names as the C++ members:

```cpp
#include <toml_config/config.h>

import std;
import nom.toml_config;

namespace demo
{
    using namespace nom::cfg_types;

    struct connection_config
    {
        cfg_string address;
        cfg_defaulted<cfg_int> timeout_s{5};
        cfg_optional<cfg_string> interface_name;

        std::expected<void, std::string> validate() const
        {
            if (*timeout_s <= 0)
                return std::unexpected("timeout_s must be positive");
            return {};
        }
    };

    NOM_TCONFIG(connection_config, address, timeout_s, interface_name)

    connection_config make_connection(const toml::value& document)
    {
        auto candidate = toml::get<connection_config>(document);
        if (const auto result = candidate.validate(); !result)
            throw std::runtime_error(result.error());
        return candidate;
    }
}
```

For `address = "localhost"`, this returns a config with a timeout of `5` and
an empty optional. `toml::value serialized(config);` converts it back to a TOML
table. Place `NOM_TCONFIG` in the same namespace as the config type.

The planned [config_workflow_example](../../apps/config_workflow_example/README.md)
combines `NOM_TCONFIG`, defaulted and optional members, and root validation with
the loader. Nested config structures declare their own mappings. Supported types
include booleans, strings, checked numeric types, nested configs, vectors, and
string-keyed maps. Plain numeric members such as `int` and `double` are rejected
at compile time; use `cfg_int`, `cfg_uint`, or `cfg_double` from `nom::cfg_types`.

Conversion uses toml11 with the Nomisma adapters described in the
[implementation notes](toml11_implementation.md#mapping-and-custom-converters).
Custom domain types can be explicitly enabled and supply `from_toml` / `to_toml`
converters or native toml11 converters. The
[type guide](https://github.com/nomisma-labs/base/blob/master/docs/base/config_types.md)
describes the format-independent types, aliases, and CMake target. Linking
`nom::toml_config` supplies that target transitively, including installed consumers.

Use `toml::get<Config>(document)` to create a config, or
`nom::tcfg::get_to(document, candidate)` to populate an existing candidate whose
initial values should be preserved. Conversion failures propagate the converter's
exceptions. Validation is a separate call.

## Required, defaulted, and optional fields

Each member has its own presence policy:

| Policy | Meaning |
|---|---|
| Required | The TOML key must be present. A C++ member initializer alone does not make the key optional. |
| Defaulted | An omitted key retains the value initialized in C++. |
| Optional | An omitted key retains the initialized optional, normally empty. A present key maps to its contained type. |

These policies can be combined in one structure. A supplied value must satisfy its
mapping rules. Nested defaults are preserved when a partial nested table supplies
only some defaulted members; required members still need their TOML keys.

TOML has no null value and the framework adds no sentinel for it. Empty optional
members are omitted from serialized tables; engaged optionals and defaults serialize
as their values. Omission does not clear an optional explicitly initialized by C++.
The [implementation notes](toml11_implementation.md#default-and-optional-wrappers)
describe presence, serialization, and the representational limit for cleared defaults.

## Enum mapping

Use `NOM_TCONFIG_ENUM` to register an enum as a config type and define its TOML
string representation. Include `<toml_config/config.h>`, import `std` and
`nom.toml_config`, and declare the mapping in the enum's namespace before its
first use in a structure mapping:

```cpp
namespace demo
{
    enum class log_level
    {
        debug,
        info,
        warn
    };

    NOM_TCONFIG_ENUM(log_level,
                     {{log_level::debug, "debug"},
                      {log_level::info, "info"},
                      {log_level::warn, "warn"}})

    struct log_config
    {
        nom::cfg_defaulted<log_level> level{log_level::info};
    };

    NOM_TCONFIG(log_config, level)
}
```

Here, `level = "debug"` selects `log_level::debug`; omitting `level` preserves
`info`. Declaring plain `log_level level` makes the field required even if it
has a C++ initializer. An optional enum uses the ordinary optional presence rules.

The mapping is a nonempty list of `{enumerator, string}` pairs. Matching is exact
and case-sensitive. Additional names for an enum value can be listed explicitly;
the first matching entry is used, so the first name for a value is its canonical
serialized form. Adding `{log_level::info, "INFO"}` after `"info"` accepts both
spellings and serializes either as `"info"`.

Unknown strings and non-string TOML values fail mapping. Serialization also fails
for an enum value without a mapping. There is no fallback to the first entry.
Deserialization errors preserve the config pointer in nested tables and containers,
and failed conversion leaves the destination enum unchanged.

## Validation boundaries

Mapping checks table structure and required keys, then uses each type's converter.
Numeric adapters validate the source before conversion: `cfg_int` rejects a
floating-point value rather than truncating it. `cfg_uint` rejects negative
integers and serialization above `INT64_MAX`, the TOML integer limit. `cfg_double`
requires finite numbers. Application validation checks domain-specific values,
ranges, and relationships between fields.

Config structures support `std::expected<void, std::string> validate() const`.
Return `{}` on success or `std::unexpected(message)` on failure. The root config's
validation includes checks of its nested configs and propagates any error.

After mapping the final runtime values, call the root config's `validate()` before
using the config to initialize application services. Make the resulting config
available only after mapping and validation succeed. Mapping errors come from the
TOML adapters or custom converters; validation errors carry the supplied message.
Mapping into an existing candidate may change some members before a failure, so
keep that candidate separate from the active config.

Component settings can remain independent of TOML and of this library. Application
adapters supply their mapping, so logger, transport, and strategy components can be
used with another configuration system. Details are in
[Implementation details using toml11](toml11_implementation.md).
