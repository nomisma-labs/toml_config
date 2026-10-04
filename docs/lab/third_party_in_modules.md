# Third-party code with CMake and modules

Updated: 2026-10-04. The findings below describe the current GCC 16/Clang 19 toolchain.

## nlohmann_json in a module's global module fragment

### GCC 16 results

Validated on 2026-10-03. Local environment: Ubuntu 26.04.1 LTS, GCC 16.0.1 experimental snapshot
20260322
(`g++-16`, Ubuntu package `16-20260322-1ubuntu1`), Clang tools 19.1.7, CMake 4.4.3,
and Ninja 1.13.2. This probe uses GCC and the pinned nlohmann_json v3.12.0 submodule.

**Result:** a module including `<nlohmann/json.hpp>` in its global module fragment compiles.
Exporting an alias for `nlohmann::json` produces a `-Wexpose-global-module-tu-local` warning;
an importing consumer compiles, links, and successfully parses JSON. Compiling that module
with `-Werror` fails with `-Werror=expose-global-module-tu-local`.

The warning identifies `json_pointer::split` in `detail/json_pointer.hpp:666` exposing the
TU-local `detail::unescape` helper. Exporting nlohmann types is unsuitable for our
warnings-as-errors CI. The template keeps JSON parsing in a private module implementation.

Probe sources, created in an isolated temporary directory:

```cpp
// json.cppm
module;
#include <nlohmann/json.hpp>
export module probe.json;
export namespace probe
{
    using json = nlohmann::json;
}
```

```cpp
// main.cpp
#include <string>
import probe.json;

int main()
{
    const auto value = probe::json::parse("{\"answer\":42}");
    return value.at("answer").get<int>() == 42 ? 0 : 1;
}
```

Set `template_source` to the template checkout, then run these commands in the probe directory:

```bash
g++-16 -std=c++23 -fmodules-ts -I"$template_source/external/nlohmann_json/include" \
  -x c++ -c json.cppm -o json.o
g++-16 -std=c++23 -fmodules-ts main.cpp json.o -o json_probe
./json_probe
g++-16 -std=c++23 -fmodules-ts -Werror -I"$template_source/external/nlohmann_json/include" \
  -x c++ -c json.cppm -o json-strict.o
```

The first three commands exit 0; the final warnings-as-errors compile exits 1.

### Current template boundary

`nom.example:settings` defines the settings type and declares `parse_settings`,
`serialize_settings` and `load_settings` using standard-library types. `settings.cpp` includes
`<nlohmann/json.hpp>` in its global module fragment and implements those services in
`module nom.example;`. JSON types and mapping details stay inside the implementation; consumers
import `nom.example` to use these services.

nlohmann is a private CMake dependency. It is still listed in the installed package dependencies
because a static library's exported link interface carries private target references.

**For macro-based configuration or logging APIs:** macros must remain in headers. Keep our
types and services in named modules, then choose a header or module wrapper for the
third-party integration that the macros require. The example's private JSON implementation is
appropriate when callers only need parsing and serialization services; it does not establish
that every macro-based configuration API can hide its JSON types the same way.

**Retest** after relevant compiler or nlohmann upgrades using the isolated alias-export probe
above with warnings as errors, then validate the intended dependency boundary with both
supported compilers.

## Metal through a native module

Validated on 2026-10-03 with Metal v2.1.4, GCC 16 and Clang 19, using the toolchain recorded
above. `nom.example:types` includes Metal's `list`, `at` and `number` headers in its global module
fragment, then exports `type_at_t<Index, Types...>`. The primary `nom.example` interface
re-exports that partition. Importing unit tests and both source and installed-package consumers
instantiate the alias successfully on both compilers; the package consumer rebuilds the module
interfaces using the installed Metal headers.

This validates a small public template backed by Metal. Full relay-style filtering and dispatch,
and their compile-time and runtime performance, remain separate investigations.

Metal is retained as a foundation submodule when initializing a repository. `nom_find_metal()`
provides the shared `nom::metal` header target without configuring Metal's upstream project.
The separate `nom_metal` package installs the headers and license; a standalone consumer using
`find_package(nom_metal 2.1.4 EXACT CONFIG REQUIRED)` passes. A two-project build sharing
`nom::metal` also installs both exported packages successfully. Public users list `nom_metal`
in `nom_install_package(DEPENDENCIES …)`.

## Third-party CMake projects as subprojects

The following findings were recorded with CMake 4.4.3.

**metal** (v2.1.4): running its CMake project through `FetchContent_MakeAvailable` adds about
2,100 targets with generic names (`example`, `bundle`, `doc`), looks for Doxygen and Boost, and
prints a deprecation warning under CMake 4.4. In a superbuild those names would collide. Since metal
is header-only, use it through its include directory and never run its CMake project; for example,
declare it with a `SOURCE_SUBDIR` that has no `CMakeLists.txt`, so FetchContent only records
the sources, and add `${metal_SOURCE_DIR}/include` to the target that needs it.

**nlohmann_json** (v3.12.0): works as a subproject. When it isn't the top-level project its tests
are off, and its install rules are off too unless `JSON_Install` is set, which the template does
(so an installed package brings nlohmann along for `find_package` consumers).

Other libraries: case by case.
