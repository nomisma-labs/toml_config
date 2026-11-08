# Config generation

> **Documentation review draft — implementation pending.** This page defines the
> target contract. Commands and APIs below are implementation acceptance criteria,
> not claims that this checkout already supports them. See [status](../../TODO.md).

`tcfggen.py` produces application TOML from tcfg sources. It can run directly or
through the [build system](build_system_integration.md), using Python 3.11+ and
the standard library. `tomllib` reads TOML; a repository-owned deterministic writer
emits TOML 1.0 because the standard library has no TOML writer. No Python package
installation is needed for this tool. See [Python's tomllib reference](https://docs.python.org/3.11/library/tomllib.html).
The [tcfg definition](tcfg.md) owns the language rules.

## Inputs and outputs

The tool accepts either one source file or an input directory tree, such as the
collected config directory:

```text
config/<app>/<app>_tcfg.toml          source definition
config/<app>/*.toml                  app-owned donor files
genconfig/<section>/<gen_file>       generated application config
```

Discovery scans recursively for `*_tcfg.toml`, including files directly in the
input directory. The app name comes from the filename without `_tcfg.toml`;
parent directory names do not affect discovery.

The output filename follows `tcfg.gen_file`, its inheritance rules, and the
source-derived default. Section names are exact identifiers; they need not be
deployment environments. The generator does not invent a `base` section.

Only sections with `tcfg.generate = true` produce files; omission means `true`.
Suppressed sections can still supply inherited values and filenames. Selecting
a suppressed section explicitly for generation is an error. Selecting a child
resolves its ancestors without automatically writing their outputs.

Two results claiming the same output path are an error. Output section names and
filenames must stay within the output directory; absolute output paths and path
traversal are rejected. Input and output locations must be separate.
With `--input-dir`, the input and output directory trees must not overlap. With
`--source`, the output may be a build subdirectory beside the source, but neither
the source nor any imported donor may reside inside the output tree. These checks
also follow symbolic links. A destination that is already a directory, or conflicts
with another output's file/directory path, is an error.

## Command line

| Argument | Meaning |
|---|---|
| `--source FILE` | Read one tcfg file directly. |
| `--input-dir DIR` | Recursively discover `*_tcfg.toml` files under `DIR`. Mutually exclusive with `--source`. |
| `--app NAME` | Select exactly one `NAME_tcfg.toml` anywhere under `--input-dir`; otherwise process all discovered sources. |
| `--config NAME` | Select a section; repeat to select several. Requires `--source` or `--app`. Omission selects all generating sections. |
| `--output-dir DIR` | Required output root when generating files. |
| `--list` | Report app, section, resolved output filename, and `generate` flag as JSON without generating files. No output directory is required. |
| `--verbose` | Include source and output paths in diagnostics. |

Exactly one input mode is required. An unknown app or section, an ambiguous
`--app` match, or discovery that finds no tcfg files is an error. App selection
happens before reading source contents, so unrelated apps are not evaluated.
A source whose sections are all suppressed is valid and produces no files when
no explicit section selection is requested.

`--list` prints a JSON array with `app`, `section`, `gen_file`, and `generate`
fields. Discovered sources are sorted by app name, then path; sections retain
source order. In `--source` mode, the app name is the source basename without `_tcfg.toml` (or the
filename stem for another suffix). Listing a suppressed section explicitly is
allowed. This JSON is tool metadata only; source definitions and generated
application configs are TOML. It keeps the listing/build interface simple and
independent of TOML application values. Verbose messages and errors go to stderr, keeping stdout usable as JSON.

For one application:

```bash
python3 tools/toml_config/tcfggen.py --input-dir build/dev/config --app md_capture \
    --config prod --output-dir build/dev/genconfig
```

To generate directly from the [complete example](../../apps/md_capture/config/md_capture_tcfg.toml):

```bash
python3 tools/toml_config/tcfggen.py \
    --source apps/md_capture/config/md_capture_tcfg.toml \
    --config prod --output-dir build/dev/genconfig
```

Both examples select `prod/md_capture.toml`. Omitting `--config` in the second
command also generates the other enabled sections, including
`prod-liquidation/md_capture_liquidation.toml`. To process all collected apps,
omit both `--app` and `--config` from the first command.

## Resolution and errors

The generator checks metadata and inheritance for every section, then resolves
imports and instructions only for selected sections and their ancestors using
the merge rules in [tcfg.md](tcfg.md). Unrelated sections do not require their
donor files or generation variables to be available. `tcfg.name`, `tcfg.extend`,
and `tcfg.gen_file` are literal strings; they do not support placeholders.
Relative imports are resolved from the source file's directory. Imported ordinary
TOML stays literal during generation.
Fragment references use `file.toml:/pointer`; see the
[fragment import rules](tcfg.md#import-a-fragment-of-a-toml-file).

`{tcfg:gen-var NAME}` is resolved during generation; an unset variable is an error.
`{tcfg:run-var NAME}` remains in the output for substitution when loading the config.
The generator does not require the runtime environment or know the application's C++ types.
Import paths can use generation-time variables such as `{tcfg:gen-var NOM_CONFIG_LIB}`,
provided through the process environment or supplied by the build system. Expand
these placeholders before resolving and reading the files; the tool must not guess
library locations from the caller's working directory.

Missing files or fragments, malformed TOML, invalid metadata, unknown instructions
in tcfg-authored content, and failed delete/override operations stop generation.
Diagnostics identify the source file, section, and property or import involved.
Return zero on success, nonzero on failure; do not substitute empty objects for
failed imports or publish a partially resolved config. Validate values against the
[shared TOML profile](tcfg.md#toml-values-and-portability), including signed integer
bounds that Python's unbounded `int` does not enforce automatically.

Resolve and check all selected results before publishing them. Use temporary files
and replace completed outputs; leave identical output files unchanged. The build
must record success only after every selected output is published. A failed run
must not make older files appear to be current successful results.

Each file replacement is atomic; the complete output set is not a filesystem
transaction. A publication failure returns nonzero and removes temporary files,
but completed replacements may remain. The [build integration](build_system_integration.md#build-sequence)
owns success records and removal of stale outputs; the standalone CLI leaves
unselected or previously generated files in place.

`--list` reads metadata and resolves output names without evaluating application
values or environment placeholders. Without a section filter it reports all
sections, including suppressed ones. It supports build planning and deployment
selection; it is not application validation. The [C++ loader](app_config_binding.md)
performs runtime substitution, overrides, mapping, and validation.

## Python API

The `../../tools/toml_config/tcfg.py` resolves configs in memory
without writing output files. From the repository root, use it directly:

```python
from tools.toml_config.tcfg import generate_configs

configs = generate_configs(
    "apps/md_capture/config/md_capture_tcfg.toml",
    sections=["prod"],
)
print(configs["prod"].gen_file)  # md_capture.toml
print(configs["prod"].config)    # resolved application TOML as a Python dict
```

TOML tables become dictionaries, arrays become lists, and date/time values use
Python's `datetime` types; they are not converted through JSON. An empty table is
`{}` in Python and serializes as an empty TOML document. The writer's output must
parse back to the same value tree under the shared profile (NaNs compare by category).

`generate_configs()` returns a dictionary keyed by section name, preserving source
order, and writes no files.
Omit `sections` to resolve all sections with generation enabled. Generation
variables use the process environment by default. An explicit `environment`
mapping replaces it for that call. Invalid configuration raises `config_error`
with source context.

`generate_configs_with_inputs()` accepts the same arguments and returns
`(configs, input_paths)`. The paths are a set of absolute `Path` objects with
symbolic links resolved, covering the source and donor files read for selected
sections and their ancestors. The CLI uses them to protect inputs from output writes.

## Tests

Run the engine and CLI tests directly from the repository root, or through the
normal CTest workflow:

```bash
python3 -m unittest discover -s tests/unit/tcfg -p '*_test.py' -v
python3 -m unittest discover -s tests/integration/tcfggen -p '*_test.py' -v
```
