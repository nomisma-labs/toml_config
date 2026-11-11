# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: MIT
"""Run the comprehensive tcfg example through its C++ application."""

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
expected_configs = repository / "docs/toml_config/examples/complete_config/genconfig"


class md_capture_tests(unittest.TestCase):
    def setUp(self):
        self.executable = os.environ["TCFG_MD_CAPTURE_TEST_EXECUTABLE"]
        self.collected = Path(os.environ["TCFG_MD_CAPTURE_TEST_CONFIG_DIR"])
        self.generated = Path(os.environ["TCFG_MD_CAPTURE_TEST_GENCONFIG_DIR"])
        directory = tempfile.TemporaryDirectory(prefix="tcfg_md_capture_test_")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.environment = dict(os.environ)
        self.environment.pop("NOM_CONFIG", None)
        self.environment.pop("NOM_CONFIG_DIR", None)

    def run_app(self, config, *arguments, success=True):
        result = subprocess.run(
            [self.executable, "--config", str(config), *arguments],
            cwd=self.directory, env=self.environment,
            capture_output=True, text=True, check=False, timeout=20,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
        else:
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn(str(config), result.stderr)
        return result

    def test_all_sections_use_the_documented_settings(self):
        snapshots = sorted(expected_configs.glob("*/*.toml"))
        self.assertEqual(len(snapshots), 4)
        for snapshot in snapshots:
            with self.subTest(section=snapshot.parent.name):
                expected = tomllib.loads(snapshot.read_text(encoding="utf-8"))
                config = self.generated / snapshot.relative_to(expected_configs)
                self.assertEqual(tomllib.loads(config.read_text(encoding="utf-8")), expected)
                result = self.run_app(config)
                connection = expected["connection"]
                subscription = expected["subscription"]
                settings = [
                    "Capture initialized",
                    f"Stream: {connection['address']}",
                    f"Snapshot: {connection['snapshot']['address']}",
                    f"Timeout: {connection['timeout_s']} seconds",
                    f"Symbols: {' '.join(subscription['symbols'])}",
                    f"Channels: {' '.join(subscription['channels'])}",
                    f"Log: {expected['log']['level']}",
                    f"Log file: {expected['log'].get('file', '(console)')}",
                    f"Market data file: {expected['md_log']['file']}",
                ]
                for setting in settings:
                    self.assertIn(setting, result.stdout.splitlines())

    def test_check_config_stops_before_capture_initialization(self):
        for snapshot in sorted(expected_configs.glob("*/*.toml")):
            with self.subTest(section=snapshot.parent.name):
                config = self.generated / snapshot.relative_to(expected_configs)
                result = self.run_app(config, "--check-config")
                self.assertIn(f"Config OK (command line): {config}\n", result.stdout)
                expected = tomllib.loads(snapshot.read_text(encoding="utf-8"))
                self.assertEqual(tomllib.loads(result.stdout.split("Configuration:\n", 1)[1]), expected)
                self.assertNotIn("Capture initialized", result.stdout)

    def test_view_and_silent_modes(self):
        config = self.generated / "prod/md_capture.toml"
        result = self.run_app(config, "-kview", "--set", "/connection/timeout_s=11")
        expected = tomllib.loads(config.read_text(encoding="utf-8"))
        expected["connection"]["timeout_s"] = 11
        self.assertEqual(tomllib.loads(result.stdout), expected)
        self.assertEqual(self.run_app(config, "-k", "silent").stdout, "OK\n")

    def test_ordinary_development_config_loads_directly(self):
        result = self.run_app(self.collected / "md_capture.toml")
        self.assertIn("Stream: wss://dev.example/ws\n", result.stdout)
        self.assertIn("Symbols: btcusdt\n", result.stdout)

    def test_nested_overrides_reach_the_application(self):
        result = self.run_app(self.generated / "prod/md_capture.toml",
                              "--set", "/connection/timeout_s=11", "--set", "/log/level=info")
        self.assertIn("Timeout: 11 seconds\n", result.stdout)
        self.assertIn("Log: info\n", result.stdout)

    def test_invalid_numeric_mapping_reports_the_nested_path(self):
        config = self.directory / "invalid.toml"
        document = tomllib.loads((self.generated / "prod/md_capture.toml").read_text(encoding="utf-8"))
        document["connection"]["timeout_s"] = 1.5
        config.write_text(toml_codec.dumps(document), encoding="utf-8")
        result = self.run_app(config, "--check-config", success=False)
        for detail in ("Config mapping", "/connection/timeout_s", "1.5"):
            self.assertIn(detail, result.stderr)

    def test_nested_validation_reports_complete_paths(self):
        source = (self.generated / "prod/md_capture.toml").read_text(encoding="utf-8")
        cases = (
            ("/connection/address", ""),
            ("/connection/snapshot/address", ""),
            ("/connection/timeout_s", 0),
            ("/subscription/symbols", []),
            ("/subscription/channels", []),
            ("/log/level", "invalid"),
            ("/log/file", ""),
            ("/md_log/file", ""),
        )
        for pointer, value in cases:
            with self.subTest(pointer=pointer):
                document = tomllib.loads(source)
                target = document
                *parents, key = pointer.removeprefix("/").split("/")
                for parent in parents:
                    target = target[parent]
                target[key] = value
                config = self.directory / "invalid.toml"
                config.write_text(toml_codec.dumps(document), encoding="utf-8")
                result = self.run_app(config, "--check-config", success=False)
                self.assertIn("Config validation", result.stderr)
                self.assertIn(pointer, result.stderr)


if __name__ == "__main__":
    unittest.main()
