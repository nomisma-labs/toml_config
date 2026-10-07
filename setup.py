# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Read package metadata from the repository's single version declaration."""

from pathlib import Path
import re

from setuptools import setup

source = (Path(__file__).parent / "CMakeLists.txt").read_text(encoding="utf-8")
match = re.search(r"project\(toml_config\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)", source)
if match is None:
    raise RuntimeError("Cannot read toml_config version from CMakeLists.txt")
setup(version=match.group(1))
