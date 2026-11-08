# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Generate the sample configs and exercise the real application's startup boundary."""

import tomllib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


repository = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repository))
from tools.toml_config import toml_codec  # noqa: E402


class config_workflow_example_tests(unittest.TestCase):
    def setUp(self):
        self.executable = os.environ["TCFG_WORKFLOW_TEST_EXECUTABLE"]
        directory = tempfile.TemporaryDirectory(prefix="tcfg_workflow_test_")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.generated = self.directory / "genconfig"
        self.environment = dict(os.environ)
        self.environment.pop("NOM_CONFIG", None)
        self.environment.pop("NOM_CONFIG_DIR", None)

        result = subprocess.run(
            [sys.executable, str(repository / "tools/toml_config/tcfggen.py"),
             "--source", str(repository / "apps/config_workflow_example/config/config_workflow_example_tcfg.toml"),
             "--output-dir", str(self.generated)],
            cwd=self.directory, env=self.environment,
            capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def config_path(self, section):
        return self.generated / section / "config_workflow_example.toml"

    def run_app(self, *arguments, success=True):
        result = subprocess.run(
            [self.executable, *map(str, arguments)],
            cwd=self.directory, env=self.environment,
            capture_output=True, text=True, check=False, timeout=20,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
        else:
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "", "failed config must not initialize the application")
            self.assertTrue(result.stderr.strip(), "failure should explain its cause")
        return result

    def test_generated_sections_initialize_with_their_selected_values(self):
        for section, timeout in (("dev", 10), ("prod", 30)):
            with self.subTest(section=section):
                config = self.config_path(section)
                result = self.run_app("--config", config)
                self.assertEqual(result.stdout,
                                 f"Config OK (command line): {config}\n"
                                 f"Application initialized; timeout: {timeout} seconds\n")

    def test_check_config_exits_before_application_initialization(self):
        for section in ("dev", "prod"):
            with self.subTest(section=section):
                config = self.config_path(section)
                result = self.run_app("--config", config, "--check-config")
                self.assertIn(f"Config OK (command line): {config}\n", result.stdout)
                self.assertIn(f"Selected candidate: {config}\n", result.stdout)
                expected = tomllib.loads(config.read_text(encoding="utf-8"))
                self.assertEqual(tomllib.loads(result.stdout.split("Configuration:\n", 1)[1]), expected)
                self.assertNotIn("Application initialized", result.stdout)

    def test_generated_section_is_found_through_the_config_key(self):
        self.environment["NOM_CONFIG_DIR"] = str(self.generated / "prod")
        result = self.run_app("--check-config")
        self.assertIn(f"Config OK (NOM_CONFIG_DIR): {self.config_path('prod')}\n", result.stdout)
        self.assertIn(f"Search directory: {self.generated / 'prod'}\n", result.stdout)
        self.assertIn("Config key: config_workflow_example\n", result.stdout)
        self.assertEqual(tomllib.loads(result.stdout.split("Configuration:\n", 1)[1])["timeout_s"], 30)

    def test_view_normalizes_runtime_values_overrides_and_cpp_defaults(self):
        config = self.directory / "runtime.toml"
        document = {"endpoint": "{tcfg:run-var TEST_ENDPOINT}", "timeout_s": 1, "unused": "ignored"}
        original = toml_codec.dumps(document)
        config.write_text(original, encoding="utf-8")
        self.environment["TEST_ENDPOINT"] = "https://runtime.example/feed"
        result = self.run_app("-c", config, "--set", "/timeout_s=12", "--set", "/timeout_s=20", "-k", "view")
        self.assertEqual(tomllib.loads(result.stdout), {
            "endpoint": "https://runtime.example/feed", "timeout_s": 20,
            "enabled": True,
        })
        self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_silent_check_prints_only_ok(self):
        for option in ("--check-config=silent", "-ksilent"):
            with self.subTest(option=option):
                result = self.run_app("-c", self.config_path("dev"), option)
                self.assertEqual(result.stdout, "OK\n")

    def test_help_precedes_config_loading(self):
        for option in ("--help", "-h"):
            with self.subTest(option=option):
                result = self.run_app("-c", self.directory / "missing.toml", option)
                for detail in ("--config", "--set", "--check-config", "-c", "-k", "full", "view", "silent"):
                    self.assertIn(detail, result.stdout)

    def test_command_line_override_reaches_application_initialization(self):
        result = self.run_app("--config", self.config_path("prod"), "--set", "/timeout_s=20")
        self.assertIn("Application initialized; timeout: 20 seconds\n", result.stdout)

    def test_mapping_failure_reports_the_file_pointer_and_value(self):
        config = self.config_path("prod")
        document = tomllib.loads(config.read_text(encoding="utf-8"))
        document["timeout_s"] = 1.5
        config.write_text(toml_codec.dumps(document), encoding="utf-8")
        result = self.run_app("--config", config, "--check-config", success=False)
        for detail in ("Config mapping", str(config), "/timeout_s", "1.5"):
            self.assertIn(detail, result.stderr)

    def test_validation_failure_prevents_both_check_and_normal_startup(self):
        config = self.config_path("prod")
        for arguments in ((), ("--check-config",), ("--check-config=view",), ("--check-config=silent",)):
            with self.subTest(arguments=arguments):
                result = self.run_app("--config", config, "--set", "/timeout_s=0",
                                      *arguments, success=False)
                for detail in ("Config validation", str(config), "timeout_s must be positive"):
                    self.assertIn(detail, result.stderr)


if __name__ == "__main__":
    unittest.main()
