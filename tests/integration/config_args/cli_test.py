# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT
"""Check application arguments remaining after the framework's config parser."""

import tomllib
import sys
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


repository = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repository))
from tools.toml_config import toml_codec  # noqa: E402


class config_args_example_tests(unittest.TestCase):
    def setUp(self):
        self.executable = os.environ["TCFG_APP_TEST_EXECUTABLE"]
        directory = tempfile.TemporaryDirectory(prefix="tcfg_app_cli_test_")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.config = self.write_config("app.toml", {"greeting": "Hello"})
        self.environment = dict(os.environ)
        self.environment.pop("NOM_CONFIG", None)
        self.environment.pop("NOM_CONFIG_DIR", None)

    def write_config(self, name, document):
        path = self.directory / name
        path.write_text(toml_codec.dumps(document), encoding="utf-8")
        return path

    def run_app(self, *arguments, success=True):
        result = subprocess.run(
            [self.executable, *map(str, arguments)],
            cwd=self.directory, env=self.environment,
            capture_output=True, text=True, check=False, timeout=20,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(result.stderr.strip(), "failure should explain its cause")
        return result

    def test_application_defaults(self):
        result = self.run_app("--config", self.config)
        self.assertEqual(result.stdout, "Hello, world!\n")

    def test_interleaved_config_and_application_options(self):
        result = self.run_app(
            "--name", "Alex", "--config", self.config,
            "--count", "2", "--set", "/greeting=Welcome", "--verbose",
        )
        self.assertEqual(result.stdout, "Greeting count: 2\nWelcome, Alex!\nWelcome, Alex!\n")

    def test_adjacent_option_values(self):
        result = self.run_app(
            f"--config={self.config}", "--name=Alex", "--set=/greeting=Hi", "--count=2",
        )
        self.assertEqual(result.stdout, "Hi, Alex!\nHi, Alex!\n")

    def test_short_application_flag_and_positional_name(self):
        result = self.run_app("--config", self.config, "-v", "Alex")
        self.assertEqual(result.stdout, "Greeting count: 1\nHello, Alex!\n")

    def test_marker_passes_config_looking_name_to_application(self):
        result = self.run_app("--config", self.config, "--", "--set")
        self.assertEqual(result.stdout, "Hello, --set!\n")

    def test_help_precedes_config_loading(self):
        malformed = self.directory / "malformed.toml"
        malformed.write_text("{", encoding="utf-8")
        for config in (self.directory / "missing.toml", malformed):
            for help_option in ("--help", "-h"):
                with self.subTest(config=config, help_option=help_option):
                    result = self.run_app("--config", config, help_option)
                    for option in ("--config", "--set", "--check-config", "--name", "--count", "--verbose",
                                   "-c", "-k", "-h", "full", "view", "silent"):
                        self.assertIn(option, result.stdout)
                    self.assertNotIn("Hello,", result.stdout)
                    self.assertEqual(result.stderr, "")

    def test_application_errors_precede_config_loading(self):
        missing = self.directory / "missing.toml"
        cases = [
            ["--unknown-app-option"],
            ["--count", "0"],
            ["--count", "-1"],
            ["--count", "many"],
            ["--name="],
            ["Alex", "Sam"],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.run_app("--config", missing, *arguments, success=False)
                self.assertNotIn(str(missing), result.stderr)
                self.assertNotIn("Config location", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_check_config_exits_before_application_work(self):
        result = self.run_app(
            "--config", self.config, "--name", "Alex", "--verbose",
            "--set", "/greeting=Hi", "--check-config",
        )
        self.assertIn(f"Config OK (command line): {self.config}\n", result.stdout)
        self.assertEqual(tomllib.loads(result.stdout.split("Configuration:\n", 1)[1]), {"greeting": "Hi"})
        self.assertNotIn("Greeting count:", result.stdout)
        self.assertNotIn("Hi, Alex!", result.stdout)

    def test_check_modes_with_short_options_and_application_arguments(self):
        for arguments, expected in (
                (("-k", "view", "-v", "Alex"), 'greeting = "Hello"'),
                (("-ksilent", "Alex"), "OK\n"),
                (("--check-config=silent", "--", "view"), "OK\n")):
            with self.subTest(arguments=arguments):
                result = self.run_app("-c", self.config, *arguments)
                if expected == "OK\n":
                    self.assertEqual(result.stdout, expected)
                else:
                    self.assertEqual(tomllib.loads(result.stdout), tomllib.loads(expected))
                self.assertEqual(result.stderr, "")

        result = self.run_app(f"-c{self.config}", "-k", "Alex", "-v")
        self.assertIn("Config lookup:\n", result.stdout)
        self.assertNotIn("Hello, Alex!", result.stdout)

    def test_unknown_check_mode_precedes_config_loading(self):
        result = self.run_app("-c", self.directory / "missing.toml", "--check-config=brief", success=False)
        self.assertIn("Config arguments", result.stderr)
        self.assertIn("full, view, or silent", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_config_failures_still_reach_framework_diagnostics(self):
        malformed = self.directory / "malformed.toml"
        malformed.write_text("{", encoding="utf-8")
        result = self.run_app("--config", malformed, "--name", "Alex", success=False)
        self.assertIn("Config parsing", result.stderr)
        self.assertIn(str(malformed), result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
