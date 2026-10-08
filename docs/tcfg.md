# tcfg 1 language specification

**Status: under review.** We are developing the language through
[educational examples](tcfg/examples/README.md) before revising this reference.

**tcfg** (pronounced “tee-config”) composes application configuration using TOML.
A `.tcfg` document is TOML 1.0 with a reserved root `tcfg` table describing
composition. All other root keys are application data. One entry file represents
one deployment variant; variants share other files through ordered inheritance.
The resolved result is ordinary TOML, with no directives or runtime interpreter
dependency. The Python generator implements this specification; C++ applications
consume ordinary TOML. The specification remains independent of implementation language.

```toml
[tcfg]
version = 1
extends = ["common.toml", "service.tcfg"]

[log]
level = "warning"
```

`tcfg.version` identifies the **tcfg language version**, independently of the TOML
format version. The current draft uses tcfg version 1 with TOML 1.0 syntax.

Generator `.toml` inputs contain application data only; a root `tcfg` key is an error.
`.tcfg` inputs must have `[tcfg]` and integer `version = 1`. Other extensions,
versions, unknown directive fields, and incorrect directive types are errors.
There is no implicit interpolation or executable expression language. Strings
such as `${HOME}` remain literal strings.

## Resolution order

For each file, the interpreter performs these steps in order:

1. Resolve `tcfg.extends` files left to right and merge their results.
2. Resolve `tcfg.import` entries in declaration order and assign their selected values.
3. Recursively merge the file's application data over that result.
4. Apply `tcfg.replace` entries using values from this file's application data.
5. Apply `tcfg.delete` entries.
6. Apply `tcfg.env` bindings in declaration order.

Two tables merge recursively. For every other combination of types, the later
value replaces the earlier value. Arrays, including arrays of tables, replace
in their entirety. An empty table contributes no keys to an existing table; use
`replace` to clear a table. Type changes are allowed during composition; typed
application binding and domain validation enforce the application's contract.

The entry file is resolved first. Explicit API/CLI overlays are resolved
independently, then merged left to right over the entry result. Finally, TOML
assignment patches are merged in argument order. Thus a deletion in an overlay
applies to that overlay's own inherited result, not to a previously resolved
entry file. To delete a base key, make the overlay extend that base and load the
overlay as the entry file.

## Metadata

`tcfg` accepts only `version`, `extends`, `import`, `replace`, `delete`, and `env`.
All except `version` are optional. Empty directive lists are allowed.

`extends` is an array of nonempty filename strings. Files can be `.toml` or
`.tcfg`. The declared order determines precedence; no filename or output name is
inherited implicitly.

### Fragment imports

```toml
[[tcfg.import]]
file = "symbols.toml"
select = ["spot", "symbols"]
into = ["feed", "symbols"]
```

Each entry has a required nonempty `file`, a required nonempty `into` path, and
an optional `select` path (default `[]`, meaning the entire resolved file).
The imported file is fully interpreted before selection. The selected value
replaces the destination value wholesale. Missing intermediate destination
tables are created; traversing a scalar or array is an error. Later local
application tables can merge over an imported table.

Paths are arrays of literal TOML key strings, not dotted strings or array
indexes. `['a.b', '']` addresses the empty key inside table `a.b`. Empty keys are
valid. A nonempty path has at least one component. Destination paths cannot
begin with the reserved root key `tcfg`. Missing selection keys are errors.

### Replacement and deletion

```toml
[tcfg]
version = 1
extends = ["base.toml"]
replace = [["services"]]
delete = [["logging", "obsolete"]]

[services]
only_this_service = true
```

Both directives are arrays of nonempty paths. `replace` copies the corresponding
subtree from this file's local application data, replacing the assembled subtree
without a recursive merge. That local path must exist. `delete` removes an
existing path from the assembled result. Missing paths and attempts to traverse
non-tables are errors. Duplicate deletions therefore fail. Root replacement or
deletion is not supported; destination paths starting with `tcfg` are forbidden.

### Explicit environment bindings

```toml
[[tcfg.env]]
name = "SERVICE_TOKEN"
into = ["service", "token"]
default = ""
```

`name` must match the portable pattern `[A-Za-z_][A-Za-z0-9_]*`, `into` is a
nonempty destination path, and `default` is an optional string. A present variable, including an empty
string, wins. An absent variable uses the default; absent variable and default
is an error. Bindings always produce strings and may create missing destination
tables. There is no implicit conversion to numbers or booleans. Unknown entry
fields are errors. Bindings run after local data and deletions.

The default environment is the process environment. The Python resolver accepts
an explicit name-to-string mapping and snapshots its environment once per load.
Values must contain valid Unicode; invalid UTF-8 or surrogate code points are
errors. These inputs let tests and
configuration management use controlled values. Generation bakes environment
values into the output.

## Files, failures, and portability

Inputs must be valid UTF-8 without a leading byte-order mark. LF and CRLF line
endings are accepted; a bare carriage return is an error. File paths cannot
contain NUL characters.

Relative file references resolve against the directory of the canonical
declaring file. Absolute paths are allowed. Symlinks are canonicalized before
cycle detection and reference resolution. There are no implicit search roots,
network fetches, optional missing includes, globs, or directory scans. External
inputs are ordinary explicit file references. Generation requires all referenced
files to be available with the same relationships.

Required missing or unreadable files, parse failures, invalid metadata, missing
paths, and reference cycles abort resolution. The active file depth defaults
to 64, counting the entry as depth 1; the APIs allow a positive limit. A file
can appear in separate branches without being a cycle. Dependencies are the
unique canonical paths in first-visit order, starting with the entry file and
including overlays. Error prose is implementation-specific; acceptance and
resolved values must agree.

The common value model is TOML 1.0: signed 64-bit integers, binary64 floats
(including explicit infinities and NaN), booleans, Unicode strings, arrays,
tables, dates, times, local datetimes, and offset datetimes. Finite float literals
that overflow binary64 are rejected; underflow follows binary64 rounding.
Calendar years range from 1 through 9999, and seconds range from 0 through 59;
year zero and leap-second literals are not supported. Datetime offsets have hours
from 00 through 23 and minutes from 00 through 59, with either sign; malformed
components are rejected before normalization. Time fractions retain microsecond
precision; additional digits are truncated, as TOML permits. Comments, key
ordering, numeric spelling, and original formatting are not semantic data and
are not guaranteed to survive generation. Compare NaNs by category, not `==`.

`--set` / API assignments are nonempty TOML document patches, usually a single
dotted-key assignment, for example `feed.timeout_ms = 500`. Strings require TOML
quotes. The patch must contain application data and cannot contain root `tcfg`.
Missing keys may be added, and merge behavior is identical to file layering.

This file and the fixtures in `tests/conformance` are the starting point for
future implementations in other languages. Rust support is not implemented.
