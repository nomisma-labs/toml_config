# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""The educational examples and focused language contracts for tcfg resolution."""

import tomllib
from tools.toml_config import toml_codec
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.toml_config.tcfg import config_error, generate_configs


repository = Path(__file__).resolve().parents[3]
examples = repository / "docs/toml_config/examples"


class example_tests(unittest.TestCase):
    def test_all_documented_expected_outputs(self):
        sources = sorted((source, source.parent / "genconfig")
                         for source in examples.glob("*/*_tcfg.toml")
                         if (source.parent / "genconfig").is_dir())
        sources.append((repository / "apps/md_capture/config/md_capture_tcfg.toml",
                        examples / "complete_config/genconfig"))
        self.assertEqual(len(sources), 10)
        for source, expected_dir in sources:
            with self.subTest(example=source.parent.name):
                expected_files = set(expected_dir.rglob("*.toml"))
                actual_files = set()
                for name, result in generate_configs(source, environment={}).items():
                    self.assertEqual(name, result.name)
                    expected = expected_dir / name / result.gen_file
                    if not expected.is_file():
                        expected = expected_dir / result.gen_file
                    self.assertTrue(expected.is_file(), str(expected))
                    self.assertEqual(result.config, tomllib.loads(expected.read_text()))
                    actual_files.add(expected)
                self.assertEqual(actual_files, expected_files)

    def test_structure_example(self):
        source = examples / "stucture_config/app_tcfg.toml"
        results = generate_configs(source, environment={})
        self.assertEqual(list(results), ["ci", "prod"])
        self.assertEqual({name: item.gen_file for name, item in results.items()},
                         {"ci": "app.toml", "prod": "prod.toml"})
        expected = tomllib.loads(source.with_name("app.toml").read_text())
        expected["log"]["level"] = "warn"
        self.assertEqual(results["ci"].config, expected)
        expected["subscription"]["symbols"] = tomllib.loads(
            source.with_name("symbol.toml").read_text())["symbols"]
        self.assertEqual(results["prod"].config, expected)


class resolver_tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.source = self.directory / "app_tcfg.toml"

    def write_toml(self, name, content):
        destination = self.directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if name == self.source.name and isinstance(content, list):
            content = {"sections": content}
        elif not isinstance(content, dict):
            content = {"sections": False if content is None else content}
        destination.write_text(toml_codec.dumps(content), encoding="utf-8")
        return destination

    def resolve_document(self, content, **options):
        self.write_toml(self.source.name, content)
        options.setdefault("environment", {})
        return generate_configs(self.source, **options)

    def assert_failure(self, content, *details, **options):
        with self.assertRaises(config_error) as caught:
            self.resolve_document(content, **options)
        message = str(caught.exception)
        self.assertIn(self.source.name, message)
        for detail in details:
            self.assertIn(detail, message)
        return message

    def test_single_section_and_section_envelope_are_equivalent(self):
        content = {"tcfg": {"name": "simulation"}, "enabled": True}
        for document in (content, [content]):
            with self.subTest(document=document):
                results = self.resolve_document(document)
                self.assertEqual(list(results), ["simulation"])
                result = results["simulation"]
                self.assertEqual((result.name, result.gen_file, result.config),
                                 ("simulation", "app.toml", {"enabled": True}))

    def test_tcfg_metadata_name_is_reserved_only_at_section_root(self):
        result = self.resolve_document({
            "tcfg": {"name": "dev"}, "nested": {"tcfg": {"name": "application data"}},
        })["dev"]
        self.assertEqual(result.config, {"nested": {"tcfg": {"name": "application data"}}})

    def test_explicit_output_filename_does_not_follow_import_name(self):
        self.write_toml("donor.toml", {"value": 1})
        result = self.resolve_document({
            "tcfg": {"name": "dev", "gen_file": "capture.toml", "import": "donor.toml"}
        })["dev"]
        self.assertEqual(result.gen_file, "capture.toml")

    def test_invalid_document_and_section_shapes(self):
        for document in (None, False, "text", 2, [], [1], {}, {"tcfg": []},
                         {"tcfg": {}}, {"tcfg": {"name": 1}}):
            with self.subTest(document=document):
                self.assert_failure(document)

    def test_invalid_inheritance(self):
        documents = [
            [{"tcfg": {"name": "dev", "extend": "dev"}}],
            [{"tcfg": {"name": "dev"}}, {"tcfg": {"name": "dev", "extend": "dev"}}],
            [{"tcfg": {"name": "dev"}}, {"tcfg": {"name": "ci"}}],
            [{"tcfg": {"name": "dev"}}, {"tcfg": {"name": "ci", "extend": "missing"}}],
            [{"tcfg": {"name": "dev"}}, {"tcfg": {"name": "ci", "extend": ["dev"]}}],
            [{"tcfg": {"name": "dev"}}, {"tcfg": {"name": "ci", "extend": "prod"}},
             {"tcfg": {"name": "prod", "extend": "dev"}}],
        ]
        for document in documents:
            with self.subTest(document=document):
                self.assert_failure(document)

    def test_invalid_metadata_types(self):
        for field, value in (("generate", 1), ("generate", "false"),
                             ("gen_file", []), ("import", {}), ("import", [1])):
            with self.subTest(field=field, value=value):
                self.assert_failure({"tcfg": {"name": "dev", field: value}}, field)

    def test_identity_parent_and_output_metadata_are_literal(self):
        for field in ("name", "gen_file", "extend"):
            with self.subTest(field=field):
                content = [{"tcfg": {"name": "dev"}},
                           {"tcfg": {"name": "ci", "extend": "dev"}}]
                content[-1]["tcfg"][field] = "{tcfg:gen-var VALUE}"
                self.assert_failure(content, field, environment={"VALUE": "dev"})

    def test_output_metadata_rejects_absolute_paths_and_traversal(self):
        for field in ("name", "gen_file"):
            for value in ("../outside.toml", "/tmp/outside.toml", "part/../../outside.toml"):
                with self.subTest(field=field, value=value):
                    self.assert_failure({"tcfg": {"name": "dev", field: value}}, field)

    def test_selection_keeps_source_order_and_resolves_ancestors(self):
        document = [
            {"tcfg": {"name": "common", "generate": False, "gen_file": "shared.toml"},
             "first": 1},
            {"tcfg": {"name": "ci", "extend": "common"}, "second": 2},
            {"tcfg": {"name": "prod", "extend": "ci"}, "third": 3},
        ]
        results = self.resolve_document(document, sections=["prod", "ci"])
        self.assertEqual(list(results), ["ci", "prod"])
        self.assertEqual({name: item.gen_file for name, item in results.items()},
                         {"ci": "shared.toml", "prod": "shared.toml"})
        self.assertEqual(results["prod"].config, {"first": 1, "second": 2, "third": 3})
        selected = self.resolve_document(document, sections=["prod"])
        self.assertEqual(list(selected), ["prod"])
        self.assertEqual(selected["prod"], results["prod"])

    def test_explicit_unknown_or_suppressed_selection_fails(self):
        document = {"tcfg": {"name": "common", "generate": False}}
        for selected in ("missing", "common"):
            with self.subTest(selected=selected):
                self.assert_failure(document, selected, sections=[selected])

    def test_no_generating_sections_needs_no_external_values(self):
        self.assertEqual(self.resolve_document({
            "tcfg": {"name": "common", "generate": False, "import": "absent.toml"},
            "secret": "{tcfg:gen-var MISSING}",
        }), {})

    def test_unselected_section_semantics_are_not_evaluated(self):
        document = [
            {"tcfg": {"name": "dev"}, "value": 1},
            {"tcfg": {"name": "prod", "extend": "dev", "import": "absent.toml"},
             "value": "tcfg:unknown"},
        ]
        results = self.resolve_document(document, sections=["dev"])
        self.assertEqual(list(results), ["dev"])
        self.assertEqual(results["dev"].config, {"value": 1})

    def test_unselected_metadata_is_still_validated(self):
        self.assert_failure([
            {"tcfg": {"name": "dev"}},
            {"tcfg": {"name": "prod", "extend": "missing", "generate": False}},
        ], "prod", sections=["dev"])

    def test_selected_child_evaluates_suppressed_parent(self):
        self.assert_failure([
            {"tcfg": {"name": "common", "generate": False},
             "secret": "{tcfg:gen-var MISSING}"},
            {"tcfg": {"name": "prod", "extend": "common"}},
        ], "common", "secret", "MISSING", sections=["prod"])

    def test_recursive_merge_replaces_other_types_and_preserves_siblings(self):
        results = self.resolve_document([
            {"tcfg": {"name": "dev"}, "object": {"keep": 1, "change": 2},
             "array": [1, 2], "scalar": 3},
            {"tcfg": {"name": "ci", "extend": "dev"},
             "object": {"change": 5}, "array": [6], "scalar": {"new": 7}},
            {"tcfg": {"name": "prod", "extend": "dev"}, "object": 8, "array": []},
        ])
        self.assertEqual(results["dev"].config,
                         {"object": {"keep": 1, "change": 2}, "array": [1, 2], "scalar": 3})
        self.assertEqual(results["ci"].config,
                         {"object": {"keep": 1, "change": 5}, "array": [6],
                          "scalar": {"new": 7}})
        self.assertEqual(results["prod"].config, {"object": 8, "array": [], "scalar": 3})
        results["ci"].config["object"]["keep"] = 99
        self.assertEqual(results["dev"].config["object"]["keep"], 1)

    def test_imports_merge_in_order_then_local_values(self):
        self.write_toml("one.toml", {"data": {"value": 2, "one": True}})
        self.write_toml("two.toml", {"data": {"value": 3, "two": True}})
        results = self.resolve_document([
            {"tcfg": {"name": "dev"}, "data": {"value": 1, "parent": True}},
            {"tcfg": {"name": "ci", "extend": "dev", "import": ["one.toml", "two.toml"]},
             "data": {"value": 4}},
        ])
        self.assertEqual(results["ci"].config["data"],
                         {"value": 4, "parent": True, "one": True, "two": True})

    def test_section_import_rejects_invalid_toml(self):
        self.source.with_name("donor.toml").write_text("[1, 2]", encoding="utf-8")
        self.assert_failure({"tcfg": {"name": "dev", "import": "donor.toml"}},
                            "dev", "donor.toml")

    def test_property_import_merges_object_and_retains_other_toml_types(self):
        self.write_toml("donor.toml", {"object": {"new": 2}, "array": [3],
                                       "string": "text", "number": 4, "null": "null",
                                       "boolean": False})
        results = self.resolve_document([
            {"tcfg": {"name": "dev"}, "object": {"keep": 1}},
            {"tcfg": {"name": "ci", "extend": "dev"},
             **{key: f"tcfg:import donor.toml:/{key}"
                for key in ("object", "array", "string", "number", "null", "boolean")}},
        ])
        self.assertEqual(results["ci"].config,
                         {"object": {"keep": 1, "new": 2}, "array": [3], "string": "text",
                          "number": 4, "null": "null", "boolean": False})

    def test_imported_toml_instructions_and_placeholders_remain_literal(self):
        literal = {"remove": "tcfg:delete", "replace": {"tcfg:override": {"new": 2}},
                   "generation": "{tcfg:gen-var MISSING}",
                   "runtime": "{tcfg:run-var MISSING}", "import": "tcfg:import absent.toml"}
        self.write_toml("donor.toml", literal)
        result = self.resolve_document({
            "tcfg": {"name": "dev", "import": "donor.toml"},
            "nested": "tcfg:import donor.toml",
        })["dev"]
        self.assertEqual(result.config, {**literal, "nested": literal})

    def test_imported_override_wrapper_is_literal_during_recursive_merge(self):
        self.write_toml("donor.toml", {"node": {"tcfg:override": {"new": 2}}})
        results = self.resolve_document([
            {"tcfg": {"name": "dev"}, "node": {"keep": 1}},
            {"tcfg": {"name": "ci", "extend": "dev", "import": "donor.toml"}},
        ])
        self.assertEqual(results["ci"].config["node"],
                         {"keep": 1, "tcfg:override": {"new": 2}})

    def test_import_pointer_escapes_empty_key_arrays_and_colons(self):
        self.write_toml("archive.toml/markets.toml", {
            "a/b": {"~key": [{"": {"venue:spot": 42}}]}, "~1": "literal slash escape",
        })
        result = self.resolve_document({
            "tcfg": {"name": "dev"},
            "value": "tcfg:import archive.toml/markets.toml:/a~1b/~0key/0//venue:spot",
            "escape_order": "tcfg:import archive.toml/markets.toml:/~01",
        })["dev"]
        self.assertEqual(result.config, {"value": 42, "escape_order": "literal slash escape"})

    def test_invalid_pointers_fail(self):
        self.write_toml("donor.toml", {"items": ["one"], "scalar": 2})
        for pointer in ("missing_slash", "/absent", "/items/1", "/items/01", "/items/-",
                        "/items/-1", "/items/a", "/scalar/child", "/bad~2escape"):
            with self.subTest(pointer=pointer):
                self.assert_failure({"tcfg": {"name": "dev"},
                                     "value": f"tcfg:import donor.toml:{pointer}"},
                                    "dev", "value", "donor.toml")

    def test_relative_and_absolute_import_paths_use_source_location(self):
        donor = self.write_toml("library/donor.toml", {"items": [1, 2]})
        result = self.resolve_document({
            "tcfg": {"name": "dev"}, "relative": "tcfg:import library/donor.toml:/items",
            "absolute": f"tcfg:import {donor}:/items",
        })["dev"]
        self.assertEqual(result.config, {"relative": [1, 2], "absolute": [1, 2]})

    def test_import_path_can_contain_spaces(self):
        self.write_toml("config library/market data.toml", {"name": "BTC"})
        result = self.resolve_document({
            "tcfg": {"name": "dev"},
            "symbol": "tcfg:import config library/market data.toml:/name",
        })["dev"]
        self.assertEqual(result.config, {"symbol": "BTC"})

    def test_delete_removes_property_but_null_is_data(self):
        results = self.resolve_document([
            {"tcfg": {"name": "dev"}, "node": {"keep": 1, "remove": 2}, "null": 3},
            {"tcfg": {"name": "ci", "extend": "dev"},
             "node": {"remove": "tcfg:delete"}, "null": "null"},
        ])
        self.assertEqual(results["ci"].config, {"node": {"keep": 1}, "null": "null"})
        self.assertEqual(results["dev"].config["node"]["remove"], 2)

    def test_delete_missing_property_and_array_element_fail(self):
        for content in ({"missing": "tcfg:delete"}, {"array": ["tcfg:delete"]},
                        {"node": {"missing": "tcfg:delete"}}):
            with self.subTest(content=content):
                self.assert_failure({"tcfg": {"name": "dev"}, **content}, "dev")

    def test_override_replaces_whole_value_and_creates_missing_property(self):
        for replacement in ({"new": 2}, [3], "text", 4, False):
            with self.subTest(replacement=replacement):
                results = self.resolve_document([
                    {"tcfg": {"name": "dev"}, "existing": {"old": 1}},
                    {"tcfg": {"name": "ci", "extend": "dev"},
                     "existing": {"tcfg:override": replacement},
                     "absent": {"tcfg:override": replacement}},
                ])
                self.assertEqual(results["ci"].config,
                                 {"existing": replacement, "absent": replacement})

    def test_override_resolves_nested_imports_without_inherited_content(self):
        self.write_toml("donor.toml", {"symbols": ["BTC"]})
        results = self.resolve_document([
            {"tcfg": {"name": "dev"}, "subscription": {"old": True}},
            {"tcfg": {"name": "ci", "extend": "dev"},
             "subscription": {"tcfg:override": {"symbols": "tcfg:import donor.toml:/symbols"}}},
        ])
        self.assertEqual(results["ci"].config, {"subscription": {"symbols": ["BTC"]}})

    def test_malformed_override_and_unknown_instruction_fail(self):
        for value in ({"tcfg:override": {}, "extra": 1}, "tcfg:unknown value",
                      {"tcfg:unknown": 1}, "tcfg:import"):
            with self.subTest(value=value):
                self.assert_failure({"tcfg": {"name": "dev"}, "value": value},
                                    "dev", "value")

    def test_generation_substitution_preserves_text_and_string_type(self):
        result = self.resolve_document({
            "tcfg": {"name": "dev"},
            "value": "{tcfg:gen-var COUNT}",
            "path": "{tcfg:gen-var ROOT}/{tcfg:gen-var NAME}/{tcfg:gen-var NAME}",
            "nested": [{"value": "{tcfg:gen-var EMPTY}"}],
            "runtime": "{tcfg:run-var UNSET}",
            "both": "{tcfg:gen-var ROOT}/{tcfg:run-var UNSET}",
        }, environment={"COUNT": "42", "ROOT": "/srv", "NAME": "data", "EMPTY": ""})["dev"]
        self.assertEqual(result.config,
                         {"value": "42", "path": "/srv/data/data", "nested": [{"value": ""}],
                          "runtime": "{tcfg:run-var UNSET}",
                          "both": "/srv/{tcfg:run-var UNSET}"})

    def test_generation_placeholders_in_section_and_property_imports(self):
        donor = self.write_toml("library/donor.toml", {"value": 7})
        result = self.resolve_document({
            "tcfg": {"name": "dev", "import": "{tcfg:gen-var LIB}/donor.toml"},
            "other": "tcfg:import {tcfg:gen-var LIB}/donor.toml:/value",
        }, environment={"LIB": str(donor.parent)})["dev"]
        self.assertEqual(result.config, {"value": 7, "other": 7})

    def test_substitution_does_not_interpret_inserted_text(self):
        for text in ("{tcfg:gen-var MISSING}", "tcfg:delete", "tcfg:import absent.toml"):
            with self.subTest(text=text):
                result = self.resolve_document({
                    "tcfg": {"name": "dev"}, "value": "{tcfg:gen-var TEXT}",
                }, environment={"TEXT": text})["dev"]
                self.assertEqual(result.config, {"value": text})

    def test_missing_generation_variable_fails_with_context(self):
        self.assert_failure({"tcfg": {"name": "dev"},
                             "connection": {"token": "{tcfg:gen-var MISSING}"}},
                            "dev", "connection", "token", "MISSING")

    def test_malformed_placeholders_fail_in_authored_values(self):
        for value in ("{tcfg:gen-var}", "{tcfg:gen-var NAME", "{tcfg:run-var}",
                      "{tcfg:unknown NAME}"):
            with self.subTest(value=value):
                self.assert_failure({"tcfg": {"name": "dev"}, "value": value},
                                    "dev", "value")

    def test_runtime_placeholders_cannot_resolve_import_paths(self):
        for content in (
            {"tcfg": {"name": "dev", "import": "{tcfg:run-var LIB}/donor.toml"}},
            {"tcfg": {"name": "dev"},
             "value": "tcfg:import {tcfg:run-var LIB}/donor.toml"},
        ):
            with self.subTest(content=content):
                self.assert_failure(content, "dev", environment={"LIB": str(self.directory)})

    def test_default_environment_and_explicit_environment_are_distinct(self):
        content = {"tcfg": {"name": "dev"}, "value": "{tcfg:gen-var TCFG_TEST_VALUE}"}
        self.write_toml(self.source.name, content)
        with patch.dict("os.environ", {"TCFG_TEST_VALUE": "from environment"}, clear=True):
            result = generate_configs(str(self.source))["dev"]
            self.assertEqual(result.config["value"], "from environment")
            self.assert_failure(content, "TCFG_TEST_VALUE", environment={})
            result = generate_configs(self.source, environment={"TCFG_TEST_VALUE": "explicit"})["dev"]
            self.assertEqual(result.config["value"], "explicit")

    def test_missing_import_reports_source_section_property_and_donor(self):
        self.assert_failure({"tcfg": {"name": "dev"},
                             "connection": "tcfg:import missing.toml"},
                            "dev", "connection", "missing.toml")

    def test_invalid_source_toml_is_config_error(self):
        self.source.write_text('{"tcfg":', encoding="utf-8")
        with self.assertRaises(config_error) as caught:
            generate_configs(self.source, environment={})
        self.assertIn(self.source.name, str(caught.exception))

    def test_invalid_donor_toml_reports_import_context(self):
        self.source.with_name("donor.toml").write_text('{"missing":', encoding="utf-8")
        self.assert_failure({"tcfg": {"name": "dev"}, "value": "tcfg:import donor.toml"},
                            "dev", "value", "donor.toml")

    def test_missing_source_is_config_error(self):
        with self.assertRaises(config_error) as caught:
            generate_configs(self.source, environment={})
        self.assertIn(self.source.name, str(caught.exception))

    def test_resolution_does_not_write_or_change_files(self):
        self.write_toml("donor.toml", {"value": 1})
        self.write_toml(self.source.name, {"tcfg": {"name": "dev", "import": "donor.toml"}})
        before = {path: path.read_bytes() for path in self.directory.rglob("*") if path.is_file()}
        generate_configs(self.source, environment={})
        after = {path: path.read_bytes() for path in self.directory.rglob("*") if path.is_file()}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
