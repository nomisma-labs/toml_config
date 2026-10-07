# CMake kit

The **kit** is the shared build framework for Nomisma repositories. It provides helpers for
declaring libraries, applications, tests and installable packages, backed by common dependency
and toolchain services. Include its entry point once, after `project()`:

```cmake
include(cmake/kit/nom_kit.cmake)
nom_project_options()
```

Include only `nom_kit.cmake`; it loads the files below in the required order.

| Location | Purpose |
|---|---|
| [api/](api/) | Helpers used in repository `CMakeLists.txt` files: project options, targets, tests, C++ installation and optional Python extensions. |
| [deps/](deps/) | Dependency services: submodule checks, Metal integration and Catch2 discovery. |
| [internal/](internal/) | Implementation details such as compiler warnings, runtime paths and Python library checks. |
| [templates/](templates/) | Templates used to generate installed CMake package metadata. Dependency-specific templates stay with their service in `deps/`. |
| [presets.json](presets.json) | The shared configure, build, test and workflow presets. Each repo's `CMakePresets.json` includes it and adds its own. |

For a library defined in `core/prices/CMakeLists.txt`:

```cmake
nom_lib(prices
    MODULES prices.cppm
    SOURCES prices.cpp)

if(nom_install)
    nom_install_package(TARGETS prices)
endif()
```

This defines the library and its `nom::prices` alias. `MODULES` lists C++ module interfaces;
`SOURCES` lists compiled implementation files. The install helper lets downstream C++ projects
use `find_package(<project> CONFIG REQUIRED)` and link `nom::prices`.

For an application in `apps/capture/CMakeLists.txt`:

```cmake
nom_app(capture SOURCES main.cpp DEPS nom::prices)
```

This creates `<project>_capture`, producing `bin/capture`. An adjacent `config/` directory is
collected and installed with the application. Add these folders through their parent's
`add_subdirectory()` calls, following the [recipes](../../docs/kit/howto.md).

Other common helpers are `nom_c2test()` for Catch2 tests, `nom_library_usage_tests()` for C++
source/install consumption checks, and `nom_python_module()` for optional Python extensions.
Dependency services such as `nom_find_metal()` and `nom_find_catch2()` are called before targets
that need them. Full signatures and options are in the [build guide](../../docs/kit/build.md#the-cmake-kit).

The kit is **template-owned**: update it in `cmake_template`, then use `tools/kit/sync_template.py`
in derived repos. Other CMake files directly under `cmake/` are repository declarations;
shared build mechanisms belong in the kit.
