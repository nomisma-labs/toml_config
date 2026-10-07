# toml_config

<!-- repo-description:begin -->
Application configuration built on TOML. **tcfg** (“tee-config”) composes `.tcfg`
files into ordinary TOML using the Python generator. C++ applications locate,
parse, and bind the resulting TOML to their settings structures.
<!-- repo-description:end -->

```toml
[tcfg]
version = 1
extends = ["defaults.toml"]

[[tcfg.import]]
file = "symbols.toml"
select = ["symbols"]
into = ["feed", "symbols"]

[feed]
timeout_ms = 2000
```

Layers merge tables recursively; arrays and scalar values replace. Explicit
directives support fragment imports, subtree replacement/deletion, and environment
bindings. Required missing inputs, invalid directives, and reference cycles fail
with diagnostics. Each deployment variant has its own entry file.

The C++23 library exposes `import nom.toml_config;`, configuration discovery,
and typed initialization. It uses toml11 v4.4.0's non-intrusive mapping
macros. The Python generator requires Python 3.11+ and has no runtime package
dependencies. CMake generation is optional and tracks transitive input files.

## Try it

```bash
git submodule update --init --recursive
cmake --preset dev
cmake --build --preset dev -j 4
ctest --preset dev

build/dev/bin/capture_example --check-config

python3 cfggen.py apps/capture_example/config/debug.tcfg -o build/capture.toml
build/dev/bin/capture_example --config build/capture.toml --check-config
```

The example demonstrates nested mappings and initialization without making
network connections. By default, CMake generates its TOML from the sample tcfg
entry. With `-DTOML_CONFIG_GENERATE_EXAMPLE=OFF`, the sample uses the ordinary
`capture_example.toml` collected from its `config/` directory. Library-only builds
can set
`-DTOML_CONFIG_BUILD_APPS=OFF -DTOML_CONFIG_BUILD_TESTS=OFF` and require no Python.

## Learn and integrate

- [Author and application guide](docs/guide.md): workflows, bindings, discovery,
  CMake integration, and deployment.
- [tcfg 1 specification](docs/tcfg.md): language contract and portability rules.
- [Parser choice](docs/parser_choice.md): toml11 evaluation and module boundary.
- [Build reference](docs/build.md): GCC/Clang toolchains, presets, and shared kit.

Install after building with `cmake --install build/dev --prefix <prefix>`.
Consumers use `find_package(toml_config CONFIG REQUIRED)` and link
`nom::toml_config`. Module interfaces, the compiled TOML dependency, its headers
and license, and optional Python/CMake tooling are installed with the package.

## Repository layout

| Path | Purpose |
|---|---|
| `core/toml_config/` | C++ TOML loading, discovery, and public module |
| `core/toml_config/util/` | Private OS utility and platform implementation |
| `cfggen.py` | Standalone Python generator launcher |
| `python/toml_config/` | Python interpreter, serializer, and CLI |
| `cmake/tcfg.cmake` | Optional configuration generation helper |
| `apps/capture_example/` | Typed initialization example and configurations |
| `tests/conformance/` | Python generator's accepted/rejected language cases |
| `tests/unit/`, `tests/python/`, `tests/integration/` | Behavior and integration tests |

Run `./bootstrap.sh` for the repository's full validation workflow, or select a
preset with `./bootstrap.sh ci`. See [AGENTS.md](AGENTS.md) and
[the conventions](docs/conventions.md) before contributing. The language
specification and fixtures can also guide future implementations in other languages.
