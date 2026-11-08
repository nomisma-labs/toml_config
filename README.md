# toml_config

> **Documentation review draft — implementation pending.** This page defines the
> target contract. Commands and APIs below are implementation acceptance criteria,
> not claims that this checkout already supports them. See [status](TODO.md).

<!-- repo-description:begin -->
**toml_config** is Nomisma's TOML configuration framework for C++ applications.
It loads settings into typed C++ structures, validates them before application
startup, and generates configuration variants from structured configs.
<!-- repo-description:end -->

Start with the [introduction](docs/toml_config/intro.md): create a config file,
build and load it in your app, then explore structured configs and variants.

## Build

The C++ library uses named modules and `import std`. The supported toolchain uses
CMake 4.4.x, Ninja, GCC 16 or Clang 22, and libstdc++ 16 module sources. Follow the
[toolchain setup](docs/kit/build.md#toolchain) for compiler and dependency installation.
The `dev` preset uses GCC 16.

Initialize dependencies, then build the library and examples and run the fast tests:

```bash
git submodule update --init --recursive
cmake --workflow --preset dev
```

Executables are written to `build/dev/bin/`. For a fresh build with all tests,
including integration tests, run `./bootstrap.sh complete`; it recreates
`build/complete/` and runs the repository checks. The
[build guide](docs/kit/build.md) covers incremental builds, other presets,
installation, and validation across toolchains. For using `toml_config` from
another project, the [consumer example](tests/integration/library_usage/README.md)
covers source and installed-package integration, including module setup.

## Docs

The [framework documentation](docs/toml_config/README.md) is the main reference.
Choose a guide according to what you want to do:

| Task | Guide |
|---|---|
| Select configs, use environment variables, or override values | [Loading and application integration](docs/toml_config/app_config_binding.md) |
| Define C++ config types, defaults, and validation | [TOML/C++ mapping](docs/toml_config/toml_cpp_mapping.md) |
| Generate, test, and install configs through CMake | [Build integration](docs/toml_config/build_system_integration.md) |
| Compose structured configs and define variants | [tcfg language](docs/toml_config/tcfg.md) |
| Generate TOML files or inspect available sections | [Config generation](docs/toml_config/config_generation.md) |

Planned examples include their own build, usage, and test instructions:

- [config_workflow_example](apps/config_workflow_example/README.md): the full generation, loading, validation, and installation workflow.
- [config_args_example](apps/config_args_example/README.md): ordinary TOML and application arguments alongside config options.
- [md_capture](apps/md_capture/README.md): a larger configuration with shared fragments and several variants.

See the [tools overview](tools/toml_config/README.md) for the generator, reusable
Python engine, build utility, and shell helpers. The template sync and shared
shell helpers are available now; the generator, C++ mapping, and examples described
here await documentation review and implementation. Release changes are recorded in
[CHANGELOG.md](CHANGELOG.md); implementation status, planned work, and open decisions
are in [TODO.md](TODO.md).

## Platform context

`toml_config` uses Nomisma's shared build kit, maintained in `cmake_template`.
The [platform documentation](docs/kit/README.md) describes the general build and
repository rules. Contributors can use the [conventions](docs/kit/conventions.md)
and [recipes for adding libraries, apps, tests, and dependencies](docs/kit/howto.md).

The `base` library supplies the format-independent configuration types;
toml11 provides TOML parsing and mapping, and Boost.Program_options supports argument
parsing. See the [mapping implementation notes](docs/toml_config/toml11_implementation.md)
for those boundaries. [json_config](https://github.com/nomisma-labs/json_config) is
the alternative JSON configuration framework. A project chooses one framework;
coexistence and compatibility between their tools or APIs are not requirements.

Instructions for automated contributors are in [AGENTS.md](AGENTS.md).
