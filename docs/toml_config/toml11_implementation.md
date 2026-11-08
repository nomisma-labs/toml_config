# Implementation details using toml11

This document describes the use of toml11 for the
[Nomisma mapping contract](toml_cpp_mapping.md). The dependency baseline is the
repository's pinned toml11 4.4.0. `<toml_config/toml11.h>` includes the native
library and is also included by `config.h`. Textual dependency and macro headers
come before module imports.

The [config types design note](https://github.com/nomisma-labs/base/blob/master/docs/base/config_types_design.md)
explains why the special types exist and how common C++ data is separated from
format mapping. The `base` dependency's `nom.config_types` module owns the types;
`nom.toml_config` supplies their TOML converters and re-exports the common module.
The common types do not depend on toml11 or the generator.

## Overview of toml11 facilities

Toml11 uses `toml::from<T>` and `toml::into<T>` specializations for user types.
Its non-intrusive macro generates these specializations for ordinary structures.
The following native example uses our checked integer converter:

```cpp
#include <toml_config/toml11.h>

import std;
import nom.toml_config;

namespace demo
{
    using namespace nom::cfg_types;

    struct connection_config
    {
        cfg_string address;
        cfg_int timeout_s;
    };
}

TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(demo::connection_config, address, timeout_s)
```

The native macro goes at global scope with the qualified type name. Given a
parsed TOML table named `document`, the corresponding operations are:

```cpp
auto config = toml::get<demo::connection_config>(document);
toml::value serialized(config);
```

Use `config.timeout_s` directly in numeric expressions or pass it to a function
accepting its underlying integer type. The converter for `cfg_int` rejects a
floating-point TOML value even when it happens to be integral.

| toml11 facility | Behavior relevant to config mapping |
|---|---|
| `TOML11_DEFINE_CONVERSION_NON_INTRUSIVE` | Generates native converters; ordinary listed members require keys. It does not supply Nomisma's per-member defaults or config-type checks. |
| `toml::get<T>(document)` | Creates a value through the native conversion mechanism. |
| `toml::from<T>::from_toml(document)` | Custom conversion returning a newly constructed `T`. |
| `toml::into<T>::into_toml(value)` | Custom conversion returning a TOML value. |
| `toml::format(document, toml::spec::v(1, 0, 0))` | Serializes a TOML value using the selected syntax version. |

Toml11 4.4.0 has no native equivalent of an in-place `get_to()` operation for
application structures and no `WITH_DEFAULT` structure macro. Use `NOM_TCONFIG`
for application configs: it preserves the initialized destination, checks enabled
member types, and supplies the presence policies below. The native facility
boundaries are documented by [toml11](https://toruniina.github.io/toml11/docs/reference/conversion/).

## Config-enabled types

Only enabled types may appear in a `NOM_TCONFIG` mapping. The check applies
recursively to wrappers and container elements.

| Type | Supported representation |
|---|---|
| `nom::cfg_bool` (`bool`) | TOML boolean only |
| `nom::cfg_string` (`std::string`) | TOML string only |
| `nom::cfg_int` | TOML integer in the `std::int64_t` range |
| `nom::cfg_uint` | Nonnegative TOML integer, from `0` through `INT64_MAX` |
| `nom::cfg_double` | TOML integer or float that converts to a finite `double` |
| Structure declared with `NOM_TCONFIG` | TOML table; the macro enables the structure automatically |
| Enum declared with `NOM_TCONFIG_ENUM` | Explicitly mapped TOML string; unmapped values fail |
| `nom::cfg_vector<T>` (`std::vector<T>`) | TOML array of enabled values |
| `nom::cfg_map<T>` or `nom::cfg_unordered_map<T>` | TOML table with enabled mapped values |

All common types have aliases in `nom::cfg_types`; both spellings name the same
types. Standard-library aliases remain usable under their original names. The
[type guide](https://github.com/nomisma-labs/base/blob/master/docs/base/config_types.md)
lists their definitions. Plain numeric members such as `int`, `unsigned`, and
`double` are not enabled; use the checked wrappers.

The numeric types remain aggregates with a public `value` member, `get()` accessors,
and implicit conversion by value to their underlying C++ type. `cfg_uint` still
stores `std::uint64_t`; the smaller supported TOML range is enforced in both
conversion directions. Serialization must reject values above `INT64_MAX` rather
than narrowing, wrapping, or encoding them as strings.

Dates and times remain native TOML values in the generator and parsed document.
They are not enabled common C++ config types. A domain-specific type can opt in
with explicit conversion; no implicit date-to-string or timezone conversion occurs.

## Mapping and custom converters

Include `<toml_config/config.h>` and import `nom.toml_config`, as shown in the
[usage example](toml_cpp_mapping.md#declaring-a-config). Link `nom::toml_config`.
Its public dependency on `nom::config_types` supplies the common module. The
installed package finds `base` and toml11; consumers use
`find_package(toml_config CONFIG REQUIRED)` and link the same target.

| Operation | Purpose |
|---|---|
| `toml::get<Config>(document)` | Create and populate a config using its converter. |
| `nom::tcfg::get_to(document, candidate)` | Populate an existing candidate without replacing its initialized defaults. |
| `toml::value document(config)` | Serialize a config using its converter. |

`NOM_TCONFIG` is declared in the same namespace as the config type. It supplies
config-type registration and argument-dependent `from_toml` / `to_toml` functions:

```cpp
void from_toml(const toml::value& document, domain_type& value);
void to_toml(toml::value& document, const domain_type& value);
```

A framework adapter connects these functions to toml11's native `from<T>` and
`into<T>` facilities. `nom::tcfg::get_to()` uses the in-place `from_toml` operation.
The adapter is for explicitly mapped config types, not a catch-all replacement
for toml11 conversions. Macro placement, member names, and presence policies
therefore remain consistent across application config structures.

Custom domain types can use these same in-place functions, declared beside their
type, or native `toml::from<T>` and `toml::into<T>` specializations. Enable a custom
type before its first mapped use:

```cpp
template <>
inline constexpr bool nom::enable_config_type<domain_type> = true;
```

Enabling a type does not supply converters. For a type using only native
return-by-value conversion, `get_to()` assigns the converted result; preserving
existing nested defaults requires an in-place `from_toml` implementation. Supply
one conversion route per type so precedence is unambiguous. Renamed keys and
domain types represented by scalars or collections use custom converters. Use
[`NOM_TCONFIG_ENUM`](toml_cpp_mapping.md#enum-mapping) for string enums.

Conversions must reject invalid representations before information is lost.
Direct mapping propagates mapping/converter exceptions. `get_to()` may modify its
candidate before failing; callers must not pass an active application config.
The loader translates failures to `config_error` with the mapping stage, selected
file, config pointer, and available toml11 source context. Containers and wrappers
must retain the full nested pointer, including the rejected value where useful.
No JSON-specific diagnostic setting or JSON intermediate representation is used.

## Default and optional wrappers

Use an ordinary member for a required value, `cfg_defaulted<T>` for an omittable
value with a C++ default, and `cfg_optional<T>` (`std::optional<T>`) for explicit
absence. The default wrapper remains an aggregate with `value`, `get()`, implicit
reference conversions, and `operator->` / `operator*`. For example,
`cfg_defaulted<cfg_int> timeout_s{5}` stores an always-present default.
Use `*timeout_s > 0` when a numeric expression would otherwise require two
user-defined implicit conversions.

| Member | Missing key | Supplied value |
|---|---|---|
| Ordinary `T` | Error, even with a C++ initializer | Map to `T` |
| `cfg_defaulted<T>` | Retain the initialized value | Map into the wrapped `T` |
| `cfg_optional<T>` | Retain the initialized optional | Map into the contained `T` |

An optional without an initializer stays empty when its key is absent. If C++
initializes it with a value, omission preserves that value. A malformed supplied
value fails mapping; it does not trigger a default fallback.

TOML has no null value, and this framework adds no null sentinel. A defaulted
member serializes as its underlying value. An engaged optional serializes as its
contained value; an empty optional causes the entire member key to be omitted.
`"null"` is ordinary string data, never absence. An empty inline table is a present
table, not an absent value.

There is consequently no TOML value or runtime `--set` value that clears an
initialized optional. Removing a source key restores the missing-key policy.
If application code manually empties an optional that has an engaged C++ default,
serialization omits the key and a fresh load restores that default; a general
round trip of that deliberately cleared C++ state is not representable in TOML.
This does not change the normal load/check workflow, which uses the same initializers.

Optionals are supported as structure members. Optional container elements, optional
map values, nested optionals, and `cfg_defaulted<std::optional<T>>` are unsupported.
An empty optional cannot be serialized as a standalone TOML value. No placeholder
value is inserted into a container, and no element or map entry is silently dropped.

## Object shape and nested defaults

Every structure mapped by `NOM_TCONFIG` requires a TOML table. Arrays, numbers,
strings, and date/time scalars fail at that boundary. Unknown application keys
are ignored by structure mapping and omitted when that structure is serialized;
applications requiring a closed schema must add their own checks.

Initialize a private C++ candidate once, then populate its members in place. For
nested structures, keep the already initialized member so omitted defaulted and
optional fields retain values supplied by the parent. If the type declares a
timeout of `5` and the parent initializes it to `42`, a partial connection table
supplying only `address` must preserve `42`. Required members still require keys
whenever their containing table is supplied.

For an engaged optional containing a structure, populate its existing value. For
an empty optional, construct the contained value and then map it. A missing
required nested table fails even if that C++ member has an initializer; an omitted
defaulted nested table retains the entire initialized value.

Arrays and maps map their supplied contents, replacing the destination container;
their elements use the same checked converters. Do not merge serialized defaults
into the input to fill required keys: doing so would hide required-key errors.
Publish the candidate only after complete mapping and root `validate()` succeed.

## Value conversion

Numeric checks belong in the TOML adapters, not the common data types. Both
`cfg_int` and `cfg_uint` reject booleans, strings, floating-point values (including
`1.0`), and values outside their representable TOML range. `cfg_uint` also rejects
negative integers. `cfg_double` accepts integers and floats, permits ordinary
floating-point rounding, and requires a finite result. It rejects nonfinite values
on serialization as well as deserialization.

The parser/writer must enforce the [shared TOML profile](tcfg.md#toml-values-and-portability)
before custom conversion. This includes integer bounds, explicit nonfinite float
handling, and temporal normalization. Parsing or serializing a date does not
implicitly convert it to a string. Keep these source-value checks separate from
application-specific ranges and the root `validate()` protocol.

`nom::tcfg::parse_config(text, label)` parses an application table using this
profile, and `nom::tcfg::format_config(document)` validates and serializes a table.
The loader and check-output path use these functions. Raw native toml11 calls
remain available but do not apply the framework profile.

Use `toml::spec::v(1, 0, 0)` explicitly for native parse/format calls. Keep toml11 in
precompiled mode with `TOML11_COMPILE_SOURCES` propagated to consumers; its compiled
adapter owns dependency headers, archive, package files, and license installation.
Source and installed consumer tests exercise module/header use, common config types,
custom application mappings, and compile-time rejection of unsupported members.
See [TODO.md](../../TODO.md) for validation evidence.
