# Toolchain findings

Supported tools and versions are recorded in [Build: Toolchain](../build.md#toolchain).
The presets use GCC 16 for normal builds and Clang 19 for the second compiler and sanitizers.

## Native modules

The `nom.example` primary interface, exported partitions, implementation units and importing
apps and tests build on GCC 16 and Clang 19. Library usage tests cover both source and installed
package consumption; installed consumers build their own compiler-specific BMIs. The sandbox
geometry module exercises a native interface and partition with the `complete` preset.

Run the current module builds and tests from the template root:

```bash
cmake --workflow --preset dev
cmake --workflow --preset clang
cmake --workflow --preset complete
```

## Sanitizers

The `asan` preset uses Clang 19 with AddressSanitizer and UBSan:
`-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer`.
It covers the native-module example and importing consumers.

```bash
cmake --workflow --preset asan
```

## Third-party module boundaries

The [third-party findings](third_party_in_modules.md) cover the GCC 16 warning when exporting a
nlohmann JSON alias and the tested Metal typelist alias on GCC 16 and Clang 19. JSON stays private
to the settings implementation; Metal supplies the exported typelist machinery.

## compile_commands.json and clang tools

The `dev` and `clang` presets generate compilation databases. For the same importing source,
`apps/hello/main.cpp`, the compilers record different module flags (other options omitted):

```text
g++-16 -std=c++23 -fmodules-ts -fmodule-mapper=…/main.cpp.o.modmap -fdeps-format=p1689r5 … -c main.cpp
clang++-19 -std=c++23 @…/main.cpp.o.modmap … -c main.cpp
```

Use `build/clang/compile_commands.json` for Clang tools; the GCC database contains module flags
they cannot use. `.clangd` selects the Clang database for the editor.

`tools/check_naming.sh` configures the `clang` preset with `-DNOM_BUILD_PRESET=complete`, then
builds it so that module BMIs are available, including those used by sandbox apps. It runs
`run-clang-tidy-19` over the native module units and importers in `core/`, `apps/` and `tests/`
using that database. The naming check passes for the current native-module example and
generated-repository recipe.

clangd-19 with `--experimental-modules-support` in VS Code, and gdb on importing code, remain
checklist items to validate.
