# TOML framework implementation

The documentation and implementation ports are complete. The implementation is
ready for the requested review; review feedback is the next step.

## Completed stages

1. **Python resolution and generation.** Added `tcfg.py`, `toml_codec.py`, and
   `tcfggen.py`, covering sections, inheritance, literal imports, fragment pointers,
   merge/delete/override instructions, placeholders, TOML values, discovery,
   metadata listing, output containment, and atomic per-file publication.
2. **Build integration.** Added `tcfg_build.py`, `nom_tcfg_generate`, and
   `nom_tcfg_test`, with ownership/success records, collection/generation targets,
   cleanup, installation checks, and stale-output handling.
3. **C++ mapping.** Added the `base` dependency and toml11 adapters for
   `NOM_TCONFIG`, `NOM_TCONFIG_ENUM`, checked numbers, nested defaults, optionals,
   containers, custom converters, and nested diagnostic pointers. Native
   conversion hooks work for enums; in-place conversion preserves parent defaults.
4. **Runtime and examples.** Added config location, arguments, substitution,
   ordered overrides, typed loading, root validation, check output, and all three
   applications. Removed the superseded generator package, application API,
   example, and fixtures.
5. **Verification and documentation.** Updated the guides to describe implemented
   behavior and completed GCC/Clang builds, source/package consumers, application
   CLI tests, generation/build tests, and repository checks.

## Review points retained

- `[[sections]]` is the multi-section envelope, with `[sections.tcfg]` metadata;
  a root `[tcfg]` table is the single-section shorthand. Review this naming later.
- Slash-separated config pointers address fragment imports and runtime `--set`
  targets. Both currently follow the documented escape and array-index rules.
- Missing optional keys preserve C++ initializers, normally an empty optional.
  Empty optionals serialize by omission and have no existing `--set` target.
  No null marker is introduced.
- `NOM_TCONFIG` uses toml11's expansion helper, supporting up to 32 member names
  per mapping. Enums support explicit aliases and reject unknown values.
- User-facing APIs, tools, conventions, and guide structure closely follow
  `json_config`. A project chooses one framework; coexistence is not required.
- JSON-framework follow-up proposals are outside this port.

## Preparation and reference

- Synchronized `cmake_template v0.13.0`; migrated source/CMake paths and removed
  unused Metal. `config_path.sh` remains byte-identical to the JSON helper.
- Ported eight guides, supporting READMEs, and TOML examples/expected outputs.
- Reference `json_config`: `d2db3130349861f88236ac1b00cc767cbc6e3b91`.
- Shared `base` dependency: `51dcfd4be7b59ed7147557d973e0363e2a4b23b7`.

## Validation evidence

Validated on 2026-11-08 with GCC 16, Clang 22, and Python 3.14.4:

- Fresh `./bootstrap.sh complete`: build, all 20 CTest entries, Python import/syntax,
  SPDX, formatting, and dependency checks passed.
- Fresh `./bootstrap.sh clang`: build, all 20 CTest entries, the same repository
  checks, and clang-tidy naming passed.
- Final GCC and Clang rebuilds and all 20 CTest entries passed after adding the
  move-only container serialization regression test; final formatting and naming
  checks also passed.
- The CTest entries include 50 Python engine/value tests, 43 generator CLI/publication
  tests, 25 CMake workflow tests, C++ mapping/runtime/locator/value-profile suites,
  all three application CLI suites, generated config checks, and source/installed
  consumers with unsupported-type compile-failure tests.
- Documentation local links, copied Bash helper identity, and `git diff --check`
  passed. No commit, tag, or publication is part of this review checkpoint.
