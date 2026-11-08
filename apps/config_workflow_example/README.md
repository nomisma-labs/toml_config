# config_workflow_example

This application demonstrates the full configuration workflow: build and generate
configs, load and map them to C++, validate startup, run CTest checks, and install
the application and generated configs. The linked consumer tests also demonstrate
using the library through its installed CMake package.

Startup remains in `main.cpp`: parse config arguments, load and validate
the config, then initialize the application or exit through `--check-config`.
See [md_capture](../md_capture/README.md) for a comprehensive config example that
illustrates the tcfg language.

## Build

Run all commands in this README from the repository root. Follow the shared
[toolchain requirements](../../docs/kit/build.md#toolchain), then:

```bash
cmake --preset dev
cmake --build --preset dev --target config_workflow_example
```

The executable is `build/dev/bin/config_workflow_example`. Its config directory is
collected into `build/dev/config/config_workflow_example/`. The build also generates
`build/dev/genconfig/dev/config_workflow_example.toml` and
`build/dev/genconfig/prod/config_workflow_example.toml`.

## Config structure

`main.cpp` defines `app_config`, maps its members using `NOM_TCONFIG`,
and implements the root `validate()` protocol.

| Field | C++ type | Default / constraint |
|---|---|---|
| `endpoint` | `cfg_defaulted<cfg_string>` | `https://example.test/feed`; must be nonempty |
| `timeout_s` | `cfg_defaulted<cfg_int>` | `10`; must be positive |
| `enabled` | `cfg_defaulted<cfg_bool>` | `true` |
| `interface_name` | `cfg_optional<cfg_string>` | Absent by default |

The common types are available through `nom::cfg_types`; `nom.toml_config`
re-exports their format-independent module. All fields are defaulted or
optional, so loading an empty TOML table succeeds. If config lookup finds no
file, these C++ defaults also support hard-wired initialization.

The ordinary [config_workflow_example.toml](config/config_workflow_example.toml) supplies the three
defaulted values. The simulated application prints the timeout after initialization;
`enabled` and `interface_name` illustrate mapping and are not used by its behavior.

## Run

Select the collected default through a search directory:

```bash
NOM_CONFIG_DIR=../config build/dev/bin/config_workflow_example
```

`NOM_CONFIG_DIR` entries are resolved against the executable directory, so
`../config` selects `build/dev/config`. The app reports the selected source and
absolute path, then prints `Application initialized; timeout: 10 seconds`.

Select a file explicitly and override its timeout:

```bash
build/dev/bin/config_workflow_example \
    --config build/dev/config/config_workflow_example/config_workflow_example.toml \
    --set /timeout_s=20 --check-config
```

This reports the lookup, selected source/path, and final TOML, then exits successfully
before application initialization. Without `--check-config`, it prints the source and
initialization message with a timeout of 20 seconds.

| Argument | Meaning |
|---|---|
| `--help`, `-h` | Print generated option help before config loading |
| `--config FILE`, `-c FILE` | Select one TOML file; relative paths use the working directory |
| `--set POINTER=value` | Override an existing config value; repeatable, applied in order |
| `--check-config[=MODE]`, `-k [MODE]` | Load, map, validate, report, and exit before initialization |

The check modes are `full` (the default: lookup details and final TOML), `view`
(TOML only), and `silent` (`OK` only). TOML reflects runtime substitutions, CLI
overrides, and C++ defaults; absent optional members are omitted.

Adjacent forms such as `--config=FILE` and `--set=/timeout_s=20` are also accepted.
Unrecognized arguments print usage and exit with status 1. Config errors print
their loading stage and exit with status 1; for example, setting `/timeout_s=0`
fails root validation. The app has no application-specific options.
See [app/config binding](../../docs/toml_config/app_config_binding.md) for lookup
precedence, environment selection, runtime variables, and override rules.

## Generated sections and CMake tests

The [tcfg source](config/config_workflow_example_tcfg.toml) defines `dev`, which imports
the ordinary TOML file, and `prod`, which extends `dev` and changes `endpoint` to
`https://example.test/production-feed` and `timeout_s` to `30`.

`CMakeLists.txt` registers generation and generated-config tests:

```cmake
nom_tcfg_generate(config_workflow_example SOURCE config_workflow_example_tcfg.toml BUILD_WITH_APP)
nom_tcfg_test(config_workflow_example dev)
nom_tcfg_test(config_workflow_example prod)
```

The helpers check the project's options internally: generation requires
`nom_build_apps`, and tests require both `nom_build_tests` and `nom_build_apps`.
The separate override test keeps its guard because it uses `add_test()` directly.

Omitting `SECTIONS` generates all enabled sections. `BUILD_WITH_APP` prepares the
generated files whenever this app is built. Select a generated section explicitly:

```bash
build/dev/bin/config_workflow_example --config build/dev/genconfig/prod/config_workflow_example.toml
```

It reports the selected config and initializes with a timeout of 30 seconds.
Generation can also be requested separately:

```bash
cmake --build --preset dev --target toml_config_generate_tcfg_config_workflow_example
```

In a `complete` build, run the example's four CTest entries with the command below; a `dev`
build leaves integration tests out and runs only the two `nom_tcfg_test()` checks:

```bash
ctest --preset complete -R '^toml_config_config_workflow_example_'
```

Two `nom_tcfg_test()` checks exercise the real loader, mapping, and validation for
`dev` and `prod`. A separate integration test loads the collected ordinary TOML,
applies `/timeout_s=20`, and uses `--check-config`. These tests expect the configs
and executable to have been built first.

The CLI suite generates this example's sections in a temporary directory and runs
the real executable. It checks each section's timeout, config-key lookup through
`NOM_CONFIG_DIR`, runtime substitutions and overrides, C++ defaults, generated help,
short aliases, and all three check modes before initialization.
Mapping and validation errors must report their context and prevent
startup. The [consumer tests](../../tests/integration/library_usage/README.md)
also exercise generated configs through source and installed-package usage.

See [build-system integration](../../docs/toml_config/build_system_integration.md)
for the helper API, aggregate config targets, cleanup, and installation.

## Install and run

With installation enabled, build all selected targets and generate configs before
installing into a staging prefix:

```bash
cmake --build --preset dev
cmake --build --preset dev --target config
cmake --install build/dev --prefix "$PWD/build/dev/stage"
NOM_CONFIG_DIR=../genconfig/prod build/dev/stage/bin/config_workflow_example --check-config
```

The installed executable selects `../genconfig/prod/config_workflow_example.toml` relative to
its own directory. Loading this generated TOML needs neither Python nor the tcfg
source files. Use a fresh staging prefix to avoid files left by earlier installs.
