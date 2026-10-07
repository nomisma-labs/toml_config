# AGENTS.md

<!-- repo-description:begin -->
This is **toml_config**, the application configuration component for Nomisma projects.
It provides Python tcfg generation, C++ TOML discovery and typed application initialization,
and optional generation for CMake. See `docs/tcfg.md` for the language contract
and `docs/guide.md` for usage. Metal v2.1.4 remains a foundation dependency; toml11 v4.4.0
provides TOML parsing and macro bindings through a compiled dependency adapter.
<!-- repo-description:end -->

Read and follow the rules every Nomisma repo shares: @docs/kit/agents.md

Rules for this repo alone follow below.

## This repo

- `core/toml_config/`: the `nom.toml_config` module, which locates, parses and binds ordinary
  TOML; `util/` is a private Linux OS boundary ([docs/os_utilities.md](docs/os_utilities.md)).
- `python/toml_config/`: the tcfg generator, the only tcfg implementation. `cfggen.py` runs it
  without installing the package, and `cmake/tcfg.cmake` runs it from CMake. Its language cases
  are in `tests/conformance/`.
- The generator and its tests need Python 3.11+ (`tomllib`), above the kit's 3.10 minimum.
- The generator ships as a pure-Python setuptools package (`pyproject.toml`, `setup.py`,
  `MANIFEST.in`) that reads its version from `project()`. The kit's native wheel packaging
  (`nom_python_module()`, scikit-build-core, `TOML_CONFIG_BUILD_PYTHON`) is for C++ extensions
  and doesn't apply here; keep the setuptools package.
