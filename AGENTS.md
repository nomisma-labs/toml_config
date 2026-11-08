# AGENTS.md

<!-- repo-description:begin -->
This is **toml_config**, Nomisma's TOML application configuration framework.
The target design is documented under `docs/toml_config/`; `TODO.md` records the
review gates and implementation status. The C++ module is `nom.toml_config`.
The checkout includes Python configuration generation and a toml11 compiled
adapter. The documented `tcfggen.py`, mapping, and runtime API port is pending
review; do not treat target documentation as evidence of implemented behavior.
<!-- repo-description:end -->

Read and follow the rules every Nomisma repo shares: @docs/kit/agents.md

Rules for this repo alone follow below.

- Keep the user-facing framework, tools, examples, and documentation closely aligned
  with `json_config`, adapting format-dependent behavior to TOML. Projects choose
  one framework; coexistence is not a design requirement.
- Complete documentation review before implementing the documented API port, then
  stop again for implementation review. Template preparation and the unchanged
  shared Bash helper copy are authorized preparation work.
- Example applications must have their own `README.md` with build, usage, and test
  instructions. Keep example-specific details there and use short repository links.
- Generator tooling requires Python 3.11+ (`tomllib`), above the kit's minimum.
- Describe the framework on its own terms in source comments and user guides.
