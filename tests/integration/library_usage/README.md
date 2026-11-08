# Library consumer tests

This standalone CMake project consumes toml_config in two ways: `find_package`
against an installation and `FetchContent` against the source tree. The repository
registers both through `nom_library_usage_tests()`; package tests also require
`nom_install`.

The consumer enables standard-library module detection before `project()` and opts its
model, executable, and compile-failure targets into `nom_enable_std_modules()`. Sources use
`import std;` for standard-library declarations and retain textual macro/third-party includes.

From the repository root, after building a preset with tests and installation enabled:

```sh
ctest --test-dir build/ci -R 'toml_config_library_usage_' --output-on-failure
```

The consumer's model imports only `nom.config_types`, supplied transitively by the
`base` dependency in both source and installed-package builds. Its executable adds
`NOM_TCONFIG` bindings and checks mapping, serialization, defaults, diagnostics,
hard-wired loading, and command-line parsing. Separate compile-failure tests reject
unsupported config member types.

A CTest fixture runs `tcfggen.py` on [consumer_tcfg.toml](consumer_tcfg.toml).
The consumer also checks generated help and normalized check output through
`print_config_help()` and `print_config_check()`.
It loads the generated files through `parse_config_arguments()` and
`load_config()`: the valid section checks inheritance, child overrides, and C++
defaults; the invalid section must report the expected validation stage, file, and
message. Selecting either loading test also runs its generation fixture.

The generator comes from this repository as test tooling. In package mode the C++
consumer uses the installed library, headers, and module interfaces; these tests do
not require installation of the generator or generation-specific CMake helpers.
