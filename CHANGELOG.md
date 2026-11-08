# Changelog

Notable changes to this repo. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org); how to release:
[docs/kit/build.md](docs/kit/build.md#versioning).

## [Unreleased]

- Add the tcfg section language and `tcfggen.py`, with inheritance, literal imports,
  fragment pointers, merge/delete/override instructions, and generation/runtime variables.
- Add TOML 1.0 value validation shared by the Python tooling and C++ runtime,
  preserving date/time categories and normalizing fractional seconds to microseconds.
- Add `nom.toml_config`, `NOM_TCONFIG`, and `NOM_TCONFIG_ENUM` mappings with common
  `base` config types, checked numbers, nested defaults, optional members, containers,
  custom converters, and nested error pointers.
- Add application config discovery, command-line parsing, runtime substitution,
  ordered overrides, root validation, and full/view/silent config checks.
- Add CMake collection/generation/test/install workflows and shell config-path helpers.
- Add three runnable examples and source/installed consumer tests, including
  compile-time rejection of unsupported config members.
- Synchronize the shared build kit with `cmake_template v0.13.0`.
