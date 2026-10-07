# C++ TOML parser choice

The C++ TOML loader uses **toml11 v4.4.0**, licensed under MIT and pinned as the shallow
`external/toml11` submodule at `be08ba2be2a964edcdb3d3e3ea8d100abc26f286`.
The upstream [release list](https://github.com/ToruNiina/toml11/releases/tag/v4.4.0)
was reviewed on 2026-10-04. The selected release is the latest published stable
release listed there.

| Requirement | toml11 | toml++ |
|---|---|---|
| Ordinary TOML parsing and serialization | Supports both | Supports both |
| Typed configuration conversion | `toml::get<T>`, `toml::from<T>`, `toml::into<T>` | Node/table access and typed value extraction |
| Struct mapping with little boilerplate | `TOML11_DEFINE_CONVERSION_NON_INTRUSIVE` | No equivalent struct-mapping macro in its documented API |
| TOML version control | Explicit `toml::spec::v(1, 0, 0)` | TOML 1.0 with separately enabled extensions |
| Compilation choices | Headers or precompiled library | Headers, compiled implementation, or module support |

Both libraries are suitable TOML parsers. toml11's conversion facilities are the
closer fit for application settings represented by C++ structs. The comparison
uses the projects' own [toml11 documentation](https://toruniina.github.io/toml11/docs/)
and [toml++ documentation](https://marzer.github.io/tomlplusplus/).

## Mapping C++ settings

```cpp
#include <toml.hpp>
#include <optional>
#include <string>

struct connection_config
{
    std::string host;
    int port;
    std::optional<std::string> token;
};

TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(connection_config, host, port, token)

// Given a resolved TOML table:
const auto settings = toml::get<connection_config>(table);
const toml::value round_trip = settings;
```

The macro belongs at global scope, after the struct definition. Use fully
qualified type names for structs in a namespace. Nested mapped structs and
standard containers compose through the same conversion system. The mapping
uses member names as TOML keys; non-optional members are required. The macro does
not reject unlisted TOML keys, perform domain validation, or retain ordinary
member initializers when required keys are absent. This release has **no
`WITH_DEFAULT` macro variant**. Implement a `toml::from<T>` specialization when
defaults, renamed keys, or validation require custom rules. Its
[conversion implementation](https://github.com/ToruNiina/toml11/blob/v4.4.0/include/toml11/conversion.hpp)
also supports `std::optional` members and limits a single macro invocation to
32 members.

## Syntax and compilation contract

The C++ loader uses TOML **1.0**. It passes `toml::spec::v(1, 0, 0)` to
parsing and serialization instead of inheriting an upstream default. Generated
TOML uses the same grammar. See
the upstream [TOML specification selector](https://toruniina.github.io/toml11/docs/reference/spec/)
and Python's [tomllib documentation](https://docs.python.org/3.11/library/tomllib.html).

The relevant raw APIs are:

```cpp
const auto version = toml::spec::v(1, 0, 0);
auto parsed_file = toml::parse("settings.toml", version);
auto parsed_text = toml::parse_str("enabled = true\n", version);
auto serialized = toml::format(parsed_file, version);
```

The project builds toml11 in its supported **precompiled mode**, with
`TOML11_COMPILE_SOURCES` propagated by `toml11::toml11`. A module/header smoke
test on GCC 16 found duplicate standard-library iterator mangling errors when
the full header-only parser appeared in both a module interface and an
importing translation unit. Precompiled mode passed the same parsing, macro
mapping, and serialization test on GCC 16 and Clang 19. It also avoids repeatedly
compiling the parser implementation. See upstream
[precompilation instructions](https://toruniina.github.io/toml11/docs/installation/).

`cmake/toml_dependency.cmake` creates the dependency through the shared CMake kit,
compiles its static archive with position-independent code, and installs the
archive, headers, CMake package, and MIT license. Consumers link
`nom::toml_config`; the public dependency and its compile definition propagate
automatically. A superbuild supplying its own `toml11::toml11` must use compatible
precompiled settings. Binding code includes `<toml.hpp>` before importing
`nom.toml_config`, because C++ module imports do not provide preprocessor macros.
