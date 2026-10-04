#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Pulls template-owned files from cmake_template into this repo.

    python3 tools/sync_template.py [--to <commit or tag>] [--template-url <url>]

Compares the template-owned paths between the template commit recorded in .template_ref and
the template's newest commit (or --to), applies the difference with `git apply --3way` and
records the new commit. The result is staged for review; commit it yourself.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_REF = ROOT / ".template_ref"

# Paths the template owns. Derived repos never edit them, so the difference applies cleanly.
TEMPLATE_OWNED = [
    "bootstrap.sh",
    "cmake/kit",
    "docs/build.md",
    "docs/conventions.md",
    "docs/howto.md",
    "docs/new_repo.md",
    ".clang-format",
    ".clang-tidy",
    ".clangd",
    ".editorconfig",
    ".github/workflows/ci.yml",
    "tools",
]
# Template-owned, but removed from derived repos by init_project.py.
TEMPLATE_ONLY = ["tools/init_project.py"]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def read_template_ref() -> dict[str, str]:
    values = {}
    for line in TEMPLATE_REF.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def write_template_ref(url: str, sha: str) -> None:
    comments = [line for line in TEMPLATE_REF.read_text().splitlines() if line.startswith("#")]
    TEMPLATE_REF.write_text("\n".join([*comments, f"url={url}", f"sha={sha}"]) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--to", help="template commit or release tag to sync to (default: newest)")
    parser.add_argument("--template-url", help="template repo (default: url in .template_ref)")
    args = parser.parse_args()

    ref = read_template_ref()
    url = args.template_url or ref.get("url", "")
    old = ref.get("sha", "")
    if not old:
        print("error: .template_ref records no template commit; was tools/init_project.py run?", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as clone:
        git("clone", "--quiet", "--no-checkout", url, clone)
        new = git("rev-parse", f"{args.to or 'HEAD'}^{{commit}}", cwd=Path(clone))
        if new == old:
            print(f"up to date with {url}@{new[:12]}")
            return 0
        pathspecs = [*TEMPLATE_OWNED, *(f":(exclude){path}" for path in TEMPLATE_ONLY)]
        patch = subprocess.run(["git", "diff", "--binary", old, new, "--", *pathspecs],
                               cwd=clone, capture_output=True, text=True, check=True).stdout

    if patch:
        applied = subprocess.run(["git", "apply", "--3way"], cwd=ROOT, input=patch, text=True)
        if applied.returncode != 0:
            print("error: the patch did not apply cleanly; resolve the conflicts, then rerun", file=sys.stderr)
            return 1
    write_template_ref(url, new)
    print(f"synced template-owned files {old[:12]} -> {new[:12]}; review with `git diff --cached`, then commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
