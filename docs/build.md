# Build

## Commands

Run `./bootstrap.sh` for dependency initialization, fresh builds/tests and quality checks.
Bootstrap discovers enabled configure/build/test presets with matching names through CMake,
including included files and `CMakeUserPresets.json`; it uses the repo's `build/<preset>/` layout.
The default run selects every discovered preset except `release`. Use `./bootstrap.sh <preset>`
to select one explicitly; `--help` lists the discovered names. For a personal preset, supply
matching build and test entries that reference its configure preset. CMake checks the compiler
and generator from the preset rather than bootstrap guessing them from its name.
Each run deletes only the selected build directories and previous `build/bootstrap/` logs.
Python compatibility/imports, headers and formatting are always checked; naming is included when
`clang` is selected. A failed check returns a nonzero exit code. Invalid arguments
are rejected before cleanup. For everyday incremental work, use the commands below.

```bash
git submodule update --init --recursive   # once, after cloning
cmake --preset dev                        # once: configure into build/dev
cd build/dev
ninja                                     # build; reruns cmake itself when a CMakeLists.txt changes
ctest --output-on-failure                 # test; -R <regex> picks tests by name
bin/<app>                                 # run an app
```

Other presets work the same way in `build/<preset>`. `cmake --workflow --preset <preset>`
configures, builds and tests in one command; CI uses it.
After changing the compiler, run `./bootstrap.sh` (or `./bootstrap.sh release` for Release)
to clear both the main build and the nested integration-test builds that cache the compiler.

## Toolchain

| Tool | Version | Used for |
|---|---|---|
| Ubuntu | 26.04 LTS | development and CI operating system |
| GCC | 16 (`g++-16`); installed compiler reports 16.0.1, experimental snapshot 20260322, package `16-20260322-1ubuntu1` | the main compiler |
| Clang tools | 19 (`clang++-19`, `clangd-19`, `clang-tidy-19`, `clang-scan-deps-19`, `clang-format-19`) | second compiler, sanitizers, IDE, checks |
| CMake | 3.30 or newer; 4.4.3 locally, Ubuntu package 4.2.3 for CI | build |
| Ninja | 1.11 or newer | generator (Makefiles can't build modules) |
| Python | 3.10 or newer; 3.14.4 locally | tools and Python integration checks; standard library only |
| Catch2 | 3 (system package, or a pinned download) | tests |

Only the versioned Clang names exist on Ubuntu (`clang++-19`, not `clang++`), so presets and
scripts name them explicitly. The installed GCC package is a development snapshot rather than
a final GCC 16 release. The CI image installs the same tools from Ubuntu packages; package
revisions without explicit pins are resolved when the image is built.

## Python environment

Repository scripts currently need no third-party Python packages or virtual environment.
Python 3.10 is the minimum because the scripts use annotations such as `str | None`;
the current local version is recorded in [Toolchain](#toolchain).

`python3 tools/check_python.py` checks the interpreter version, compiles repository Python
scripts in memory, and checks their imported modules. It discovers tracked and unignored new
scripts through Git; local helpers are syntax-checked without executing them. Bootstrap runs
this check before builds and skips Python-dependent steps if it fails. When `clang` is selected,
it also checks that the clang-tidy runner starts. The runner's optional PyYAML support is not
needed by our current naming check.

## Presets

`CMakePresets.json` holds the build settings that developers, CI, IDEs and agents share.

| Preset | Compiler and build type | Purpose |
|---|---|---|
| `dev` | GCC 16, Debug | daily work |
| `complete` | GCC 16, Debug | every app, including experiments, regardless of its `BUILD_FOR` list |
| `release` | GCC 16, Release | benchmarks and production builds |
| `clang` | Clang 19, Debug | second compiler; its database feeds clangd and clang-tidy |
| `asan` | Clang 19, Debug, AddressSanitizer + UBSan | memory and undefined-behaviour checks |
| `ci` | GCC 16, RelWithDebInfo, warnings as errors | CI |

Executable names and package versions are recorded in [Toolchain](#toolchain). Current module
and sanitizer validation is recorded in `cmake_template/docs/lab/toolchain.md`;
validate the supported presets when changing compiler versions.

Personal presets go in `CMakeUserPresets.json`, which is git-ignored. For example, to build
against a local checkout of the config repo (see Dependencies):

```json
{
  "version": 6,
  "configurePresets": [
    { "name": "dev-local", "inherits": "dev",
      "cacheVariables": { "FETCHCONTENT_SOURCE_DIR_CONFIG": "${sourceDir}/../config" } }
  ]
}
```

## Selecting apps by preset

`nom_app()` accepts an optional list: `BUILD_FOR dev ci`. Omit it, or use `BUILD_FOR any`, to
include the app in every preset. Use `BUILD_FOR complete` for an experiment that should only join
complete builds. The `complete` preset inherits the `dev` compiler settings and selects every app,
including apps listed only for other presets.

Apps outside the selected list remain available by target name, but are excluded from the
normal build and installation. The same selection applies to installation of their config
folders; a folder shared by multiple apps is installed if any of those apps is selected.
Dependencies of a requested target are still built as needed.

```bash
cmake --workflow --preset dev                         # configure, build selected targets, run tests
cmake --workflow --preset complete                         # same workflow with every app
cmake --build --preset dev --target cmake_template_sandbox_native_module  # one excluded app explicitly
```

`any` means every preset; `complete` names the preset that builds every app. For example,
`BUILD_FOR dev` includes the app in both `dev` and `complete`, so adding `complete` to that list
is optional. A normal build includes the selected apps and test executables; the workflow
also runs the tests.

Presets set the shared cache variable `NOM_BUILD_PRESET`. A custom preset inherits its parent's
selection unless it overrides that variable, so `dev-local` above still selects `dev` apps.
Without a preset it defaults to `dev`; set `-DNOM_BUILD_PRESET=release` or `complete` when needed.
This selects apps independently of `CMAKE_BUILD_TYPE`; `<PROJECT>_BUILD_APPS` still controls
whether the apps directory participates. For every app with Clang, use
`cmake --preset clang -DNOM_BUILD_PRESET=complete`, then build that preset.

## compile_commands.json

Every preset writes this compilation database (the exact compiler command for each file) into
its build directory. Clang tools can't read GCC's module flags, so clangd and clang-tidy use the
`clang` preset's database: `.clangd` points at `build/clang`, so configure and build that preset
once. In VS Code, use the clangd extension with `"clangd.path": "/usr/bin/clangd-19"` and
`"clangd.arguments": ["--experimental-modules-support"]`.

## The CMake kit

`cmake/kit/` is shared by every repo and owned by the template (change it in `cmake_template`, then
run `tools/sync_template.py` in the other repos). The top-level `CMakeLists.txt` includes
`cmake/kit/nom_kit.cmake`, which sets C++23 without compiler extensions and defines:

| Function | What it does |
|---|---|
| `nom_project_options()` | The project's options (below). Call it right after `project()`. |
| `nom_lib(<name> [STATIC \| SHARED] [SOURCES …] [HEADERS …] [MODULES …] [BASE_DIR <dir>] [PUBLIC_DEPS …] [PRIVATE_DEPS …])` | Library `<name>` plus alias `nom::<name>`. `MODULES` lists native interfaces and partitions; `SOURCES` lists implementation units and other compiled sources. File sets are rooted at `BASE_DIR` (default `core/`). Header-only macro or dependency adapters can be INTERFACE targets. |
| `nom_app(<name> SOURCES … [DEPS …] [BUILD_FOR …])` | Executable target `<project>_<name>`, binary `bin/<name>`; selects default build/install participation by preset; collects an adjacent `config/` directory. |
| `nom_c2test(<suite> SOURCES … [DEPS …])` | Catch2 executable `<project>_<suite>`, registered with CTest. Needs `nom_find_catch2()`. |
| `nom_library_usage_tests(<dir> [OPTIONS …])` | Integration tests: build and run a separate project using this library as an installed package and from source (see Tests). |
| `nom_install_package(TARGETS … [DEPENDENCIES …])` | Install rules and `<project>-config.cmake`, so consumers can `find_package(<project>)` and link `nom::<target>`. |
| `nom_require_submodule(<path>)` | Fails early, with the fix, when a submodule wasn't checked out. |
| `nom_find_catch2()` | The system Catch2 3, otherwise a pinned download; called at the project root when tests are enabled, before code directories. |
| `nom_find_metal()` | The retained Metal submodule as `nom::metal`, plus its separate `nom_metal` installed package. |

`nom_c2test` is specific to Catch2. Future test frameworks can have their own helpers
without changing `nom_lib` or `nom_app`.

The options, where `<PROJECT>` is the upper-case project name. Set them with `-D` on the command
line; the CMake files read the variables:

| Option | Variable | Default | Controls |
|---|---|---|---|
| `<PROJECT>_BUILD_TESTS` | `nom_build_tests` | ON when top level | `tests/` |
| `<PROJECT>_BUILD_APPS` | `nom_build_apps` | ON when top level | `apps/`, including the sandbox |
| `<PROJECT>_INSTALL` | `nom_install` | ON | install rules and the package config |

In a superbuild each repo brings its own copy of the kit; the first one loaded wins, and a
different version is reported as a warning.

Named modules are part of every Nomisma library build.

## Dependencies

- **Metal:** the shared foundation includes a submodule pinned to v2.1.4. Call
  `nom_find_metal()` before adding code directories and link `nom::metal` where its headers are
  needed. The helper uses only Metal's include directory, leaving its upstream CMake project
  unconfigured. With installation enabled, it installs a separate `nom_metal` package containing
  the headers and license. Libraries whose exported targets reference Metal list `nom_metal` in
  `nom_install_package(DEPENDENCIES …)`, including private dependencies of static libraries.
- **Our repos:** a git submodule in `external/<name>`, wired with
  `FetchContent_Declare(<name> SOURCE_DIR ${PROJECT_SOURCE_DIR}/external/<name>)` and
  `FetchContent_MakeAvailable(<name>)`. FetchContent keeps the first declaration of a name, so in a
  superbuild the outermost project must declare all shared pins before making any dependency
  available. Use consistent dependency names; version compatibility remains the system repo's
  responsibility. See the [FetchContent documentation](https://cmake.org/cmake/help/latest/module/FetchContent.html).
- **Third-party code:** a submodule pinned to a release tag, handled case by case.
  - nlohmann_json: its own CMake project works as a subproject, so it is used as is (see
    cmake_template's top-level `CMakeLists.txt`). `JSON_Install` follows our install option, so an
    installed package brings nlohmann with it.
  - Header-only libraries whose CMake project doesn't suit a subproject are used through
    their include directory only; their CMake project is never run.
- **System libraries** (Boost, OpenSSL, later): `find_package` only.
- **Catch2:** `nom_find_catch2()`.
- **Co-developing two repos:** set `FETCHCONTENT_SOURCE_DIR_<NAME>` (upper-case name) to a local
  checkout, in `CMakeUserPresets.json` as above. No submodule bump is needed until you commit.
- **Moving a pin:**
  ```bash
  git -C external/nlohmann_json fetch --depth 1 origin tag v3.12.1
  git -C external/nlohmann_json checkout v3.12.1
  git add external/nlohmann_json
  ```

Adding one: [howto.md](howto.md#a-dependency).

## App configuration collection

When an app directory contains `config/`, `nom_app()` stages its contents at
`build/<preset>/config/<app-directory>/` whenever the app builds. Multiple executables declared
in the same directory share one collection target, `<project>_copy_<app-directory>_config`.
The staged folder is refreshed on each build, so deleted source files disappear as well. With
`<PROJECT>_INSTALL=ON` and the app selected for the current preset, the executable installs to `<prefix>/bin/` and the collected files to
`<prefix>/config/<app-directory>/`. Build before installing so the collected files are current.
App directory names must be unique within a combined build because they share `build/config/`.
This step copies config files; it does not generate or load runtime configuration. See the
[app recipe](howto.md#an-app).

## Modules

Nomisma libraries define their C++ APIs in native named modules. The primary interface is
`core/<repo>/<repo>.cppm`, declaring `export module nom.<repo>;`. Larger APIs can split into
interface partitions and re-export them from the primary interface. Template definitions live
in interfaces or partitions; compiled definitions live in `.cpp` implementation units declaring
`module nom.<repo>;`. Apps and tests use `import nom.<repo>;`.

Use `MODULES` in `nom_lib()` to declare interfaces and partitions, including for libraries
consisting entirely of templates. The [module recipe](howto.md#a-module) shows the CMake and
source layout.

Headers still have specific roles at the boundaries:

- Macros cannot be exported. Keep them in ordinary headers and include them before imports;
  Catch2 tests follow the same rule for their assertion macros.
- Include the standard-library headers each file uses (for example `<string>` to compare
  `std::string`s). A module's global module fragment does not make those declarations visible
  to importers. `import std;` needs separate toolchain validation.
- Third-party libraries without suitable module support can be included in a global module
  fragment, wrapped behind a module API, or used through headers by consumers that need them.
  Choose the boundary for the dependency and test it on the supported compilers. Keep our
  public declarations in named modules.
- Prefer keeping a dependency private when its types are not part of the API. The example's
  settings implementation uses nlohmann headers privately, while the module exports settings
  values and parsing/serialization functions. Current third-party integration findings are in
  `cmake_template/docs/lab/third_party_in_modules.md`.

In module units, put includes in the global module fragment (`module;` followed by the includes),
before the named module declaration. In ordinary sources, put includes before imports.
Installed packages carry module interface and partition sources along with any macro headers;
consumers build their own compiled module interfaces (BMIs), which are specific to the compiler
and its flags. Package consumption is tested with the same compiler as the package build;
cross-toolchain binary compatibility is not implied.

## Tests

- `tests/unit/<suite>/` or inline `<code dir>/tests/<suite>/`: Catch2 unit tests, created with
  `nom_c2test()` and labeled `unit`. The root enables testing and finds Catch2 before processing
  `core/` and `apps/`, when `nom_build_tests` is enabled. Suites import the library's primary
  module; there is one path through the public API.
- `tests/integration/`: checks involving project boundaries or installation, labeled `integration`.
  `app_presets/` verifies app build/install selection; `library_usage/` is a separate CMake project
  that compiles, links and runs against this library.
  `nom_library_usage_tests()` installs the main project into
  `build/<preset>/tests/integration/library_usage/install`, then builds and runs the test project
  against that package with `find_package` (`<project>_library_usage_package`), and from source
  through `FetchContent` (`<project>_library_usage_source`). Both modes compile the same importing
  consumer, including rebuilding installed module interfaces in package mode.

```bash
ctest --preset dev                   # all tests
ctest --preset dev -L unit           # unit tests only
ctest --preset dev -L integration    # integration tests, including required installation
```

## Install and use

```bash
cmake --install build/release --prefix /opt/nomisma
```

```cmake
find_package(<project> 0.1 CONFIG REQUIRED)       # with CMAKE_PREFIX_PATH=/opt/nomisma
target_link_libraries(app PRIVATE nom::<project>)
```

The consumer uses `import nom.<project>;` and the supported module-capable compiler, CMake and
generator listed in [Toolchain](#toolchain).

## Versioning

Every repo follows Semantic Versioning (`MAJOR.MINOR.PATCH`) from its first commit, starting at
`0.1.0`: MAJOR for incompatible API changes, MINOR for compatible additions, PATCH for fixes.
While MAJOR is 0 any release may break the API, so an installed `0.y` package only satisfies
requests for the same `0.y`. The version lives only in `project()`, and each release is an
annotated tag `vX.Y.Z` on `master`.

To release `x.y.z`:

1. `CMakeLists.txt`: set `VERSION x.y.z` in `project()`.
2. `CHANGELOG.md`: rename the `[Unreleased]` section to `[x.y.z] - YYYY-MM-DD`, and start a new,
   empty `[Unreleased]` above it.
3. Commit ("Release x.y.z") and merge to `master`.
4. Tag that commit on `master` and push the tag:
   ```bash
   git switch master && git pull
   python3 tools/check_version.py vx.y.z     # the check CI runs on the tag
   git tag -a vx.y.z -m "Release x.y.z"
   git push origin vx.y.z
   ```

## Checks and CI

| Check | Command |
|---|---|
| Python environment | `python3 tools/check_python.py` |
| SPDX headers | `python3 tools/check_headers.py` |
| Formatting | `tools/check_format.sh` (`--fix` to reformat) |
| Naming | `tools/check_naming.sh` (builds `clang` with `NOM_BUILD_PRESET=complete` to cover every app) |
| Release tag | `python3 tools/check_version.py <tag>` |

GitHub Actions (`.github/workflows/ci.yml`) runs the `ci` and `clang` workflows and the first three
checks on pushes to `master`, pull requests, manual runs, and `v*` tags. The version check runs
only on `v*` tags. Build and quality checks run in the CI
image `ghcr.io/<owner>/ci`, which cmake_template builds from `docker/ci/Dockerfile`.
