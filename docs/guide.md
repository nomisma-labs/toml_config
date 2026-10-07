# Writing and using configuration

Write ordinary `.toml` configuration directly, or compose it from **tcfg** inputs
using the Python generator. The build system collects configuration files;
C++ applications locate an ordinary TOML file, parse it, and bind its values.

## Start with the example

From the repository root:

```bash
git submodule update --init --recursive
cmake --preset dev
cmake --build --preset dev -j 4
ctest --preset dev
build/dev/bin/capture_example --check-config
build/dev/bin/capture_example --print-config
```

The example binds nested `log`, `feed`, and `storage` tables to C++ structures.
It prints a short summary and makes no network requests. Its `.invalid` endpoint
is intentionally an example address.

`apps/capture_example/config/defaults.toml` provides common values;
`capture_example.tcfg` imports a symbol list and changes the timeout;
`debug.tcfg` derives another variant with a debug log level, a smaller symbol
list, and an environment binding. See [the language specification](tcfg.md) for
all directives and their precise ordering. The checked-in `capture_example.toml`
is a complete ordinary TOML example; C++ can load it without generation.

## Generate TOML with Python

Python 3.11 or newer is required for the generator because it uses the standard
library's `tomllib` parser. It has no third-party runtime dependencies and can
run from source without installation:

```bash
python3 cfggen.py \
  apps/capture_example/config/capture_example.tcfg \
  -o build/capture.toml

python3 cfggen.py \
  apps/capture_example/config/debug.tcfg \
  --set 'log.level = "warning"' --check

build/dev/bin/capture_example --config build/capture.toml --check-config
```

`cfggen.py` is a thin launcher for `python/toml_config/__main__.py`; it finds the
adjacent `python/` directory automatically, including when called from another
working directory. `PYTHONPATH=python python3 -m toml_config` remains an equivalent
entry point. Both commands use the same generator implementation.

Omit `-o` to write TOML to stdout. Repeat `--overlay FILE` to merge additional
resolved files; repeat `--set TOML` to apply final patches. `--check` resolves and
validates the language without writing output; it does not validate the C++
application schema. Use the application's `--check-config` for typed and domain
validation. Failures return exit status 2 with a diagnostic.

Generation validates the complete result before atomically publishing an output
file. A failed generation leaves the last successful artifact intact; the build
still fails, so do not deploy artifacts from a failed build. Output content is
deterministic and unchanged content is not rewritten. `--depfile FILE` records
all contributing files for build tools. Input and output files must be distinct.
`--depfile` requires `--output`; `--check` cannot be combined with either option.
The depfile must also differ from the output and all input files.

For Python code, add `python/` to the import path or install the project package
with `python3 -m pip install .`. Package builds use setuptools 77 or newer; this
is a build dependency, not a generator runtime dependency. The package version
is read from the repository's CMake version declaration.

```python
from toml_config import dumps, load

resolved = load("service.tcfg", environment={"SERVICE_TOKEN": "example"})
print(resolved.dependencies)
print(dumps(resolved.values))
```

Passing `environment={}` disables access to the process environment for that
load, while still allowing explicit defaults in `tcfg.env` entries. Environment
binding names must match `[A-Za-z_][A-Za-z0-9_]*`. Bindings preserve empty values
and always produce strings.

## C++ binding and initialization

Include the parser and binding declarations before importing the library module.
The example's `settings.h` demonstrates complete nested mappings:

```cpp
#include <string>
#include <toml.hpp>

struct settings
{
    std::string endpoint;
};
TOML11_DEFINE_CONVERSION_NON_INTRUSIVE(settings, endpoint)

import nom.toml_config;

int main(int argc, char* argv[])
{
    auto options = nom::config::parse_arguments(argc, argv);
    auto config = nom::config::initialize<settings>(options);
    // Start application work after binding and domain validation.
}
```

The macro maps TOML keys to identically named members, including nested mapped
types and standard containers. Listed non-optional fields are required; a C++
member initializer does not make one optional. Use `std::optional<T>` and
`value_or(default_value)` for simple defaults. Write a `toml::from<T>`
specialization when names differ or custom conversion is required. Perform
domain validation (such as positive timeouts) before constructing application
services. Prefer `std::int64_t` for TOML integers, as the example does; check
ranges in a custom conversion before binding into a narrower integer type.
Unknown application keys are retained and ignored by these bindings. Closed
application schemas require application-specific validation.

`initialize<T>` discovers a TOML file, parses it, and binds the result. It returns
the typed `value`, parsed document in `resolved`, and `location`. `load(path)`,
`bind<T>(document)`, and `format(document)` are also available independently.
The document contains the parsed TOML `value`.

`locate_config` accepts an optional environment callback for controlled discovery
tests or embedding applications. By default it uses the process environment.
Composition, environment bindings in tcfg, overlays, and assignment patches are
handled by `cfggen.py` before the C++ application starts.

The library throws errors and never exits the process or writes diagnostics.
`parse_arguments` only parses arguments: it leaves `executable` and `app_name`
unset and performs no filesystem or executable lookup. Set these fields explicitly
when supplying an application location or name; otherwise discovery determines
them only after explicit file overrides have been checked.
The recognized options are `--config`/`-c`, `--config-dir`, `--check-config`,
`--print-config`, and `--help`/`-h`. The application handles `help`, `check_config`,
`print_config`, and any
`remaining_arguments` returned by `parse_arguments`. The example handles all
three modes before application work. Explicitly printing resolved configuration
also prints any bound credentials; it is an operator-requested diagnostic.
In the example, `--print-config` takes precedence when combined with
`--check-config`, and both modes run typed binding and domain validation first.

## Discovery and path rules

Discovery checks these locations in order and stops at the first selected file:

1. `--config FILE` / `-c FILE`.
2. `TCFG_CONFIG`, if present. An empty or missing selected file is an error;
   discovery does not silently fall back.
3. Repeated `--config-dir DIR` directories, followed by `TCFG_CONFIG_DIR` entries.
4. Beside the executable.
5. `<executable-dir>/../generated_config/<app>/`.
6. `<executable-dir>/../config/<app>/`.

Each explicit search directory checks `<dir>/<app>.toml`, then
`<dir>/<app>/<app>.toml`. Other locations check `<app>.toml`.
Explicit file selections must also be `.toml`. `TCFG_CONFIG_DIR` uses `:`
separators; empty entries are ignored. Relative search directories are
executable-relative.
The application name defaults to the executable stem and may be set in
`application_options.app_name`. If `application_options.executable` is empty,
directory discovery requests the running executable from the private OS utility.
The current Linux backend resolves the actual executable, including launches
through `PATH` and symlinks. There is no guessed `argv[0]`/`PATH` fallback.
An explicit `--config` or `TCFG_CONFIG` requires no executable lookup; `--help`
also works without it. OS lookup failure during directory discovery is an error.
Linux is the currently supported backend; another OS needs a validated backend
before it can be built. See [the OS utility boundary and migration plan](os_utilities.md).

Explicit file arguments and `TCFG_CONFIG` are relative to the startup working
directory. References used by the Python generator are relative to the canonical
declaring file. Application path strings are ordinary data;
`resolve_path(location, value)` is an explicit helper for resolving one relative
to the selected entry file. If you relocate generated TOML, relative application
paths consequently have a different base when using that helper. Choose a
deployment convention, use absolute data paths, or resolve against an explicit
application data directory when that distinction matters.

## Build and installation

The project uses its existing CMake kit. Configuration generation is an optional
project-owned helper, not a change to the shared kit:

```cmake
include(path/to/toml_config/cmake/tcfg.cmake)
nom_app(service SOURCES main.cpp DEPS nom::toml_config)
tcfg_generate(TARGET ${PROJECT_NAME}_service
    INPUT "${CMAKE_CURRENT_SOURCE_DIR}/config/service.tcfg"
    OUTPUT "${PROJECT_BINARY_DIR}/generated_config/service/service.toml"
    INSTALL_DESTINATION "generated_config/service")
```

The helper discovers Python only when invoked, attaches generation to the app
target, and uses a depfile for transitive inputs. Outputs have explicit names.
It supports `OVERLAYS`, `SET`, and extra `DEPENDS` files. Generated files live
outside the kit's copied source-config directory, so that copy cannot erase
them. Each output and depfile has one producer; duplicate claims fail during
configuration. Installation follows the owning app's selection, so apps excluded
from the default build do not install generated configs. `nom_install=OFF`
disables these installation rules. Ordinary incremental builds regenerate only
when dependencies change.
Environment changes alone are not file dependencies: remove the generated output
to regenerate after changing a bound environment variable, or provide an
environment stamp file through `DEPENDS` in controlled build automation.

By default the sample reads generated TOML from `generated_config/`. Disable
sample generation with `-DTOML_CONFIG_GENERATE_EXAMPLE=OFF` to use the complete
`capture_example.toml` staged by the existing config collector under `config/`.
The C++ library needs no Python at runtime. A build with tests and sample
generation disabled does not require a Python interpreter at configure time.
Deploy the final TOML file with the application; generation inputs are needed
where `cfggen.py` runs.

Build before installing:

```bash
cmake --install build/dev --prefix /tmp/toml_config-install
/tmp/toml_config-install/bin/capture_example --check-config
```

Consumers use `find_package(toml_config CONFIG REQUIRED)` and link
`nom::toml_config`, with C++23 and a compiler supporting the repository's native
module workflow. The install includes toml11 headers and its license, module
interfaces, libraries, example files, and the generator under
`share/toml_config/python`, with its launcher at `share/toml_config/cfggen.py`.
The optional generation helper is installed as
`share/toml_config/cmake/tcfg.cmake` and invokes that launcher. Run the installed
generator with `python3 <prefix>/share/toml_config/cfggen.py INPUT -o OUTPUT`.
The launcher and helper continue to work when the installation prefix is moved.

Use a fresh install prefix when removing or renaming packaged files; ordinary
CMake installation does not remove artifacts from previous installations.

## Troubleshooting and design scope

- A missing generator input is a hard error. Make the complete input tree
  available when generating TOML.
- A reference cycle reports the active file chain. Share bases without making
  them depend on their derived variants.
- A missing required binding field means composition succeeded but the result
  does not satisfy the C++ type. Check the resolved TOML and member spelling.
- Generator strings in `--set` require TOML quotes: `--set 'log.level = "debug"'`.
- Arrays replace; explicit imports select arrays from TOML fragment tables.
- The generator normalizes time fractions to microseconds. Its portability
  rules require UTF-8 without a leading byte-order mark and LF or CRLF line
  endings; year zero, leap seconds, and finite float literals that overflow
  binary64 are rejected. See the specification for details.

There is no automatic reload, remote configuration service, secret manager,
schema generator, string interpolation, or Rust interpreter in this version.
Applications can implement reload by constructing and validating a new typed
configuration, then swapping it into use only after successful initialization.
