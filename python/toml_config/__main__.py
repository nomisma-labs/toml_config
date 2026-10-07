# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Command-line generator: python -m toml_config INPUT [-o OUTPUT]."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

from .engine import config_error, dumps, load


def _atomic_write(destination: Path, text: str) -> None:
    if destination.is_file() and destination.read_bytes() == text.encode("utf-8"):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=destination.parent, prefix=f".{destination.name}.",
                                         delete=False) as stream:
            temporary = stream.name
            stream.write(text)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _escape_dependency(path: Path) -> str:
    result = str(path)
    for old, new in (("\\", "\\\\"), ("$", "$$"), ("#", "\\#"), (" ", "\\ "),
                     ("\t", "\\\t"), (":", "\\:")):
        result = result.replace(old, new)
    if "\n" in result or "\r" in result:
        raise config_error("dependency filenames cannot contain newlines")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve tcfg into ordinary TOML.")
    parser.add_argument("input", type=Path, help="root .tcfg or .toml file")
    parser.add_argument("-o", "--output", type=Path, help="output path (default: stdout)")
    parser.add_argument("--overlay", action="append", default=[], help="merge an additional file; repeatable")
    parser.add_argument("--set", dest="assignments", action="append", default=[],
                        metavar="TOML", help="apply a TOML document patch last; repeatable")
    parser.add_argument("--depfile", type=Path, help="write Make-style dependencies (requires --output)")
    parser.add_argument("--check", action="store_true", help="validate only; write no output")
    arguments = parser.parse_args(argv)
    if arguments.depfile and not arguments.output:
        parser.error("--depfile requires --output")
    if arguments.check and (arguments.output or arguments.depfile):
        parser.error("--check cannot be combined with --output or --depfile")
    try:
        resolved = load(arguments.input, overlays=arguments.overlay, assignments=arguments.assignments)
        if arguments.check:
            return 0
        output = dumps(resolved.values)
        if arguments.output:
            destination = arguments.output.resolve()
            if destination in resolved.dependencies:
                raise config_error("output must not overwrite an input dependency")
            if arguments.depfile:
                dependency_path = arguments.depfile.resolve()
                if dependency_path in resolved.dependencies or dependency_path == destination:
                    raise config_error("depfile must differ from output and all input dependencies")
                dependency_text = _escape_dependency(destination) + ": " + " ".join(
                    _escape_dependency(path) for path in resolved.dependencies) + "\n"
                _atomic_write(dependency_path, dependency_text)
            _atomic_write(destination, output)
        else:
            sys.stdout.write(output)
        return 0
    except (config_error, OSError, UnicodeError) as error:
        print(f"tcfg: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
