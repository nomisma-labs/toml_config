# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Exercise TOML startup, discovery, typed validation, and relocatable configs."""

from __future__ import annotations

import argparse
import copy
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


class application_test(unittest.TestCase):
    app: Path
    source: Path

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="toml_application_")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.unrelated = self.directory / "unrelated working directory"
        self.unrelated.mkdir()
        self.environment = dict(os.environ)
        for key in ("TCFG_CONFIG", "TCFG_CONFIG_DIR", "CAPTURE_API_KEY"):
            self.environment.pop(key, None)
        self.environment["PYTHONPATH"] = str(self.source / "python")
        self.config_directory = self.source / "apps/capture_example/config"
        self.entry = self.config_directory / "capture_example.toml"
        self.tcfg_entry = self.config_directory / "capture_example.tcfg"
        self.expected = self.api.load(self.tcfg_entry, environment={}).values

    def run_app(self, *arguments, app: Path | None = None, environment: dict | None = None,
                cwd: Path | None = None, expected_code: int = 0) -> subprocess.CompletedProcess:
        process = subprocess.run([str(app or self.app), *map(str, arguments)],
                                 cwd=cwd or self.unrelated,
                                 env=self.environment if environment is None else environment,
                                 text=True, capture_output=True, check=False)
        self.assertEqual(process.returncode, expected_code,
                         f"arguments={arguments!r}\nstdout={process.stdout}\nstderr={process.stderr}")
        if expected_code:
            self.assertNotIn("Traceback", process.stderr)
        return process

    def write_toml(self, path: Path, values: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.api.dumps(values), encoding="utf-8")
        return path

    def generate(self, source: Path, output: Path, *, environment: dict | None = None) -> Path:
        process = subprocess.run([sys.executable, str(self.source / "cfggen.py"),
                                  str(source), "-o", str(output)],
                                 cwd=self.unrelated,
                                 env=self.environment if environment is None else environment,
                                 text=True, capture_output=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        return output

    def deploy(self, name: str = "prefix") -> tuple[Path, Path]:
        prefix = self.directory / name
        executable = prefix / "bin/capture_example"
        executable.parent.mkdir(parents=True)
        shutil.copy2(self.app, executable)
        shutil.copytree(self.config_directory, prefix / "config/capture_example")
        return prefix, executable

    def test_checked_in_and_python_generated_toml_agree(self):
        generated = self.generate(self.tcfg_entry, self.directory / "generated config.toml")
        collected = self.run_app("--config", self.entry, "--print-config")
        baked = self.run_app(f"--config={generated}", "--print-config")
        self.assertEqual(tomllib.loads(collected.stdout), self.expected)
        self.assertEqual(tomllib.loads(baked.stdout), self.expected)
        checked = self.run_app("-c", generated, "--check-config")
        self.assertEqual(checked.stdout, "Configuration valid\n")
        self.assertNotIn("Endpoint:", checked.stdout)

    def test_tcfg_requires_python_generation_before_cpp_loading(self):
        process = self.run_app("--config", self.tcfg_entry, "--check-config", expected_code=2)
        self.assertIn(".toml", process.stderr)
        self.assertNotIn("Endpoint:", process.stdout)

    def test_typed_binding_and_domain_validation_precede_startup(self):
        invalid_values = [
            ("timeout_ms", -1), ("timeout_ms", 0), ("symbols", []),
            ("reconnect_delay_ms", -1), ("timeout_ms", "wrong type"),
        ]
        for index, (key, value) in enumerate(invalid_values):
            with self.subTest(key=key, value=value):
                values = copy.deepcopy(self.expected)
                values["feed"][key] = value
                source = self.write_toml(self.directory / f"invalid_{index}.toml", values)
                process = self.run_app("--config", source, "--check-config", expected_code=2)
                self.assertNotIn("Endpoint:", process.stdout)
                self.assertNotIn("Configuration valid", process.stdout)
        missing = copy.deepcopy(self.expected)
        del missing["feed"]["endpoint"]
        source = self.write_toml(self.directory / "missing_required.toml", missing)
        process = self.run_app("--config", source, "--check-config", expected_code=2)
        self.assertIn("binding", process.stderr)
        self.assertIn("endpoint", process.stderr)
        self.assertNotIn("Endpoint:", process.stdout)

    def test_build_tree_discovery_ignores_unrelated_working_directory(self):
        (self.unrelated / "capture_example.toml").write_text("invalid TOML", encoding="utf-8")
        process = self.run_app("--print-config")
        self.assertEqual(tomllib.loads(process.stdout), self.expected)
        process = self.run_app()
        self.assertIn("Timeout: 2000 ms", process.stdout)
        self.assertIn("Reconnect delay: 1000 ms", process.stdout)
        self.assertIn("Config:", process.stdout)
        self.assertNotIn(str(self.unrelated), process.stdout)

    def test_collected_toml_deployment_survives_relocation(self):
        prefix, executable = self.deploy("first prefix")
        self.assertFalse((prefix / "generated_config").exists())
        resolved = self.run_app("--print-config", app=executable)
        self.assertEqual(tomllib.loads(resolved.stdout), self.expected)
        destination = self.directory / "relocated prefix"
        shutil.move(str(prefix), destination)
        moved_executable = destination / "bin/capture_example"
        resolved = self.run_app("--print-config", app=moved_executable)
        self.assertEqual(tomllib.loads(resolved.stdout), self.expected)
        summary = self.run_app(app=moved_executable)
        self.assertIn(str(destination / "config/capture_example/capture_example.toml"), summary.stdout)
        self.assertIn(str(destination / "config/capture_example/data"), summary.stdout)
        self.assertFalse((destination / "config/capture_example/data").exists())

    def test_automatic_discovery_ignores_tcfg_inputs(self):
        prefix, executable = self.deploy()
        (prefix / "config/capture_example/capture_example.toml").unlink()
        self.run_app("--check-config", app=executable, expected_code=2)

    def test_path_launch_through_renamed_symlink_uses_actual_executable(self):
        prefix, executable = self.deploy()
        launch_directory = self.directory / "launchers"
        launch_directory.mkdir()
        (launch_directory / "capture_alias").symlink_to(executable)
        environment = dict(self.environment, PATH=str(launch_directory))
        process = self.run_app("--print-config", app=Path("capture_alias"), environment=environment)
        self.assertEqual(tomllib.loads(process.stdout), self.expected)
        process = self.run_app(app=Path("capture_alias"), environment=environment)
        self.assertIn(str(prefix / "config/capture_example/capture_example.toml"), process.stdout)

    def test_environment_file_selection_and_explicit_precedence(self):
        generation_environment = dict(self.environment, CAPTURE_API_KEY="integration-example-token")
        generated = self.generate(self.config_directory / "debug.tcfg", self.directory / "debug.toml",
                                  environment=generation_environment)
        environment = dict(self.environment, TCFG_CONFIG=str(generated))
        resolved = self.run_app("--print-config", environment=environment)
        values = tomllib.loads(resolved.stdout)
        self.assertEqual(values["log"]["level"], "debug")
        self.assertEqual(values["feed"]["api_key"], "integration-example-token")
        self.assertEqual(values["feed"]["reconnect_delay_ms"], 250)
        explicit = self.run_app("--config", self.entry, "--print-config", environment=environment)
        self.assertEqual(tomllib.loads(explicit.stdout), self.expected)
        for selected in ["", str(self.directory / "missing.toml"), str(self.tcfg_entry)]:
            with self.subTest(selected=selected):
                self.run_app("--check-config", environment=dict(self.environment, TCFG_CONFIG=selected),
                             expected_code=2)
        relative = self.write_toml(self.unrelated / "selected.toml", self.expected)
        resolved = self.run_app("--print-config", environment=dict(self.environment, TCFG_CONFIG=relative.name))
        self.assertEqual(tomllib.loads(resolved.stdout), self.expected)

    def test_search_directories_are_executable_relative_and_ordered(self):
        prefix, executable = self.deploy()
        first = copy.deepcopy(self.expected)
        first["feed"]["timeout_ms"] = 101
        self.write_toml(prefix / "alternate/capture_example/capture_example.toml", first)
        second = copy.deepcopy(self.expected)
        second["feed"]["timeout_ms"] = 202
        self.write_toml(prefix / "environment/capture_example.toml", second)
        environment = dict(self.environment, TCFG_CONFIG_DIR=os.pathsep + "../environment" + os.pathsep)
        resolved = self.run_app("--config-dir", "../missing", "--config-dir=../alternate", "--print-config",
                                app=executable, environment=environment)
        self.assertEqual(tomllib.loads(resolved.stdout)["feed"]["timeout_ms"], 101)
        resolved = self.run_app("--print-config", app=executable, environment=environment)
        self.assertEqual(tomllib.loads(resolved.stdout)["feed"]["timeout_ms"], 202)
        adjacent = copy.deepcopy(self.expected)
        adjacent["feed"]["timeout_ms"] = 303
        self.write_toml(prefix / "bin/capture_example.toml", adjacent)
        (prefix / "bin/capture_example.tcfg").write_text("invalid TOML", encoding="utf-8")
        resolved = self.run_app("--print-config", app=executable)
        self.assertEqual(tomllib.loads(resolved.stdout)["feed"]["timeout_ms"], 303)

    def test_composition_flags_are_rejected_and_print_mode_takes_precedence(self):
        for flag in ["--overlay", "--overlay=extra.toml", "--set", "--set=feed.timeout_ms = 400"]:
            with self.subTest(flag=flag):
                process = self.run_app("--config", self.entry, flag, expected_code=2)
                self.assertIn("unknown argument", process.stderr)
        resolved = self.run_app("-c", self.entry, "--check-config", "--print-config")
        self.assertEqual(tomllib.loads(resolved.stdout), self.expected)
        checked = self.run_app("--config", self.entry, "--check-config")
        self.assertEqual(checked.stdout, "Configuration valid\n")

    def test_help_and_argument_errors(self):
        empty_prefix = self.directory / "empty_prefix/bin"
        empty_prefix.mkdir(parents=True)
        executable = empty_prefix / "capture_example"
        shutil.copy2(self.app, executable)
        for flag in ["--help", "-h"]:
            with self.subTest(flag=flag):
                help_text = self.run_app(flag, app=executable).stdout
                for option in ["--config", "--config-dir", "--print-config", "--check-config"]:
                    self.assertIn(option, help_text)
                self.assertNotIn("--overlay", help_text)
                self.assertNotIn("--set", help_text)
        for arguments in [("--unknown",), ("--config", ""),
                          ("--config", self.entry, "-c", self.entry), ("--", "--check-config")]:
            with self.subTest(arguments=arguments):
                self.run_app(*arguments, expected_code=2)
        self.run_app("--check-config", app=executable, expected_code=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    arguments = parser.parse_args()
    application_test.app = arguments.app.resolve()
    application_test.source = arguments.source.resolve()
    sys.path.insert(0, str(application_test.source / "python"))
    application_test.api = importlib.import_module("toml_config")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(application_test)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
