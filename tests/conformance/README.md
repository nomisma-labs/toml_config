# tcfg conformance corpus

These fixtures validate the implementation present during preparation. They do
not validate the target [tcfg contract](../../docs/toml_config/tcfg.md), whose
implementation is pending documentation review. See [status](../../TODO.md).

Each `success/<case>/input.tcfg` must resolve to the typed values in its
`expected.toml`; serialization layout is immaterial. Helpers belong in the same
case directory. Each `failure/<case>/input.tcfg` must fail without producing a
resolved document. The missing environment variable used by the fixtures is
absent from the Python test mapping.

The corpus covers ordered layering, nested source-relative dependencies,
subtree imports, replacement and deletion, environment defaults, quoted and
empty keys, diamond inheritance, every TOML value kind, integer boundaries,
non-finite floats, and microsecond time precision. Rejection cases cover missing
dependencies, canonical dependency cycles, invalid directives, missing paths,
reserved metadata, syntax errors, and integer overflow.

Run the Python suite from the repository root:

```sh
python3 -m unittest discover -s tests/python -v
```

The Python tests also cover generator overlays, typed patches, empty environment
values, and literal strings that resemble interpolation. Future implementations
can consume these fixtures and compare both values and TOML types. C++ tests
cover ordinary TOML loading, binding, and application discovery separately.
