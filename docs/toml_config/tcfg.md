# tcfg - a structural configuration language

## Objective
Nomisma **tcfg** language defines application configuration using TOML.
The purpose of this language is to add structural features to TOML configs, i.e. ability to compose a single valid config from several fragments. For those who are familiar with OOP this reminds "inheritance" and "aggregation". So instead of redefining potentially complex multi-component config for different purposes we define "base" config with some default parameters and then re-use it by extending it in "derived" configs (inheritance) or by defining common parameters in "donor" config and including parts or whole "donor" into an "acceptor" config (aggregation). Those are main structural mechanisms. Apart from it there would be "adjustment" instructions that controls how these extension (aka inheritance) or aggregation (aka import or inclusion) happens.
Another way of looking at tcfg - a "stackable" or "layered" configuration with each layer introducing or refining previous layers config properties.

## Basic conventions
**tcfg** files by convention have `*_tcfg.toml` file suffix. Any tcfg file is a well formed TOML file so it can be processed with regular TOML tools (e.g. pretty printers etc.) The name of the tcfg file will have its special meaning when we come to integration with Nomisma build system, but in this guide we can use any name (usually just `app_tcfg.toml`). Nomisma platform provides a tool to generate well formed TOML configs from tcfg so they can be used by Nomisma apps in different cases.

The format contract is TOML **1.0**. C++ selects this version explicitly; the
Python generator uses `tomllib` with the same supported grammar. Features from
other TOML versions are outside the contract. Source files, ordinary donors, and
generated files use that grammar. TOML
comments and formatting are authoring conveniences; generation preserves values,
not their source spelling or layout. The generator needs Python 3.11+ for `tomllib`.

## Motivating example
Just to make it more illustrative let's consider `md_capture` app that have 2 configs - for dev and prod environments (shown schematically):
```
dev:
    log.level = debug
    connection
        snapshot.address = wss://ws-api.binance.com:443/ws-api/v3
        address = wss://stream-sbe.binance.com:9443/ws
    subscription
        symbols = btcusdt
        channels = trade, depth
    md_log.file = binance-spot-%Y%m%d-%H.md

prod:
    log
        level = warn
        file = log/%Y%m%d/md_capture.log
    connection
        snapshot.address = wss://ws-api.binance.com:443/ws-api/v3
        address = wss://stream-sbe.binance.com:9443/ws
    subscription
        symbols = btcusdt, ethusdt
        channels = trade, depth
    md_log.file = md/%Y%m%d/binance-spot-%Y%m%d-%H.md
```
As you see even in this small config there are repeating and unique parameters and values. There are multiple ways how we can abstract them out. But first - why would we want to do it?
Here are the cases:
1. A trader/quant maintains a list of required symbols for MD capture. He wants to focus on this list only and not to get into details of app configuration. For that he creates a file `binance-spot-md-capture-symbols.toml` and adds the required symbols there. On the other hand a dev, while testing the MD capture app, wants to focus on specific list of symbols (perhaps only one symbol for simplicity).
2. An infra team monitors the connection parameters of Binance MD end point. They learned that Binance migrated to a new infra with different DNS address. Infra team wants to apply this new address for all components homogenously - for that they maintain a single `binance-spot-connection.toml` config which contains actual connectivity parameters, so they don't need to update configs of 20+ apps that connect to Binance market data end point. However one trader learned that one particular subscription channel that he subscribes (e.g. liquidation info) was not migrated properly by Binance, so he wants his app to use old connectivity parameters - so he applies an exception to his app config.

One possible way of defining a coherent config for this app and use cases is to:
1. Create base config which would be also a dev config, e.g. `md_capture.toml` with complete dev config;
2. Create `md_capture_tcfg.toml` which in `base` case imports `md_capture.toml`;
3. Add `ci` section for integration environment that inherits base config and imports `binance-spot-connection.toml`. It also updates parameters `log` and `md_log` to standard values for infra deployment;
4. Add `prod` section for main production deployment and inherit it from `ci`. Update `subscription.symbols` parameter - by including it from `binance-spot-md-capture-symbols.toml`;
5. Add `prod-liquidation` section to collect liquidation data, inherit it from `prod` and update `connection` and `subscription` parameter sections.

As you see, by defining configuration this way we allowed several teams (dev, QA, devops/infra, researchers, traders) to collaborate and not to step on each other toes while configuring and using md_capture app.

## Structure of tcfg file

A **tcfg** file contains one or more ordered config sections. Every section is a
TOML table with a `tcfg` metadata table and application properties alongside it.
TOML documents have a table at their root, so the multiple-section form puts the
sections in an array of tables named `sections`:

```toml
[[sections]]
[sections.tcfg]
name = "base"
gen_file = "app.toml"

[sections.log]
level = "debug"

[[sections]]
[sections.tcfg]
name = "prod"
extend = "base"

[sections.log]
level = "warn"
```

`[[sections]]` starts a new section. Subsequent `[sections.tcfg]` and
`[sections.log]` headers belong to that most recent section. Writing `[log]`
instead would create a document-root table and is an error in this form. TOML
inline tables and dotted keys are equivalent ways of authoring the same tree;
the generator works on parsed values, not on the choice of syntax.

For a single section, omit the `sections` envelope and use root metadata:

```toml
[tcfg]
name = "dev"
gen_file = "app.toml"

[log]
level = "debug"
```

If the document has a root `tcfg` key, it is the single-section form and that key
must be a metadata table. Otherwise the document must contain exactly one root
key, `sections`, holding a nonempty array of section tables. Mixing the forms or
omitting section metadata is an error. In the single form, an application property
named `sections` is ordinary data; in the array form it lives inside an entry.

The source section's `tcfg` key is reserved for metadata and excluded from generated
application TOML. The outer `sections` envelope is also removed. Nested application keys named
`tcfg` are ordinary data. Metadata accepts exactly `name`, `extend`, `import`,
`generate`, and `gen_file`; unknown keys or wrong types are errors. No version,
file inheritance, or additional composition mechanism is implicit.

In tcfg-authored keys and values, the `tcfg:` marker is reserved for instructions
and placeholders; using it as literal application text is unsupported. Unknown or
malformed markers are errors. Imported ordinary TOML stays literal.

See [app_tcfg.toml](examples/stucture_config/app_tcfg.toml) for an example with three
sections: `common`, `ci`, and `prod`. Each section defines an application config,
although writing its output file may be suppressed. A section usually represents
an environment (e.g. ci, prod) or a use case (e.g. sim, perf).

The same folder contains [app.toml](examples/stucture_config/app.toml), the default
application config, and [symbol.toml](examples/stucture_config/symbol.toml), the
symbol list imported by `prod`.

The structure follows these rules:

1. **Section identity and order.** Each section has a unique `tcfg.name`, including
   in the single-section form. The first section is the root and has no `tcfg.extend`.
   Its name can be any section name, such as `dev`, `sim`, `common`, or `base`;
   Every other section names exactly one parent through `tcfg.extend`, a string
   referring to an earlier section in the same file. All sections therefore derive
   directly or indirectly from the root; forward references and inheritance cycles
   are not allowed.
2. **Merge precedence.** Start with the parent's resolved application config, or
   an empty table for the root. `tcfg.import` accepts a single filename string or
   an array of filename strings; `"app.toml"` is equivalent to `["app.toml"]`.
   Merge those files in their listed order, then merge the section's local
   application properties. Omitting `tcfg.import` means no section-level imports.
   Tables merge recursively; arrays and other values replace earlier values.
   Later values take precedence.
3. **Metadata inheritance.** Application data is inherited separately from
   metadata. `tcfg.name`, `tcfg.extend`, `tcfg.import`, and `tcfg.generate` describe
   only the current section and are not inherited. An explicit `tcfg.gen_file`
   selects its output filename; when omitted in a derived section, the filename
   is inherited from its parent. See
   [output filenames](#output-filenames-default-inherited-and-explicit) for the
   default naming rule. `tcfg.name`, `tcfg.extend`, and `tcfg.gen_file` are literal
   strings and do not support placeholders.
4. **Property imports.** A tcfg-authored property value such as
   `"tcfg:import symbol.toml:/symbols"` imports TOML data at that property before merging
   it into the inherited/imported configuration. Imported ordinary TOML remains
   literal data during generation. [Fragment imports](#import-a-fragment-of-a-toml-file)
   select a value within a donor file.
5. **Config generation.** `tcfg.generate` is a boolean that defaults to `true` for
   each section. Setting it to `false` suppresses that section's output file, while
   its resolved application data and output filename remain available to children.
   Its imports and instructions are evaluated when it is an ancestor of a selected
   section. Children generate their own files by default, even when their parent
   has `tcfg.generate` set to `false`.

Validate metadata and inheritance for every section. Resolve imports and
instructions only for selected sections and their ancestors; unrelated sections
do not require their donor files or generation variables to be available.

In the example, `common` imports `app.toml` and sets `log.level` to `debug`, but
`tcfg.generate` is `false`, so it produces no output file. The `ci` section changes
the level to `warn` and inherits the output filename `app.toml`.
The `prod` section inherits from `ci`, selects `prod.toml` as its output filename,
and imports the symbol list into `subscription.symbols`. Neither child specifies
`tcfg.generate`, so both generate their output files.

A common, optional layout places `<app>_tcfg.toml` and a complete application
config, `<app>.toml`, in `<app>/config`. The root section can import that TOML
file in full and use the same output filename. Source files and generated files
live in different locations: the build collects source configs under
`build/<preset>/config/`, and generated configs belong under
`build/<preset>/genconfig/`. When the source TOML already contains the desired
development configuration, the app can use it directly without generation.

## Define basic tcfg mechanisms

Each example folder contains a tcfg source, any TOML files it imports, and the
expected application TOML under `genconfig/`. Examples with several sections group
their expected outputs under `genconfig/<section>/`, so sections can share an output
filename. These directories identify the results being illustrated; the build or
generator invocation selects the actual output location.

The examples introduce the mechanisms in this order:

1. [In-place config with an explicit output name](#in-place-config-with-an-explicit-output-name)
1. [Import a TOML config](#import-a-toml-config)
1. [Import a fragment of a TOML file](#import-a-fragment-of-a-toml-file)
1. [Output filenames: default, inherited and explicit](#output-filenames-default-inherited-and-explicit)
1. [Extend a section](#extend-a-section)
1. [Merge inherited and local parameters](#merge-inherited-and-local-parameters)
1. [Merge several TOML files into an extended section](#merge-several-toml-files-into-an-extended-section)
1. [Delete a key and override a value](#delete-a-key-and-override-a-value)
1. [Override with imported content](#override-with-imported-content)
1. [Illustrate all basic mechanisms in one example](#complete-example)

### In-place config with an explicit output name

The [app_tcfg.toml](examples/mech_01_config/app_tcfg.toml) example defines a complete
application config directly in a single section. All application values are
written in place alongside the section's `tcfg` metadata.

- `tcfg.name` identifies the root section as `dev`.
- `tcfg.gen_file` names the output file `app.toml`.
- `log` and `subscription` contain the application settings.

The source file uses the single-section form. Placing that section under
`[[sections]]` and prefixing its table headers with `sections.` has the same meaning. Resolving the section produces one TOML table
containing the application settings, with the `tcfg` metadata removed.
`tcfg.generate` is omitted, so it defaults to `true`. The expected output is shown in
[genconfig/app.toml](examples/mech_01_config/genconfig/app.toml).

### Import a TOML config

In [app_tcfg.toml](examples/mech_02_config/app_tcfg.toml), the single `dev` section
has `tcfg.import` set to `"app.toml"`. This is equivalent to `["app.toml"]`; an
array supports merging several whole TOML tables in order. Relative import paths
are resolved from the tcfg source file's directory, so the input is the adjacent
[app.toml](examples/mech_02_config/app.toml).

The section has no local application properties. Its expected output,
[genconfig/app.toml](examples/mech_02_config/genconfig/app.toml), therefore contains
the same application data as the imported file. The source and output share a
filename but live in different locations. The source is also a complete config
that the application can use directly.

### Import a fragment of a TOML file

[app_tcfg.toml](examples/mech_03_config/app_tcfg.toml) imports two arrays from
[markets.toml](examples/mech_03_config/markets.toml), a donor containing separate
`spot` and `perps` settings:

| Destination property | Import instruction | Selected value |
|---|---|---|
| `subscription.symbols` | `tcfg:import markets.toml:/spot/symbols` | The spot symbol array |
| `subscription.channels` | `tcfg:import markets.toml:/spot/channels` | The spot channel array |

In `tcfg:import markets.toml:/spot/symbols`, the file is `markets.toml` and the
config pointer is `/spot/symbols`. The colon separates the filename from the pointer,
which retains its leading `/`. Without a colon, as in `tcfg:import markets.toml`,
the whole document is imported. As in the previous example, the donor file is
located relative to the tcfg source.

After expanding generation placeholders, split the import argument (the text after
`tcfg:import`) at its first `:`. The colon is reserved and cannot appear in donor
file paths; any later colons belong to the config pointer.

The **config pointer** applies [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901)
token syntax to the parsed TOML tree: tables supply named members and arrays supply
zero-based elements. This is an addressing convention, not a conversion to JSON.
`/spot/symbols/0` selects the first array element. In property names, `~1`
represents `/` and `~0` represents `~`. A missing member or invalid array index
is an error. Array indexes use `0` or a nonzero digit followed by digits; `-`,
negative indexes, and leading zeroes are invalid. Empty pointer text selects the
whole document, while `/` selects a table's empty-string key. Dots are literal:
`/a.b` selects the key `"a.b"`, not the path `/a/b`. Invalid `~` escapes fail.

The selected TOML value retains its type: an array stays an array,
a string stays a string, and a date stays a date. A TOML donor always has a table
root. To share a standalone list, write `symbols = ["btcusdt", "ethusdt"]` and
import `symbol.toml:/symbols`; importing the whole file would import the table.

The selected arrays become the property values before the local section is
merged. The unrelated `perps` settings do not enter the application config.
See [genconfig/app.toml](examples/mech_03_config/genconfig/app.toml).

Fragment imports are also useful for keeping generation-time values in a separate
TOML map. In the same example, [values.toml](examples/mech_03_config/values.toml)
holds `log_level` and `timeout_s`. `tcfg:import values.toml:/log_level` supplies
`log.level`, while `tcfg:import values.toml:/timeout_s` supplies `connection.timeout_s`.
The generator copies these values into the output as a string and a number,
respectively, using the same fragment-import mechanism.

Imported ordinary TOML is not interpreted by the generator, even if its filename
ends in `_tcfg.toml`: import means data import, never recursive section resolution.
Do not use a structured source as a donor to obtain its generated config. A
section-level donor contributes its complete table, including metadata-looking
keys as literal data. Runtime environment
placeholders are resolved when the application loads the config.

### Output filenames: default, inherited and explicit

[app_tcfg.toml](examples/mech_04_config/app_tcfg.toml) illustrates three naming
cases. The default filename comes from the source filename: replace the
`_tcfg.toml` suffix with `.toml`. Thus `app_tcfg.toml` defaults to `app.toml`.
For a source passed explicitly with another suffix, retain its full basename.
Names are nonempty literal strings; output section paths and filenames must remain
relative and cannot contain NUL or `..` path components. Output containment and
collision checks are defined by [generation](config_generation.md#inputs-and-outputs).

| Section | Filename rule | Expected output |
|---|---|---|
| `dev` | No `tcfg.gen_file`; use the source-derived default | [dev/app.toml](examples/mech_04_config/genconfig/dev/app.toml) |
| `ci` | No `tcfg.gen_file`; inherit the parent's filename | [ci/app.toml](examples/mech_04_config/genconfig/ci/app.toml) |
| `prod` | Explicit `tcfg.gen_file` is `capture.toml` | [prod/capture.toml](examples/mech_04_config/genconfig/prod/capture.toml) |

An explicit filename takes precedence over an inherited filename. Importing a
file supplies application data; its filename does not change the section's output
name. The `ci` and `prod` outputs here have the same application data even though
their filenames differ.

### Extend a section

In [app_tcfg.toml](examples/mech_05_config/app_tcfg.toml), `ci` extends `base`,
and `prod` extends `ci`. Both derived sections contain only `tcfg` metadata.
Their application settings and output filenames are inherited unchanged.

Compare [base/app.toml](examples/mech_05_config/genconfig/base/app.toml),
[ci/app.toml](examples/mech_05_config/genconfig/ci/app.toml), and
[prod/app.toml](examples/mech_05_config/genconfig/prod/app.toml): all three have the
same contents. Each derived section has exactly one parent, and that parent appears
earlier in the source array.

### Merge inherited and local parameters

[app_tcfg.toml](examples/mech_06_config/app_tcfg.toml) starts with a `base` config
and changes selected settings in `ci`. Compare
[base/app.toml](examples/mech_06_config/genconfig/base/app.toml) with
[ci/app.toml](examples/mech_06_config/genconfig/ci/app.toml):

- `log.level` changes from `debug` to `warn`.
- `log.file.name` changes to `ci.log`, while the inherited `rotationSize` remains.
- `connection.timeout_s` changes to `20`, while the inherited address remains.
- `subscription.symbols` becomes `["ethusdt"]`. The inherited symbol array is
  replaced in full; `subscription.channels` remains unchanged.

Table properties merge recursively. At every other value boundary, the later
value replaces the earlier one. Resolving `ci` leaves the resolved `base` config
unchanged, so other sections can still inherit the original values.

### Merge several TOML files into an extended section

In [app_tcfg.toml](examples/mech_07_config/app_tcfg.toml), `ci` extends `base`,
then imports [connection.toml](examples/mech_07_config/connection.toml) and
[deployment.toml](examples/mech_07_config/deployment.toml), in that order.
Local properties are applied last.

The value of `connection.timeout_s` shows the precedence:

| Step | Value |
|---|---|
| Inherit `base` | `5` |
| Merge `connection.toml` | `10` |
| Merge `deployment.toml` | `20` |
| Merge local properties | `30` |

The final config keeps the address from `connection.toml`, the log filename from
`deployment.toml`, and the local log level `error`. Other inherited values remain.
See [base/app.toml](examples/mech_07_config/genconfig/base/app.toml) and
[ci/app.toml](examples/mech_07_config/genconfig/ci/app.toml).

This is still single inheritance: `ci` has one parent section. The import list
adds ordinary TOML data sources to that inherited configuration. Consider that
multiple import is a powerful tool that can easily confuse both the writer and
the reader of the config, especially when many people collaborate on it. Typical
use case for this feature is building a config for multiple environments (e.g.
dev, research, ci, prod) where different people are responsible for different
parts of the app config. So if the config has such logical separation, then
multiple import is a useable tool. However if the config is not semantically
structured, then multiple import can create a mess.

### Delete a key and override a value

[app_tcfg.toml](examples/mech_08_config/app_tcfg.toml) applies two instructions
while merging `ci` into its inherited application config:

- `log.file` has the value `"tcfg:delete"`, removing that property. The inherited
  `log.level` remains.
- `subscription` contains a `tcfg:override` wrapper whose value is the complete
  replacement object. The inherited `snapshot` property disappears because the
  replacement contains only `symbols` and `channels`.

Compare [base/app.toml](examples/mech_08_config/genconfig/base/app.toml) with
[ci/app.toml](examples/mech_08_config/genconfig/ci/app.toml).

`tcfg:delete` operates on a table property. Deleting a missing property is an
error. It cannot delete an array element or the application root. TOML has no
null value; omission is distinct from deleting an inherited key. A quoted
`"null"` is ordinary string data and has no special meaning.

An override wrapper is a table containing exactly one key, `tcfg:override`.
The key must be quoted in TOML because it contains a colon. Its value replaces
the target in full, without recursive merging with the previous value:

```toml
[sections.subscription]
"tcfg:override" = { symbols = ["ethusdt"], channels = ["trade"] }
```

This snippet belongs to the current `[[sections]]` entry. The replacement can be
a table, array, or scalar; if the target property is absent, it creates it. An
empty replacement table clears a table; an ordinary empty table merely contributes
no keys during recursive merging. A delete inside a replacement has no inherited
value to remove and fails. Array values replace in full; imports and placeholders
inside tcfg-authored array elements are still evaluated. Neither the delete instruction nor the override wrapper
is written to the generated config.

### Override with imported content

[app_tcfg.toml](examples/mech_09_config/app_tcfg.toml) uses an import instruction
as the value inside a `tcfg:override` wrapper:

| Section | Replacement source | Expected output |
|---|---|---|
| `base` | Initial in-place settings | [base/app.toml](examples/mech_09_config/genconfig/base/app.toml) |
| `ci` | `tcfg:import subscription.toml` | [ci/app.toml](examples/mech_09_config/genconfig/ci/app.toml) |
| `prod` | `tcfg:import markets.toml:/perps` | [prod/app.toml](examples/mech_09_config/genconfig/prod/app.toml) |

The `ci` replacement comes from the complete
[subscription.toml](examples/mech_09_config/subscription.toml) document. The
`prod` replacement comes from the `perps` object inside
[markets.toml](examples/mech_09_config/markets.toml).

First resolve the import, including its pointer if present. Then assign the
result as the complete `subscription` value. The inherited `snapshot` property
does not survive either replacement. Imports inside an in-place replacement
object are also resolved before that object is assigned.

### Complete example

[md_capture_tcfg.toml](../../apps/md_capture/config/md_capture_tcfg.toml) brings the
mechanisms together for the [motivating example](#motivating-example).
The [md_capture application](../../apps/md_capture/README.md) loads these
configs into C++, validates them, and illustrates the resulting capture settings.
The application and this guide share the inputs in its `config/` directory;
the expected generated outputs remain linked below.

The input files separate the responsibilities:

- [md_capture.toml](../../apps/md_capture/config/md_capture.toml) contains a complete
  development config with literal values. It can be used without generation.
- [connection.toml](../../apps/md_capture/config/connection.toml) supplies the current
  connection settings shared by deployed variants.
- [deployment.toml](../../apps/md_capture/config/deployment.toml) supplies deployment
  logging settings and the market-data output path.
- [symbols.toml](../../apps/md_capture/config/symbols.toml) supplies separate symbol
  lists for ordinary spot capture and liquidation capture.

| Section | How it is assembled | Expected output |
|---|---|---|
| `base` | Import the complete development config | [base/md_capture.toml](examples/complete_config/genconfig/base/md_capture.toml) |
| `ci` | Extend `base`; import connection and deployment settings | [ci/md_capture.toml](examples/complete_config/genconfig/ci/md_capture.toml) |
| `prod` | Extend `ci`; import `/spot` from the symbol lists | [prod/md_capture.toml](examples/complete_config/genconfig/prod/md_capture.toml) |
| `prod-liquidation` | Extend `prod`; restore the old connection, replace the subscription, and adjust logging | [prod-liquidation/md_capture_liquidation.toml](examples/complete_config/genconfig/prod-liquidation/md_capture_liquidation.toml) |

For the liquidation exception, `connection` is overridden by importing the
`/connection` fragment of the development config. This restores the old settings
as one object. `subscription` is overridden with the liquidation symbol list and
channel, while `log.file` is deleted and `md_log.file` receives a separate capture
path. The other variants retain their own resolved settings.


## Advanced tcfg generation topics

1. Suppress config generation with `tcfg.generate = false`; see the
   [structure rules and example](#structure-of-tcfg-file).
   The section remains available for inheritance, but the flag is not inherited.
   This property is useful if you created a "service" config section - which is not
   supposed to have an associated environment or use case, but it's used by other
   config sections as an extension base.
1. Placeholder substitution during generation
    `{tcfg:gen-var NAME}` substitutes a generation-time variable supplied through the
    process environment or by the build system. Placeholders are allowed in
    application string values and import paths. A placeholder can occupy the whole
    string or appear within text; surrounding text is preserved. `{tcfg:run-var NAME}`
    placeholders pass through generation unchanged for resolution when loading the config.
    Example:
    ```toml
    [log]
    file = "{tcfg:gen-var NFS_PATH}/logs"
    ```
1. Common config libraries
    Config libraries are shared directories of TOML files that app configs can
    import. They avoid duplicating common settings, such as production connection
    parameters used by both a trading strategy and an MD capture app.

    Import paths in `tcfg.import` and `tcfg:import` can start with a location
    placeholder. For example, `NOM_CONFIG_LIB` can point to a well-known config
    library directory in the project. Set it in the process environment, or let
    the build system supply it in the generator's environment:

    ```toml
    symbols = "tcfg:import {tcfg:gen-var NOM_CONFIG_LIB}/markets.toml:/spot/symbols"

    [tcfg]
    name = "prod"
    import = "{tcfg:gen-var NOM_CONFIG_LIB}/connection.toml"
    ```

    Resolve location placeholders before reading the referenced files. An unset
    variable or missing file fails generation. Expanded absolute paths are used
    directly; relative paths are resolved from the tcfg source file's directory.

## Runtime value overrides

When loading a TOML config file, the application follows this order:

1. Parse the application TOML.
2. Resolve runtime environment placeholders.
3. Apply command-line overrides.
4. Perform TOML/C++ mapping and application validation.

For [hard-wired config](app_config_binding.md#hard-wired-config), command-line
overrides target the TOML serialized from the initialized C++ config.

Each stage must succeed before the next begins. An unset required environment
variable causes failure before command-line overrides, even if an override would
replace that value.

There could be multiple reasons for runtime value overrides, but they all boil down to the fact that some parameter is required to have different value at the time when app is executed (versus the time when the app config was defined and generated), for instance.
1. We want to restart the app with different log.level to get more detailed diagnostics.
1. We want to try running the trading strategy with different parameters (e.g. risk aversion).
1. Binance MD API endpoint address changed and we need to restart MD capture with different address.
1. Order gateway requires private key to connect to Order API endpoint and we don't want to provide this key during config generation, so we set the private key only when we start a trading strategy.

All such cases can be done by updating the app config and restarting the app (or dynamically resetting the app config). However this might be inconvenient. For this case we have other ways of runtime value overrides.

### Types of overrides

1. Placeholder substitution at runtime.
    Example `app.toml`:
    ```toml
    [log]
    level = "{tcfg:run-var LOG_LEVEL}"
    file = "{tcfg:run-var NFS_PATH}/logs"
    ```
    `{tcfg:run-var NAME}` substitutes an environment value within the string when
    loading the config.
    With `NFS_PATH=/srv/data`, the example's `log.file` becomes `/srv/data/logs`.
    An unset variable is an error.
2. Command line config override format
    The app accepts `--set <config-pointer>=<value>` to replace an existing TOML value.
    A missing target is an error. These overrides run after placeholder substitution,
    so command-line values take precedence. Value conversion and ordered mapping
    probes follow [loading and overrides](app_config_binding.md#loading-and-overrides).

### TOML values and portability

The shared value profile for generation and runtime parsing is TOML 1.0 with
signed 64-bit integers and binary64 floats. Explicit `inf`, `-inf`, and `nan`
are valid document values; `cfg_double` rejects them during typed mapping.
Finite float literals that overflow binary64 are errors, not implicit infinity.
Booleans are not numbers. Mixed-type arrays are valid TOML; an application vector
still requires every element to map to its enabled C++ element type.

Dates, local times, local datetimes, and offset datetimes retain their categories.
The framework profile uses calendar years 1–9999, seconds 0–59, and microsecond
precision, truncating additional fractional digits. Offsets must have hours
00–23 and minutes 00–59; validate components before normalization. Year zero and
leap seconds are unsupported. Generation does not supply an implicit timezone.
C++ parsing uses the same profile so directly loaded and generated configs agree.
The common C++ types do not add date/time aliases; use an explicitly enabled
custom converter when the application needs these values.

Source files must be valid UTF-8 without a BOM. LF and CRLF are accepted; bare CR,
invalid Unicode, duplicate keys, and incompatible table declarations fail parsing.
Comments, key order, numeric bases, quoting, and table layout are not semantic data.
Array order is semantic. Serialization must preserve types, empty tables and arrays,
finite float round trips, and infinity signs; NaN payloads and signs are not promised.
An empty application table is an empty TOML document, not a bare `{}`.

Placeholder substitution affects string values, including strings inside arrays,
but never keys. It also applies to literal-quoted TOML strings after parsing;
quotes do not disable the tcfg language. Substitutions remain strings, even when
a variable contains `20` or `true`; use a typed fragment import for generation-time
numbers. A missing variable fails, while a present empty string is valid. Inserted
text is not reparsed as a directive or recursively expanded. Runtime placeholders
are forbidden in import paths, which must be resolved before application startup.

The syntax baseline follows the [TOML 1.0 specification](https://toml.io/en/v1.0.0);
the profile above is the framework's cross-parser contract.
