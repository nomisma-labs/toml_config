# cmake_template

<!-- repo-description:begin -->
The template every Nomisma C++ repo is created from, and the lab where build-system and C++
features (modules first) are tried before real repos rely on them.
<!-- repo-description:end -->

Nomisma libraries define their C++ APIs in named modules from the start.
Headers remain for macros and third-party libraries that need them;
[the module rules](docs/build.md#modules) describe those boundaries.

Metal v2.1.4 is part of the shared foundation. `nom_find_metal()` exposes its headers through
`nom::metal`; generated repositories retain the pinned submodule. Installed consumers use the
`nom_metal` package, which includes those headers and their license.

## Bootstrap

After installing the tools listed in [docs/build.md](docs/build.md#toolchain), run:

```bash
./bootstrap.sh           # standard validation presets
./bootstrap.sh release   # one preset only
./bootstrap.sh --help    # usage and available presets
```

Bootstrap discovers enabled presets through CMake, including included files and
`CMakeUserPresets.json`. It uses matching configure/build/test names and the repo's
`build/<preset>/` layout. With no argument, it validates every discovered preset except
`release`; pass a name to select one preset explicitly. Adding a paired preset to CMake
automatically makes it available here. Each run clears selected build directories and previous
bootstrap logs, initializes missing submodules, and configures/builds/tests from scratch.
Unselected build directories are preserved.

Python compatibility/imports, SPDX headers and formatting run every time. The Python check
verifies version 3.10 or newer, script syntax, and imported modules; no pip packages are
currently required. Naming is included when `clang` is selected. Tests include unit suites and
integration checks for library usage from source and through an installed package. Every step reports `PASS`, `FAIL`
or `SKIP`, followed by a summary and next steps. Failures return a nonzero exit code;
independent checks continue where possible. Only the current run's logs are kept under
`build/bootstrap/`. Use the commands in **Build** below for incremental work.

An empty generated repository reports its tests as skipped until you add them. Submodules at
unexpected commits are reported for you to resolve; bootstrap does not reset them. Dependency
initialization or CMake's dependency fallback may need network access. Build concurrency defaults
to the available CPU core count minus one, with a minimum of one job. Use
`CMAKE_BUILD_PARALLEL_LEVEL=4 ./bootstrap.sh` to override it. The script also works when invoked
from another directory.

## Manual build

```bash
git submodule update --init --recursive   # once, after cloning
cmake --preset dev                        # once: configure into build/dev
cd build/dev
ninja                                     # build; reruns cmake itself when a CMakeLists.txt changes
ctest --output-on-failure                 # test
```

Other presets (`complete`, `clang`, `asan`, `release`, `ci`) work the same way in `build/<preset>`, and
`cmake --workflow --preset dev` configures, builds and tests in one command. Apps land in
`build/<preset>/bin/`. Use `cmake --workflow --preset complete` for a Debug build including every
app and experiment. Apps can limit their default build/install with `BUILD_FOR dev ci`; omitting
`BUILD_FOR` includes them everywhere. More: [docs/build.md](docs/build.md).

## Docs

Agents start at [AGENTS.md](AGENTS.md), people at [docs/](docs/README.md). Adding a library, an
app, tests or a dependency: [docs/howto.md](docs/howto.md). Releases: [CHANGELOG.md](CHANGELOG.md).

<!-- template-only:begin -->
## A new repo from the template

On GitHub, "Use this template" (or `gh repo create --template`), then
`python3 tools/init_project.py <name>`, which removes the example code and the lab. See
[docs/new_repo.md](docs/new_repo.md).

## What's inside

The CMake project and installed package are named `cmake_template`. The illustrative library
is named `example` (`nom::example`); its code and tests exercise the build system.

- **Example library `example`** (`core/example/`): the native named module `nom.example`, with
  interface partitions, a template, compiled implementation units, a config-like type, and a
  macro header. JSON parsing uses a third-party header behind the module API.
- **Apps:** `hello` through `import nom.example;`
  (`build/dev/bin/hello build/dev/config/hello/settings.json`), and lab experiments in `apps/sandbox/`.
- **Tests:** `tests/unit/` holds Catch2 suites that import the module; `tests/integration/`
  checks library usage from a separate project and config installation. Use `ctest --preset dev -L unit` or `ctest --preset dev -L integration` to select a group.
- **Build system:** presets, the CMake kit (`cmake/kit/`), dependencies as submodules in `external/`.
- **Checks and CI:** SPDX headers, formatting, naming and the release-tag check, on a shared CI
  image. Validate a newly initialized repo locally with `./bootstrap.sh`.
- **Lab:** [docs/lab/](docs/lab/README.md).
<!-- template-only:end -->
