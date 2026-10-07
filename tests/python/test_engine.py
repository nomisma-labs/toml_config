# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Behavioral checks and the shared, language-independent conformance corpus."""

from __future__ import annotations

import datetime
import importlib
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "python"))
api = importlib.import_module("toml_config")


def assert_toml_equal(test: unittest.TestCase, actual, expected) -> None:
    """Compare value types too, including signed zero and non-reflexive NaN."""
    test.assertIs(type(actual), type(expected))
    if isinstance(expected, dict):
        test.assertEqual(actual.keys(), expected.keys())
        for key in expected:
            assert_toml_equal(test, actual[key], expected[key])
    elif isinstance(expected, list):
        test.assertEqual(len(actual), len(expected))
        for left, right in zip(actual, expected):
            assert_toml_equal(test, left, right)
    elif isinstance(expected, float) and math.isnan(expected):
        test.assertTrue(math.isnan(actual))
    else:
        test.assertEqual(actual, expected)
        if isinstance(expected, float) and expected == 0:
            test.assertEqual(math.copysign(1, actual), math.copysign(1, expected))


class conformance_test(unittest.TestCase):
    def test_success_corpus(self):
        for case in sorted((root / "tests/conformance/success").iterdir()):
            with self.subTest(case=case.name):
                resolved = api.load(case / "input.tcfg", environment={})
                expected = tomllib.loads((case / "expected.toml").read_text(encoding="utf-8"))
                assert_toml_equal(self, resolved.values, expected)
                assert_toml_equal(self, tomllib.loads(api.dumps(resolved.values)), expected)

    def test_rejection_corpus(self):
        for case in sorted((root / "tests/conformance/failure").iterdir()):
            with self.subTest(case=case.name), self.assertRaises(api.config_error):
                api.load(case / "input.tcfg", environment={})

    def test_dependency_discovery_and_diamond(self):
        case = root / "tests/conformance/success/diamond"
        resolved = api.load(case / "input.tcfg", environment={})
        self.assertEqual(resolved.values, {"a": 1, "b": 3})
        self.assertEqual([path.name for path in resolved.dependencies],
                         ["input.tcfg", "left.tcfg", "base.toml", "right.tcfg"])
        self.assertTrue(all(path.is_absolute() for path in resolved.dependencies))

    def test_import_dependencies_are_unique(self):
        case = root / "tests/conformance/success/imports"
        resolved = api.load(case / "input.tcfg", environment={})
        self.assertEqual([path.name for path in resolved.dependencies],
                         ["input.tcfg", "wrapped.tcfg", "symbols.toml"])


class engine_test(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_nested_relative_source_and_absolute_reference(self):
        data = self.write("nested/data.toml", "answer = 42\n")
        layer = self.write("nested/layer.tcfg", '[tcfg]\nversion = 1\nextends = ["data.toml"]\n')
        source = self.write("input.tcfg", f'[tcfg]\nversion = 1\nextends = [{str(layer)!r}]\n')
        self.assertEqual(api.load(source).values, {"answer": 42})
        self.assertEqual(api.load(source).dependencies[-1], data)

    def test_overlay_then_assignment_order_and_types(self):
        source = self.write("input.toml", '[service]\nport = 1\nhost = "original"\n')
        first = self.write("first.toml", '[service]\nport = 2\nhost = "first"\n')
        second = self.write("second.toml", '[service]\nport = 3\n')
        result = api.load(source, overlays=[first, second],
                          assignments=['service.port = 4', 'service.port = 5\nservice.enabled = true'])
        self.assertEqual(result.values, {"service": {"port": 5, "host": "first", "enabled": True}})
        self.assertEqual(result.dependencies, (source, first, second))

    def test_empty_assignments_reserved_and_invalid_typed_values_reject(self):
        source = self.write("input.toml", "value = 1\n")
        for assignment in ["", "# only a comment", "tcfg.version = 1", "x = unquoted", "x = 9223372036854775808"]:
            with self.subTest(assignment=assignment), self.assertRaises(api.config_error):
                api.load(source, assignments=[assignment])

    def test_environment_snapshot_and_empty_value(self):
        source = self.write("input.tcfg", '''[tcfg]
version = 1
[[tcfg.env]]
name = "SECRET"
into = ["auth", "token"]
default = "fallback"
''')
        self.assertEqual(api.load(source, environment={}).values["auth"]["token"], "fallback")
        self.assertEqual(api.load(source, environment={"SECRET": ""}).values["auth"]["token"], "")
        self.assertEqual(api.load(source, environment={"SECRET": "a$b${literal}"}).values["auth"]["token"],
                         "a$b${literal}")
        with self.assertRaises(api.config_error):
            api.load(source, environment={"SECRET": 42})
        for value in ["\udcff", "\ud800"]:
            with self.subTest(value=repr(value)), self.assertRaises(api.config_error):
                api.load(source, environment={"SECRET": value})

    def test_environment_overrides_body_after_delete(self):
        source = self.write("input.tcfg", '''token = "body"
[tcfg]
version = 1
delete = [["token"]]
[[tcfg.env]]
name = "TOKEN"
into = ["token"]
default = "env"
''')
        self.assertEqual(api.load(source, environment={}).values, {"token": "env"})

    def test_array_replacement_and_table_scalar_transitions(self):
        self.write("base.toml", 'items = [{ a = 1 }, { b = 2 }]\na = {x = 1}\nb = false\n')
        source = self.write("input.tcfg", '''items = [{ c = 3 }]
a = true
b = { y = 2 }
[tcfg]
version = 1
extends = ["base.toml"]
''')
        self.assertEqual(api.load(source).values, {"items": [{"c": 3}], "a": True, "b": {"y": 2}})

    def test_replace_then_delete_order(self):
        self.write("base.toml", '[service]\na = 1\nb = 2\n')
        source = self.write("input.tcfg", '''[tcfg]
version = 1
extends = ["base.toml"]
replace = [["service"]]
delete = [["service", "b"]]
[service]
b = 3
c = 4
''')
        self.assertEqual(api.load(source).values, {"service": {"c": 4}})

    def test_import_assigns_whole_subtree_before_body(self):
        self.write("base.toml", '[service]\nold = true\n')
        self.write("data.toml", 'new = true\n')
        source = self.write("input.tcfg", '''[tcfg]
version = 1
extends = ["base.toml"]
[[tcfg.import]]
file = "data.toml"
into = ["service"]
[service]
local = true
''')
        self.assertEqual(api.load(source).values, {"service": {"new": True, "local": True}})

    def test_import_can_select_scalar_or_empty_table(self):
        self.write("data.toml", 'a = 5\n[empty]\n')
        source = self.write("input.tcfg", '''[tcfg]
version = 1
[[tcfg.import]]
file = "data.toml"
select = ["a"]
into = ["number"]
[[tcfg.import]]
file = "data.toml"
select = ["empty"]
into = ["table"]
''')
        self.assertEqual(api.load(source).values, {"number": 5, "table": {}})

    def test_depth_limit_and_canonical_symlink_cycle(self):
        self.write("base.toml", 'a = 1\n')
        source = self.write("input.tcfg", '[tcfg]\nversion = 1\nextends = ["base.toml"]\n')
        self.assertEqual(api.load(source, max_depth=2).values, {"a": 1})
        with self.assertRaisesRegex(api.config_error, "depth"):
            api.load(source, max_depth=1)
        for limit in [0, -1, True]:
            with self.subTest(limit=limit), self.assertRaises(api.config_error):
                api.load(source, max_depth=limit)
        (self.directory / "link.tcfg").symlink_to(source)
        source.write_text('[tcfg]\nversion = 1\nextends = ["link.tcfg"]\n', encoding="utf-8")
        with self.assertRaisesRegex(api.config_error, "cycle"):
            api.load(source)

    def test_invalid_directive_shapes_and_reserved_destinations(self):
        metadata = [
            'version = "1"', 'version = 1\nextends = [1]', 'version = 1\nextends = [""]',
            'version = 1\nreplace = "x"', 'version = 1\ndelete = ["a"]',
            'version = 1\nimport = [3]', 'version = 1\nenv = true',
            'version = 1\n[[env]]\nname = ""\ninto = ["token"]',
            'version = 1\n[[env]]\nname = "X"\ninto = ["tcfg"]\ndefault = "bad"',
            'version = 1\n[[env]]\nname = "X"\ninto = ["token"]\nunknown = true',
            'version = 1\n[[import]]\nfile = "base.toml"',
            'version = 1\n[[import]]\nfile = "base.toml"\ninto = ["tcfg"]',
            'version = 1\ndelete = [["tcfg"]]',
        ]
        self.write("base.toml", "value = 1\n")
        for body in metadata:
            content = "[tcfg]\n" + body.replace("[[env]]", "[[tcfg.env]]").replace("[[import]]", "[[tcfg.import]]")
            source = self.write("input.tcfg", content)
            with self.subTest(content=content), self.assertRaises(api.config_error):
                api.load(source, environment={})

    def test_datetime_precision_and_unicode_roundtrip(self):
        source = self.write("input.toml", '''clock = 12:34:56.123456789
local = 2026-10-04T12:34:56.999999999
offset = 2026-10-04T12:34:56.999999999-03:30
text = "literal 12:34:56.123456789"
''')
        values = api.load(source).values
        self.assertEqual(values["clock"].microsecond, 123456)
        self.assertEqual(values["local"].microsecond, 999999)
        assert_toml_equal(self, tomllib.loads(api.dumps(values)), values)
        for character in [chr(code) for code in range(128)] + ["é", "π", "日本語", "😀"]:
            values = {character: character}
            with self.subTest(character=repr(character)):
                self.assertEqual(tomllib.loads(api.dumps(values)), values)

    def test_serializer_unsupported_values(self):
        for values in [{"null": None}, {"surrogate": "\ud800"}, {"large": 2**63},
                       {"offset_time": datetime.time(12, tzinfo=datetime.timezone.utc)}]:
            with self.subTest(values=repr(values)), self.assertRaises(api.config_error):
                api.dumps(values)

    def test_serializer_rejects_fractional_minute_timezone_offsets(self):
        for offset in [datetime.timedelta(seconds=1), datetime.timedelta(seconds=-61),
                       datetime.timedelta(microseconds=1)]:
            value = datetime.datetime(2026, 10, 4, tzinfo=datetime.timezone(offset))
            with self.subTest(offset=offset), self.assertRaisesRegex(api.config_error, "whole minutes"):
                api.dumps({"timestamp": value})
        value = datetime.datetime(2026, 10, 4, tzinfo=datetime.timezone(datetime.timedelta(minutes=-210)))
        self.assertEqual(tomllib.loads(api.dumps({"timestamp": value})), {"timestamp": value})

    def test_serializer_rejects_nonstring_table_keys_at_every_depth(self):
        for value in [{1: "root"}, {"string": 1, 2: "mixed"}, {"nested": {None: 2}},
                      {"records": [{"good": 1}, {False: 2}]}, {"records": [{"nested": {3: "bad"}}]}]:
            with self.subTest(value=value), self.assertRaisesRegex(api.config_error, "keys must be strings"):
                api.dumps(value)

    def test_empty_and_nested_tables_roundtrip(self):
        values = {"empty": {}, "nested": {"a": {}, "b": {"c": {}}},
                  "records": [{}, {"nested": {"empty": {}}}]}
        self.assertEqual(tomllib.loads(api.dumps(values)), values)
        self.assertEqual(api.dumps({}), "")


class cli_test(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "source.tcfg"
        self.source.write_text('value = 1\n[tcfg]\nversion = 1\n', encoding="utf-8")

    def run_cli(self, *arguments):
        environment = dict(os.environ, PYTHONPATH=str(root / "python"))
        return subprocess.run([sys.executable, "-m", "toml_config", str(self.source), *map(str, arguments)],
                              env=environment, cwd=self.directory, text=True, capture_output=True, check=False)

    def test_stdout_check_and_typed_assignment(self):
        process = self.run_cli("--set", "value = 42")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(tomllib.loads(process.stdout), {"value": 42})
        process = self.run_cli("--check")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "")

    def test_cfggen_launcher_works_outside_checkout_without_pythonpath(self):
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        output = self.directory / "generated.toml"
        depfile = self.directory / "generated.d"
        command = [sys.executable, str(root / "cfggen.py"), str(self.source)]
        process = subprocess.run([*command, "-o", str(output), "--depfile", str(depfile),
                                  "--set", "value = 42"],
                                 env=environment, cwd=self.directory, text=True, capture_output=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(tomllib.loads(output.read_text()), {"value": 42})
        self.assertIn(str(self.source), depfile.read_text())
        process = subprocess.run([*command, "--set", "invalid = unquoted"],
                                 env=environment, cwd=self.directory, text=True, capture_output=True, check=False)
        self.assertEqual(process.returncode, 2)
        self.assertNotIn("Traceback", process.stderr)

    def test_atomic_output_depfile_and_unchanged_mtime(self):
        output = self.directory / "out space" / "result#$.toml"
        depfile = self.directory / "result.d"
        process = self.run_cli("-o", output, "--depfile", depfile)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(tomllib.loads(output.read_text()), {"value": 1})
        self.assertIn("out\\ space/result\\#$$.toml:", depfile.read_text())
        self.assertIn(str(self.source), depfile.read_text())
        stamp = output.stat().st_mtime_ns
        self.assertEqual(self.run_cli("-o", output, "--depfile", depfile).returncode, 0)
        self.assertEqual(output.stat().st_mtime_ns, stamp)
        process = self.run_cli("-o", output, "--set", "invalid = unquoted")
        self.assertEqual(process.returncode, 2)
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(output.stat().st_mtime_ns, stamp)
        self.assertFalse(list(output.parent.glob(".*.toml.*")))

    def test_refuse_to_overwrite_source_or_conflicting_depfile(self):
        for args in [("-o", self.source), ("-o", self.directory / "out.toml", "--depfile", self.source),
                     ("-o", self.directory / "out.toml", "--depfile", self.directory / "out.toml")]:
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)
                self.assertTrue(self.source.read_text().startswith("value = 1"))

    def test_argument_errors(self):
        for args in [("--depfile", "result.d"), ("--check", "-o", "result.toml")]:
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)


if __name__ == "__main__":
    unittest.main()
