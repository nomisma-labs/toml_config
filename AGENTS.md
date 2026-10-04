# AGENTS.md

<!-- repo-description:begin -->
This is **cmake_template**: the template every Nomisma C++ repo is created from, and the lab
where build-system and C++ features (modules first) are tried before real repos rely on them.
Its example code (library `example`, app `hello`, their tests and the library usage test project) shows
every mechanism working; `tools/init_project.py` removes it from new repos.
<!-- repo-description:end -->

## Build and test

- Run `./bootstrap.sh` for fresh validation builds, tests and quality checks, or `./bootstrap.sh <preset>` for one preset.
  Presets are discovered through CMake; the default selects all matching configure/build/test names except `release`.
  It clears selected build directories and previous bootstrap logs; `--help` lists the discovered presets.
  Python 3.10+ is required; `tools/check_python.py` validates syntax and imports before builds.
- First checkout: `git submodule update --init --recursive`.
- Configure once with `cmake --preset dev`; then, in `build/dev`, `ninja` builds and
  `ctest --output-on-failure` tests. Binaries land in `build/<preset>/bin/`.
- `cmake --workflow --preset dev` does all three. Other presets: `complete`, `clang`, `asan`, `release`, `ci`.
  `complete` is Debug with every app; `nom_app(... BUILD_FOR dev ci)` limits normal build/install participation.
  Details: [docs/build.md](docs/build.md).

## Layout

- `core/<repo>/`: the library. Its public API is the named module `nom.<repo>`; module
  interfaces and partitions use `.cppm`, implementation units use `.cpp`.
- `apps/<app>/`: executables; optional `config/` is collected into `build/<preset>/config/<app>/` and installed with the app.
- `apps/sandbox/`: experiments, normally `BUILD_FOR complete`; also buildable explicitly in other presets.
- `tests/unit/<suite>/` or inline `<code dir>/tests/<suite>/`: Catch2 unit tests, labeled `unit`.
  Catch2 is found at the project root when tests are enabled, before code directories.
- `tests/integration/`: library usage and installation checks, labeled `integration`.
- `external/`: git submodules (third-party code pinned to release tags, and our own repos).
  Metal v2.1.4 is retained as a foundation dependency; `nom_find_metal()` provides `nom::metal`.
- `cmake/kit/`: the shared CMake kit. `tools/`: checks and repo scripts. `docs/`: documentation.

## Adding code

Follow [docs/howto.md](docs/howto.md): a library, a module, an app, a unit test suite, library usage integration tests,
a dependency, an experiment.

## Rules

- Follow [docs/conventions.md](docs/conventions.md): `snake_case` everywhere, `PascalCase` template
  parameters, UPPER_CASE only for macros. `tools/check_naming.sh` enforces the naming.
- C++ test sources use `*_test.cxx` in both unit and integration tests; regular sources use `.cpp`.
- Every source file starts with the SPDX header; `python3 tools/check_headers.py` checks it.
- Format with `tools/check_format.sh --fix`.
- Add targets with the kit (`nom_lib`, `nom_app`, `nom_c2test`), not raw CMake.
- Link `nom::metal` where Metal headers are needed. For a public dependency, list `nom_metal`
  in `nom_install_package(DEPENDENCIES …)`; the kit installs its headers and license separately.
- Template-owned paths (`bootstrap.sh`, `cmake/kit/`, `tools/`, `docs/build.md`, `docs/conventions.md`,
  `docs/howto.md`, `docs/new_repo.md`, `.clang-format`, `.clang-tidy`, `.clangd`, `.editorconfig`,
  `.github/workflows/ci.yml`) change only in cmake_template and reach other repos through
  `tools/sync_template.py`. Don't edit them in a derived repo.
- Define our C++ library APIs in named modules; apps and tests import them.
  Keep macros in headers, and use wrappers or headers at third-party boundaries.
  Put `#include`s before `import`s and include the std
  headers you use yourself ([docs/build.md](docs/build.md#modules)).
- The version lives only in `project()`; releases follow [docs/build.md](docs/build.md#versioning).
- When you change behaviour that a doc describes, update the doc in the same change.
- Lab work (template only): experiments go in `apps/sandbox/`, findings in `docs/lab/`. <!-- template-only -->
- Template only: end a line that new repos must not get with a `template-only` comment, or wrap a block in `template-only:begin`/`template-only:end` comments; `tools/init_project.py` removes them. Template-owned files carry none. <!-- template-only -->
