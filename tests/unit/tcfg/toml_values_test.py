# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT
"""TOML scalar, container, syntax, and serialization boundaries."""

import datetime
import math
from pathlib import Path
import tempfile
import tomllib
import unittest

from tools.toml_config import toml_codec
from tools.toml_config.tcfg import config_error, generate_configs, generate_configs_with_inputs


def assert_values(test, actual, expected):
    test.assertIs(type(actual), type(expected))
    if isinstance(expected, dict):
        test.assertEqual(actual.keys(), expected.keys())
        for key in expected:
            assert_values(test, actual[key], expected[key])
    elif isinstance(expected, list):
        test.assertEqual(len(actual), len(expected))
        for left, right in zip(actual, expected):
            assert_values(test, left, right)
    elif isinstance(expected, float) and math.isnan(expected):
        test.assertTrue(math.isnan(actual))
    else:
        test.assertEqual(actual, expected)
        if isinstance(expected, float) and expected == 0:
            test.assertEqual(math.copysign(1, actual), math.copysign(1, expected))


class toml_values_tests(unittest.TestCase):
    def test_all_scalar_types_and_empty_containers_round_trip(self):
        text = '''integer = -9223372036854775808
unsigned_max = 9223372036854775807
hexadecimal = 0x7FFF_FFFF_FFFF_FFFF
mixed = [1, true, "one", 1.0, {nested = []}]
float_values = [inf, -inf, nan, -0.0, 1e308, 5e-324]
date = 2026-11-08
clock = 12:34:56.123456789
local = 2026-11-08T12:34:56.999999999
offset = 2026-11-08T12:34:56.999999999-03:30
empty_array = []
records = [{}, {nested = {empty = {}}}]
[empty]
[nested.empty]
'''
        values = toml_codec.loads(text)
        self.assertEqual(values["clock"].microsecond, 123456)
        self.assertEqual(values["local"].microsecond, 999999)
        assert_values(self, tomllib.loads(toml_codec.dumps(values)), values)
        self.assertEqual(toml_codec.dumps({}), "")
        self.assertEqual(toml_codec.dumps({"b": 2, "a": 1}),
                         toml_codec.dumps({"a": 1, "b": 2}))

    def test_invalid_syntax_and_profile_values(self):
        invalid = ["x = null", "x = 9223372036854775808", "x = -9223372036854775809",
                   "x = 1e999", "x = -1e999", "x = 0000-01-01", "x = 23:59:60",
                   "x = 2026-11-08T00:00:00+00:60", "x = 2026-11-08T00:00:00-24:00",
                   "x = 2026-11-08T00:00:00-23:99", "\ufeffx = 1", "x = 1\ry = 2",
                   "x = 1\nx = 2", "x = 1\n[x]\ny = 2", 'x = "\\uD800"',
                   'x = "\\x41"', "x = {a = 1,}"]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                toml_codec.loads(text)

    def test_unicode_keys_and_string_escaping(self):
        for char in [chr(n) for n in range(128)] + ["é", "π", "日本語", "😀"]:
            with self.subTest(char=repr(char)):
                values = {char: char, "nested": {char: [char]}}
                assert_values(self, tomllib.loads(toml_codec.dumps(values)), values)

    def test_unrepresentable_python_values_are_rejected(self):
        bad = [{"x": None}, {"x": "\ud800"}, {"x": 2**63}, {1: "key"},
               {"nested": {None: 2}}, {"items": [{False: 1}]},
               {"x": datetime.time(12, tzinfo=datetime.timezone.utc)},
               {"x": datetime.datetime(2026, 11, 8, tzinfo=datetime.timezone(datetime.timedelta(seconds=1)))}]
        for value in bad:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                toml_codec.dumps(value)

    def test_native_values_survive_resolution_import_and_cli_serialization(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            donor = root / "values.toml"
            donor.write_text('clock = 12:34:56.123456789\nvalue = nan\n', encoding="utf-8")
            source = root / "app_tcfg.toml"
            source.write_text('''[[sections]]
[sections.tcfg]
name = "base"
import = "values.toml"

[[sections]]
[sections.tcfg]
name = "prod"
extend = "base"

[sections.values]
clock = "tcfg:import values.toml:/clock"
value = "tcfg:import values.toml:/value"
''', encoding="utf-8")
            configs, inputs = generate_configs_with_inputs(source, sections=["prod"], environment={})
            actual = configs["prod"].config
            self.assertEqual(actual["clock"], datetime.time(12, 34, 56, 123456))
            assert_values(self, actual["values"], {"clock": actual["clock"], "value": math.nan})
            assert_values(self, tomllib.loads(toml_codec.dumps(actual)), actual)
            self.assertEqual(inputs, {source.resolve(), donor.resolve()})

    def test_sections_envelope_rejects_root_application_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "app_tcfg.toml"
            for text in ['[[sections]]\ntcfg.name="dev"\n[log]\nlevel="info"',
                         'sections=[]', 'sections=[1]', '[sections]\nname="dev"']:
                source.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(config_error):
                    generate_configs(source)
            source.write_text('[tcfg]\nname="dev"\n[sections]\nvalue=1', encoding="utf-8")
            self.assertEqual(generate_configs(source)["dev"].config, {"sections": {"value": 1}})

    def test_invalid_input_bytes_and_environment_report_config_error(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "app_tcfg.toml"
            for data in [b'\xff', b'value=1\r[tcfg]\rname="dev"']:
                source.write_bytes(data)
                with self.assertRaises(config_error):
                    generate_configs(source)
            source.write_text('value="{tcfg:gen-var BAD}"\n[tcfg]\nname="dev"', encoding="utf-8")
            with self.assertRaisesRegex(config_error, "BAD.*Unicode"):
                generate_configs(source, environment={"BAD": "\udcff"})


if __name__ == "__main__":
    unittest.main()
