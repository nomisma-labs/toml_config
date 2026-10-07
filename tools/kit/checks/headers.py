#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Checks that every source file starts with the SPDX header (after an optional shebang).

Covers the C++, CMake, Python, shell, YAML and Docker files git knows about (tracked, or new
and not ignored). Submodule contents are not ours and are skipped. JSON can't carry comments
and Markdown is documentation, so both are exempt.
"""

import subprocess
import sys
from pathlib import Path

# The header, without its comment marker. Also used by tools/kit/add_sandbox_app.py.
HEADER_LINES = [
    "SPDX-FileCopyrightText: 2026 Alexey Tkachenko",
    "SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary",
]

MARKER_BY_SUFFIX = {
    ".h": "//", ".hpp": "//", ".ipp": "//", ".cpp": "//", ".cxx": "//", ".cppm": "//",
    ".cmake": "#", ".in": "#", ".py": "#", ".sh": "#", ".yml": "#", ".yaml": "#",
}
MARKER_BY_NAME = {"CMakeLists.txt": "#", "Dockerfile": "#", ".clang-tidy": "#", ".clangd": "#"}


def comment_marker(path: Path) -> str | None:
    return MARKER_BY_NAME.get(path.name) or MARKER_BY_SUFFIX.get(path.suffix)


def has_header(path: Path, marker: str) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("#!"):
        lines = lines[1:]
    tags = [line.split(":", 1)[0] for line in HEADER_LINES]
    return len(lines) >= len(tags) and all(line.startswith(f"{marker} {tag}:") for line, tag in zip(lines, tags))


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    missing = []
    for name in listed:
        path = root / name
        marker = comment_marker(path)
        if marker and path.is_file() and not has_header(path, marker):
            missing.append(name)
    for name in missing:
        print(f"missing SPDX header: {name}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
