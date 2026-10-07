# OS utilities and future shared core

Executable discovery currently lives in the private header
`core/toml_config/util/os.h` and the Linux implementation `util/os_linux.cpp`.
It is compiled into toml_config, but is not part of the exported configuration
module or installed headers. The header is an internal OS boundary; the public
library API continues to use the named module.

The interface is deliberately independent of configuration:

```cpp
std::filesystem::path current_executable(std::error_code& failure);
```

It returns the absolute path to the running executable, resolving launch
symlinks. An OS lookup failure returns an empty path and sets the error code.
The Linux implementation canonicalizes `/proc/self/exe`. It neither guesses from
`argv[0]` nor searches `PATH`. Filesystem allocation failures retain normal C++
exception behavior; the function is not `noexcept`.

The utility uses only standard-library types. It does not parse arguments, read
configuration, choose search directories, throw `nom::config::error`, or log.
The configuration adapter translates OS errors into configuration diagnostics.

`application_options.executable` supplies an explicit executable location when
needed. Otherwise `locate_config` calls the utility to find ordinary TOML files
only after checking the explicit file and `TCFG_CONFIG`. Argument parsing and
help do no discovery.
This also allows an embedding application to supply its own installation context.

CMake selects the platform source through the existing `nom_lib(SOURCES ...)`
interface. Only Linux has a backend today; unsupported systems fail configuration
explicitly. A future macOS backend will implement the same interface and must
pass the same behavior tests, including relocated installations, symlink
launches, and launches through `PATH`. Adding a platform also requires support
and validation in the shared build framework.

## Promotion to common core

1. When a shared core utility library is established, move this interface,
   implementation, and OS unit test into its `core/util/` area. Give it a neutral
   namespace such as `nom::os` and expose its public API through that library's
   named module. Keep OS headers and platform details private.
2. Keep that utility target independent of toml_config, logging, assembly, and
   application policy. Its required runtime types remain standard-library types.
3. Declare the shared core dependency using cmake_template's existing dependency
   and target helpers. Any new general build mechanism belongs in cmake_template;
   platform source declarations belong to the utility library.
4. Change toml_config's internal adapter to call the shared utility, remove its
   local copy, and retain configuration-specific search rules and error messages
   here. Application-facing configuration APIs need no change for that move.
5. Move other users to the shared utility as needed. Keep the utility tests with
   core and the configuration discovery/integration tests with toml_config.

This avoids introducing a new foundation dependency before it has a home, while
keeping the current implementation small enough to move without a redesign.
