# TOML application config library

Start with the [introduction](intro.md) for the basic config workflow, C++ application
integration, and structured configs. The guides below cover each part in more detail.

**tcfg** is TOML based app config language described in [tcfg.md](tcfg.md)

TOML app config framework has 4 components supporting various config related workflows:

1. [Python config generator: tcfggen.py](config_generation.md);
1. [Build system integration](build_system_integration.md) : config collector and generator integration
1. [C++ config loader and app config resolution](app_config_binding.md);
1. [TOML/C++ mapping](toml_cpp_mapping.md);

Implementation status and open design decisions are recorded in [TODO.md](../../TODO.md).

## Implementation notes

- [Config types](https://github.com/nomisma-labs/base/blob/master/docs/base/config_types.md) — common types and their CMake integration, owned by `base`.
- [toml11 implementation](toml11_implementation.md) — TOML mapping and conversion details.
- [Config types and serialization dependencies](https://github.com/nomisma-labs/base/blob/master/docs/base/config_types_design.md) — separation of common C++ config data from TOML mapping.

## Learning by example

Each example includes its own build, usage, and test instructions.

- [md_capture](../../apps/md_capture/README.md) — the comprehensive configuration from [tcfg.md](tcfg.md#complete-example).
- [config_workflow_example](../../apps/config_workflow_example/README.md) — the full build, generation, loading, testing, packaging, and installation workflow.
- [config_args_example](../../apps/config_args_example/README.md) — application arguments alongside config arguments, using Boost.Program_options.
- [Consumer tests](../../tests/integration/library_usage/README.md) — using the library from source and as an installed C++ package.
