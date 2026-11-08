# AGENTS.md

<!-- repo-description:begin -->
This is **toml_config**, Nomisma's TOML application configuration framework.
Its guides live under `docs/toml_config/`; `TODO.md` records implementation review
and validation status. The C++ module is `nom.toml_config`, with common config
types from `base`, a precompiled toml11 dependency, and Boost.Program_options.
Python tooling supplies `tcfggen.py`, section resolution, and CMake generation.
<!-- repo-description:end -->

Read and follow the rules every Nomisma repo shares: @docs/kit/agents.md

Rules for this repo alone follow below.

- Keep the user-facing framework, tools, examples, and documentation closely aligned
  with `json_config`, adapting format-dependent behavior to TOML. Projects choose
  one framework; coexistence is not a design requirement.
- The documentation review is complete. Implement and validate in stages, then
  stop for one implementation review. Flag issues requiring a contract decision
  during implementation.
- Example applications must have their own `README.md` with build, usage, and test
  instructions. Keep example-specific details there and use short repository links.
- Generator tooling requires Python 3.11+ (`tomllib`), above the kit's minimum.
- Describe the framework on its own terms in source comments and user guides.
