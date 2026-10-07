# Changelog

Notable changes to this repo. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org); how to release:
[docs/build.md](docs/build.md#versioning).

## [Unreleased]

- Remove C++ tcfg interpretation and direct loading; C++ locates, parses, and binds
  ordinary TOML produced by the Python generator or written directly.
- Isolate executable discovery behind a private Linux OS utility and defer it
  until directory-based configuration discovery; remove unsupported Windows code.
- Add the standalone `cfggen.py` launcher, shared by source and installed CMake generation.
- Add tcfg 1 layered TOML configuration with ordered inheritance, fragment imports,
  subtree replacement/deletion, and explicit environment bindings.
- Add a Python tcfg generator with language conformance fixtures.
- Add `nom.toml_config` application discovery and typed initialization
  using toml11 v4.4.0 mappings.
- Add optional CMake generation with transitive dependency tracking, installed
  tooling, a sample application, and author/integration documentation.
