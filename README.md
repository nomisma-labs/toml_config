# toml_config

<!-- repo-description:begin -->
Application configuration for Nomisma projects. This repository starts from the shared
CMake template; configuration APIs and tooling will be developed here.
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
