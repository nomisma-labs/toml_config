#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Generate application TOML files from tcfg sources, or list their metadata."""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import tempfile

if __package__:
    from . import tcfg, toml_codec
else:
    import tcfg
    import toml_codec


@dataclass(frozen=True)
class _output:
    source: Path
    section: str
    relative_path: Path
    content: bytes


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source", type=Path, metavar="FILE", help="read one tcfg source")
    inputs.add_argument("--input-dir", type=Path, metavar="DIR",
                        help="recursively discover *_tcfg.toml files under DIR")
    parser.add_argument("--app", metavar="NAME",
                        help="select one NAME_tcfg.toml file under --input-dir")
    parser.add_argument("--config", action="append", metavar="NAME",
                        help="select a section; repeat to select several")
    parser.add_argument("--output-dir", type=Path, metavar="DIR", help="generated config root")
    parser.add_argument("--list", action="store_true", dest="list_only",
                        help="print section metadata as JSON without generating files")
    parser.add_argument("--verbose", action="store_true", help="report source and output paths")
    args = parser.parse_args(argv)
    if args.app is not None and args.input_dir is None:
        parser.error("--app requires --input-dir")
    if args.config and args.source is None and args.app is None:
        parser.error("--config requires --source or --app")
    if not args.list_only and args.output_dir is None:
        parser.error("--output-dir is required when generating files")
    return args


def _find_config_sources(args: argparse.Namespace) -> list[tuple[str, Path]]:
    if args.source is not None:
        source = args.source.absolute()
        name = (source.name[:-len("_tcfg.toml")] if source.name.endswith("_tcfg.toml")
                else source.stem)
        return [(name, source)]

    root = args.input_dir.absolute()
    if not root.is_dir():
        raise tcfg.config_error(f"input directory does not exist or is not a directory: {root}")
    if args.app is not None:
        if not args.app or args.app in {".", ".."} or Path(args.app).name != args.app:
            raise tcfg.config_error(f"invalid app name: {args.app!r}")

    sources = sorted((source.name[:-len("_tcfg.toml")], source)
                     for source in root.rglob("*_tcfg.toml") if source.is_file())
    if args.app is not None:
        sources = [(name, source) for name, source in sources if name == args.app]
        if not sources:
            raise tcfg.config_error(f"no tcfg source for app {args.app!r} under {root}")
        if len(sources) > 1:
            matches = ", ".join(str(source) for _, source in sources)
            raise tcfg.config_error(f"ambiguous app name {args.app!r}; matching tcfg sources: {matches}")
    if not sources:
        raise tcfg.config_error(f"no tcfg files found under {root}")
    return sources


def _list_config_metadata(sources: list[tuple[str, Path]], selected: list[str] | None) -> list[dict]:
    rows = []
    for app, source in sources:
        sections = tcfg._read_sections(source)
        names = {section.name for section in sections}
        requested = set(selected) if selected is not None else names
        unknown = requested - names
        if unknown:
            raise tcfg.config_error(f"{source}: unknown selected section {sorted(unknown)[0]!r}")
        for section in sections:
            if section.name in requested:
                rows.append({"app": app, "section": section.name,
                             "gen_file": section.gen_file, "generate": section.generate})
    return rows


def _generate_config_outputs(sources: list[tuple[str, Path]], selected: list[str] | None,
                             verbose: bool) -> tuple[list[_output], set[Path]]:
    outputs = []
    inputs = set()
    for _, source in sources:
        if verbose:
            print(f"Reading {source}", file=sys.stderr)
        configs, read_paths = tcfg.generate_configs_with_inputs(source, sections=selected)
        inputs.update(read_paths)
        for name, config in configs.items():
            content = toml_codec.dumps(config.config).encode("utf-8")
            outputs.append(_output(source, name, Path(name) / config.gen_file, content))
    return outputs, inputs


def _validate_output_paths(outputs: list[_output], root: Path, inputs: set[Path],
                           input_dir: Path | None) -> list[tuple[Path, bytes]]:
    if root.exists() and not root.is_dir():
        raise tcfg.config_error(f"output root is not a directory: {root}")
    if input_dir is not None:
        collected = input_dir.resolve()
        if root.is_relative_to(collected) or collected.is_relative_to(root):
            raise tcfg.config_error(f"input and output directories must be separate: {collected}, {root}")
    for path in sorted(inputs):
        if path.is_relative_to(root):
            raise tcfg.config_error(f"input file is inside the output directory: {path}")

    destinations: dict[Path, _output] = {}
    for output in outputs:
        path = (root / output.relative_path).resolve()
        context = f"{output.source} [section {output.section!r}]"
        if path == root or not path.is_relative_to(root):
            raise tcfg.config_error(f"{context}: output escapes its directory: {output.relative_path}")
        for other, owner in destinations.items():
            if path.is_relative_to(other) or other.is_relative_to(path):
                raise tcfg.config_error(
                    f"{context}: conflicting output {path}; also claimed by "
                    f"{owner.source} [section {owner.section!r}] at {other}")
        if path.exists() and not path.is_file():
            raise tcfg.config_error(f"{context}: output is not a regular file: {path}")
        for parent in path.parents:
            if parent.exists() and not parent.is_dir():
                raise tcfg.config_error(f"{context}: output parent is not a directory: {parent}")
            if parent == root:
                break
        destinations[path] = output
    return [(path, output.content) for path, output in destinations.items()]


def _write_config_files(outputs: list[tuple[Path, bytes]], verbose: bool) -> None:
    # Preflight all existing files before creating or replacing any output.
    changed = []
    for path, content in outputs:
        if path.is_file() and path.read_bytes() == content:
            if verbose:
                print(f"Unchanged {path}", file=sys.stderr)
        else:
            changed.append((path, content))

    pending: list[tuple[Path, Path]] = []
    try:
        # Stage every changed file before replacing the first destination.
        for path, content in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                             prefix=f".{path.name}.", suffix=".tmp",
                                             delete=False) as temporary:
                pending.append((Path(temporary.name), path))
                temporary.write(content)
            if path.exists():
                Path(temporary.name).chmod(path.stat().st_mode & 0o777)
        for temporary, path in pending:
            os.replace(temporary, path)
            if verbose:
                print(f"Generated {path}", file=sys.stderr)
    finally:
        for temporary, _ in pending:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = _parse_arguments(argv)
    try:
        sources = _find_config_sources(args)
        if args.list_only:
            rows = _list_config_metadata(sources, args.config)
            if args.verbose:
                for _, source in sources:
                    print(f"Listed {source}", file=sys.stderr)
            print(json.dumps(rows, indent=4))
        else:
            outputs, inputs = _generate_config_outputs(sources, args.config, args.verbose)
            root = args.output_dir.resolve()
            destinations = _validate_output_paths(outputs, root, inputs, args.input_dir)
            _write_config_files(destinations, args.verbose)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"tcfggen: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
