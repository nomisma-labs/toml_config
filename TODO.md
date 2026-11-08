# Implementation status and TODO

This port is **DOC-REVIEW-PENDING**. The documentation defines the target contract;
it does not describe completed generator, mapping, or loader work. The reference
is the `json_config` checkout at `d2db3130349861f88236ac1b00cc767cbc6e3b91`.
Its existing convenience proposals remain follow-up work, not port requirements.

## Implementation status

- Template preparation: synchronized template-owned files from `cmake_template`
  v0.6.0 to v0.13.0 (`ccd09413e6a6421dd1b6b97873c1be11bc44e06e`). The
  official sync worker ran in a clean disposable clone, and only its template-owned
  outputs and `.template_ref` were copied into this checkout. The upstream URL is
  retained; no repository commit was created. The local release tag matches the
  published tag. Repository-owned source/CMake paths and target references are
  adapted for the synchronized kit, and the unused Metal dependency was removed.
  These changes do not implement the new API.
- Shared Bash tools: `tools/toml_config/config_path.sh` is an unchanged copy of
  `json_config`'s script; its commands use the same `NOM_CONFIG_DIR` convention.
- Documentation: the eight framework guides, repository/docs/tool indexes,
  three example READMEs, consumer README, language fixtures, and expected outputs
  mirror the JSON framework's structure. Commands for planned tools and applications
  are acceptance criteria until implementation is complete.
- Implementation: the target Python tools, CMake generation API, common-type
  adoption, mapping macros, runtime loader, and example C++ applications are pending.
  Existing code/tests are retained for preparation validation. Passing those tests
  does not demonstrate conformance to the new documentation.

## Review sequence

1. **Documentation review.** Review [tcfg](docs/toml_config/tcfg.md),
   [TOML/C++ mapping](docs/toml_config/toml_cpp_mapping.md), and
   [application integration](docs/toml_config/app_config_binding.md), then the other
   guides. Correct inconsistencies before implementing the new framework.
2. **Implementation, after review.** Port the Python engine/CLI/build utility,
   CMake helpers, shared `base` types and toml11 mapping, locator/loader, examples,
   and source/package tests to the documented interfaces. Retire superseded code,
   packaging, unused dependencies, and tests rather than maintaining parallel APIs.
3. **Implementation review.** Stop again with validation evidence. Further review
   may require changes to both the contract and the implementation.

### TOML choices for the documentation review

| Area | Proposed contract |
|---|---|
| Source naming | `<app>_tcfg.toml`; outputs `<app>.toml` by default |
| Sections | Ordered `[[sections]]` with `[sections.tcfg]` metadata; a root `[tcfg]` table permits the single-section shorthand |
| Composition | The same metadata, single-parent inheritance, ordered data imports, recursive table merge, replacement and deletion rules |
| Fragment addresses | RFC 6901 token syntax over TOML tables/arrays; no TOML-to-JSON data conversion |
| Optional values | Missing keys preserve C++ initializers; empty optionals serialize by omission; no null sentinel |
| Mapping | `NOM_TCONFIG` / `NOM_TCONFIG_ENUM` remain beside the type; an adapter bridges in-place conversion to native toml11 facilities |
| Numbers and time | Signed 64-bit TOML integer boundary; finite checked C++ doubles; native temporal values use the shared profile and explicit domain mapping |
| Tools | `tcfg.py`, `tcfggen.py`, `tcfg_build.py`; Python 3.11+ standard library; `--list` retains JSON machine metadata |
| Runtime/build conventions | `nom::tcfg`, `NOM_CONFIG`, `NOM_CONFIG_DIR`, `NOM_CONFIG_KEY`, `config`, `clean_config`, and the same CLI/check modes |

The optional-value policy is confirmed: absence retains an initialized optional,
which is empty by default. The remaining design choices await the user's review.

### Documentation and preparation validation

- `./bootstrap.sh complete`: passed all 8 current tests (5 integration, 3 unit),
  plus Python, SPDX, formatting, and dependency checks. This validates preparation,
  not the pending API port. Evidence: `build/bootstrap/run.0V8s7A/`.
- All template-owned files and `.template_ref` match v0.13.0 exactly.
- All relocated C++ sources/headers remain byte-identical to their pre-sync contents.
- The copied Bash script is byte-identical to its source; set, add, deduplication,
  print, clear, spaces in paths, and invalid-input behavior passed smoke checks.
- 50 TOML fixtures and 7 TOML documentation snippets parse successfully.
- 13 source examples were translated temporarily to the JSON resolver's input form;
  all 22 stored expected outputs match its common composition semantics. This checks
  the documentation examples without implementing a new TOML resolver.
- All 8 guide counterparts retain the reference's section headings in order;
  local links/anchors and whitespace checks pass.

### Implementation acceptance coverage

- Parse and compare every documented example; exercise section ordering, metadata,
  selected ancestors, missing donors, literal imports, pointers, replacement,
  deletion, generation/runtime placeholders, and output-name inheritance.
- Check the TOML profile in both parsers, including integer limits, mixed arrays,
  temporal categories/precision, nonfinite floats, empty values, and Unicode.
- Exercise CLI listing, discovery, output containment, publication failures,
  unchanged files, CMake ownership records, cleanup, tests, and installation.
- Exercise required/defaulted/optional members, parent-initialized nested defaults,
  enums, custom converters, containers, numeric checks, path diagnostics, runtime
  substitution, ordered override probes, hard-wired loading, and check output.
- Validate all three applications and source/installed-package consumers with GCC
  and Clang; run a fresh complete build and the repository checks.

The following topics mirror the JSON framework's review and follow-up list.
Source review, initialization simplification, and a user-local layer remain future
work. Items already included in the target CLI contract are baseline port work;
no new convenience API or user-local layer is approved by this port.

## 1. Review key source files and workflows

Review each significant script and C++ source, together with its tests and the
workflows it supports:

- [ ] `tools/toml_config/tcfg.py`
- [ ] `tools/toml_config/tcfggen.py`
- [ ] `tools/toml_config/tcfg_build.py`
- [ ] `src/toml_config/config_loader.cpp`
- [ ] `src/toml_config/config_locator.cpp`
- [ ] `src/toml_config/config_options.cpp` — revisit enum stringification.
- [ ] `src/toml_config/config_runtime.cppm` — review whether the name reflects its responsibilities.
- [ ] Work through the build, usage, and test instructions in every example README:
  [config_workflow_example](apps/config_workflow_example/README.md),
  [config_args_example](apps/config_args_example/README.md), and
  [md_capture](apps/md_capture/README.md).

## 2. Revisit application initialization

Do this after the source review. Cover command-line arguments, config discovery,
and loading. The goal is to make the common case concise while allowing
applications to define and validate their own arguments.

### Target behavior and constraints to preserve

- `main()` owns initialization, services, error reporting, and exit codes. Prefer
  meaningful startup code there over a `run_app()` wrapper.
- `parse_config_arguments()` extracts framework options and preserves the remaining
  arguments. In `config_args_example`, the application parses those with
  Boost.Program_options and handles help before calling `load_config<Config>(options)`.
- Loading resolves the config source, reads TOML (or uses hard-wired defaults),
  substitutes runtime variables, applies command-line overrides, maps to C++, and
  validates. The library returns the load result or reports errors to its caller.
- Application help and argument validation happen before config I/O. After
  successful loading, `--check-config` exits before application services start.

See [application integration](docs/toml_config/app_config_binding.md#application-integration)
and the working examples:
[config_workflow_example](apps/config_workflow_example/README.md) and
[config_args_example](apps/config_args_example/README.md). Keep detailed usage in
their READMEs and link to it contextually from other docs.

### Proposal and open questions

- [ ] Consider `load_config<Config>(argc, argv, key)` for config-only applications,
  reusing the existing implementation. Keep separate parsing and loading interfaces
  available for more elaborate applications.
- [ ] Decide the overload's return shape and handling of unexpected arguments.
- [ ] Expose standard config help alongside application help with `print_config_help()`;
  the parser returns the help request in `.help`.
- [ ] Simplify the startup workflow when combining framework and application arguments,
  especially `--help` handling and passing help state between the two parsers.
  Revisit the TODO comment in `apps/config_args_example/main.cpp`,
  which calls out the complexity of this workflow.
- [ ] Decide how much diagnostic reporting belongs in the example.

## 3. Add a user-local config layer

This is a convenience feature to design first. **User-local config layer** is the
working name: it describes the additional source of settings, while "override"
describes its effect. Naming is not settled.

The initial idea is to keep local, possibly unversioned TOML files that the
generator imports and automatically applies to any generated config as its final
TOML merge. Unlike a standalone development config, which is a base config that
does not require generation, this layer would customize generated configs without
editing each one.

- [ ] Agree on the name: **user-local config layer**, **user config layer**, or
  **local config overrides**.
- [ ] Resolve when the layer is applied. The requested precedence is runtime
  `run-var` substitution, then the user-local layer, then command-line overrides.
  The target generation workflow preserves `{tcfg:run-var NAME}` for substitution by the
  C++ loader. A final generation-time merge would therefore happen before
  `run-var` substitution. Decide how to reconcile these two parts of the proposal.
- [ ] Define file naming, discovery, and scope: how local files are selected and
  how their automatic application across generated configs is controlled.
- [ ] Define merge behavior, ordering between multiple local files, and handling
  of missing or invalid local files.

## 4. Improve command-line usability

- [ ] Make `--help` (`-h`) print more explanatory help, generated by
  `boost::program_options`, with descriptions of the available options and their usage.
- [ ] Add short option aliases, including `-c` for `--config` and `-k` for
  `--check-config`, and show both forms in the generated help.
- [ ] Add `full`, `view`, and `silent` modes to `--check-config` with the following output:

| Mode | Output |
|---|---|
| `full` (default) | Actual lookup inputs and candidates, selected source/path or fallback, then final TOML. |
| `view` | Only the final configuration. |
| `silent` | Just `OK`. |

In `full` and `view` modes, the final normalized configuration is serialized from
the validated C++ value after runtime substitutions and command-line overrides.
It includes C++ defaults; absent optional members are omitted.
All three example applications use the reporting helpers; source and installed
consumers exercise the public API. See
[check output](docs/toml_config/app_config_binding.md#check-output) for usage and lookup details.
