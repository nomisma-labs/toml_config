# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Check publication failures through the public command-line entry point."""

from contextlib import redirect_stderr
import io
import tomllib
from tools.toml_config import toml_codec
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.toml_config.tcfggen import main


class publication_tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.source = self.directory / "app_tcfg.toml"
        self.outputs = self.directory / "genconfig"
        self.source.write_text(toml_codec.dumps({"sections": [
            {"tcfg": {"name": "dev"}, "value": "new-dev"},
            {"tcfg": {"name": "prod", "extend": "dev"}, "value": "new-prod"},
        ]}), encoding="utf-8")
        for section in ("dev", "prod"):
            path = self.outputs / section / "app.toml"
            path.parent.mkdir(parents=True)
            path.write_text(toml_codec.dumps({"value": f"old-{section}"}), encoding="utf-8")
        self.previous = self.files()

    def files(self):
        return {path.relative_to(self.outputs).as_posix(): path.read_bytes()
                for path in self.outputs.rglob("*") if path.is_file()}

    def assert_cli_failure(self, diagnostic):
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = main(["--source", str(self.source), "--output-dir", str(self.outputs)])
        self.assertNotEqual(result, 0)
        self.assertIn(diagnostic, errors.getvalue())
        self.assertNotIn("Traceback (most recent call last)", errors.getvalue())

    def test_later_staging_failure_preserves_destinations_and_removes_temporary_files(self):
        create_temporary = tempfile.NamedTemporaryFile
        calls = 0

        def fail_second_temporary(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated staging failure")
            return create_temporary(*args, **kwargs)

        with patch("tools.toml_config.tcfggen.tempfile.NamedTemporaryFile", side_effect=fail_second_temporary):
            self.assert_cli_failure("simulated staging failure")
        self.assertEqual(calls, 2)
        self.assertEqual(self.files(), self.previous)

    def test_later_replace_failure_leaves_complete_toml_and_no_temporary_files(self):
        replace = os.replace
        calls = 0

        def fail_second_replace(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated replacement failure")
            return replace(*args, **kwargs)

        with patch("tools.toml_config.tcfggen.os.replace", side_effect=fail_second_replace):
            self.assert_cli_failure("simulated replacement failure")
        self.assertEqual(calls, 2)
        remaining = self.files()
        self.assertEqual(set(remaining), set(self.previous))
        self.assertIn(tomllib.loads(remaining["dev/app.toml"].decode("utf-8")),
                      [{"value": "old-dev"}, {"value": "new-dev"}])
        self.assertEqual(remaining["prod/app.toml"], self.previous["prod/app.toml"])

    def test_older_python_symlink_loop_error_has_a_clean_diagnostic(self):
        with patch.object(Path, "resolve", side_effect=RuntimeError("Symlink loop from '/loop'")):
            self.assert_cli_failure("Symlink loop")
        self.assertEqual(self.files(), self.previous)


if __name__ == "__main__":
    unittest.main()
