#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Manage config generation ownership and successful build records."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

if __package__:
    from . import toml_codec
else:
    import toml_codec


@dataclass(frozen=True)
class _group:
    identifier: str
    source: Path
    sections: list[str]
    environment: dict[str, str]
    outputs: dict[str, str]


@dataclass(frozen=True)
class _plan:
    input_dir: Path
    output_dir: Path
    state_dir: Path
    groups: dict[str, _group]


def _read_json_file(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read JSON file {path}: {error}") from error


def _require_absolute_path(value, field: str) -> Path:
    if not isinstance(value, str) or not value or "\0" in value or not Path(value).is_absolute():
        raise ValueError(f"{field} must be an absolute path")
    return Path(value).resolve()


def _require_relative_path(value, field: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError(f"{field} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"{field} must be relative without path traversal: {value!r}")
    return path.as_posix()


def _paths_overlap(first: Path, second: Path) -> bool:
    return first.is_relative_to(second) or second.is_relative_to(first)


def _resolve_output_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"output path escapes {root}: {relative}")
    return path


def _read_build_plan(path: Path) -> _plan:
    document = _read_json_file(path)
    if not isinstance(document, dict):
        raise ValueError("build plan must be an object")
    input_dir = _require_absolute_path(document.get("input_dir"), "input_dir")
    output_dir = _require_absolute_path(document.get("output_dir"), "output_dir")
    state_dir = _require_absolute_path(document.get("state_dir"), "state_dir")
    if any(_paths_overlap(first, second) for first, second in (
            (input_dir, output_dir), (input_dir, state_dir), (output_dir, state_dir))):
        raise ValueError("input, output, and state directories must be separate")
    definitions = document.get("groups")
    if not isinstance(definitions, list):
        raise ValueError("build plan groups must be an array")
    groups = {}
    sources = set()
    owners: dict[Path, str] = {}
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("each generation group must be an object")
        identifier = definition.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{64}", identifier):
            raise ValueError("group id must be a SHA256 identifier")
        if identifier in groups:
            raise ValueError(f"duplicate group id: {identifier}")
        source = _require_absolute_path(definition.get("source"), "group source")
        if source == input_dir or not source.is_relative_to(input_dir):
            raise ValueError(f"group source must belong to the collected config directory: {source}")
        if source in sources:
            raise ValueError(f"source has conflicting generation registrations: {source}")
        sections = definition.get("sections")
        if (not isinstance(sections, list)
                or any(not isinstance(section, str) or not section for section in sections)
                or len(set(sections)) != len(sections)):
            raise ValueError(f"{source}: sections must be an array of unique names")
        for section in sections:
            _require_relative_path(section, "section")
        environment = definition.get("environment", {})
        if (not isinstance(environment, dict)
                or any(not isinstance(name, str) or not name or "=" in name or "\0" in name
                       or not isinstance(value, str) or "\0" in value
                       for name, value in environment.items())):
            raise ValueError(f"{source}: environment must map variable names to string values")
        output_definitions = definition.get("outputs")
        if not isinstance(output_definitions, list):
            raise ValueError(f"{source}: outputs must be an array")
        outputs = {}
        for output in output_definitions:
            if not isinstance(output, dict) or output.get("section") not in sections:
                raise ValueError(f"{source}: output must name a selected section")
            section = output["section"]
            if section in outputs:
                raise ValueError(f"{source}: duplicate output for section {section!r}")
            relative = _require_relative_path(output.get("path"), "output path")
            if (PurePosixPath(relative) == PurePosixPath(section)
                    or not PurePosixPath(relative).is_relative_to(PurePosixPath(section))):
                raise ValueError(f"{source}: output must be beneath its section: {relative}")
            destination = _resolve_output_path(output_dir, relative)
            for owned, owner in owners.items():
                if _paths_overlap(destination, owned):
                    raise ValueError(f"conflicting output ownership: {destination} ({identifier}) "
                                     f"and {owned} ({owner})")
            owners[destination] = identifier
            outputs[section] = relative
        if set(outputs) != set(sections):
            raise ValueError(f"{source}: every selected section must have exactly one output")
        groups[identifier] = _group(identifier, source, sections, environment, outputs)
        sources.add(source)
    return _plan(input_dir, output_dir, state_dir, groups)


def _record_path(plan: _plan, group: _group, kind: str) -> Path:
    return plan.state_dir / f"{group.identifier}.{kind}.json"


def _write_json_atomically(path: Path, document: dict) -> None:
    content = (json.dumps(document, indent=4, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if path.is_file() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.",
                                         suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _registration_fingerprint(plan: _plan, group: _group) -> str:
    registration = {"input_dir": str(plan.input_dir), "output_dir": str(plan.output_dir),
                    "source": str(group.source), "sections": group.sections,
                    "environment": group.environment, "outputs": group.outputs}
    return hashlib.sha256(json.dumps(registration, sort_keys=True).encode("utf-8")).hexdigest()


def _read_owned_paths(plan: _plan, group: _group) -> set[str]:
    path = _record_path(plan, group, "ownership")
    if not path.exists():
        return set()
    record = _read_json_file(path)
    if (not isinstance(record, dict) or record.get("group") != group.identifier
            or record.get("output_dir") != str(plan.output_dir)
            or not isinstance(record.get("paths"), list)):
        raise ValueError(f"invalid ownership record: {path}")
    return {_require_relative_path(relative, "recorded output path") for relative in record["paths"]}


def _write_owned_paths(plan: _plan, group: _group, paths: set[str]) -> None:
    _write_json_atomically(_record_path(plan, group, "ownership"),
                          {"group": group.identifier, "output_dir": str(plan.output_dir),
                           "paths": sorted(paths)})


def _invalidate_success(plan: _plan, group: _group) -> None:
    _record_path(plan, group, "success").unlink(missing_ok=True)


def _generator_arguments(group: _group) -> list[str]:
    arguments = [sys.executable, str(Path(__file__).with_name("tcfggen.py")),
                 "--source", str(group.source)]
    arguments.extend(f"--config={section}" for section in group.sections)
    return arguments


def _check_collected_output_plan(group: _group, environment: dict[str, str]) -> None:
    result = subprocess.run(_generator_arguments(group) + ["--list"], env=environment,
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"cannot list config metadata: {group.source}")
    rows = json.loads(result.stdout)
    actual = {row["section"]: (PurePosixPath(row["section"]) / row["gen_file"]).as_posix()
              for row in rows if row["generate"]}
    if actual != group.outputs:
        raise ValueError(f"collected config metadata differs from the build plan: {group.source}; "
                         "configure the build again")


def _read_output_hashes(plan: _plan, group: _group, *, validate_toml: bool) -> dict[str, str]:
    hashes = {}
    for relative in group.outputs.values():
        path = _resolve_output_path(plan.output_dir, relative)
        if not path.is_file():
            raise ValueError(f"generated config is missing or is not a regular file: {path}")
        content = path.read_bytes()
        if validate_toml:
            toml_codec.loads(content.decode("utf-8"), str(path))
        hashes[relative] = hashlib.sha256(content).hexdigest()
    return hashes


def _remove_stale_outputs(plan: _plan, group: _group, owned: set[str]) -> None:
    current_paths = [_resolve_output_path(plan.output_dir, relative)
                     for registered in plan.groups.values() for relative in registered.outputs.values()]
    for relative in sorted(owned - set(group.outputs.values())):
        canonical = _resolve_output_path(plan.output_dir, relative)
        if any(_paths_overlap(canonical, current) for current in current_paths):
            continue
        path = plan.output_dir / relative
        if path.is_dir() and not path.is_symlink():
            raise ValueError(f"recorded config output is now a directory; refusing to remove it: {path}")
        path.unlink(missing_ok=True)


def _generate_group(plan: _plan, group: _group) -> None:
    _invalidate_success(plan, group)
    owned = _read_owned_paths(plan, group)
    owned.update(group.outputs.values())
    # Keep all possible publications recorded even if generation later fails.
    _write_owned_paths(plan, group, owned)
    environment = dict(os.environ)
    environment.update(group.environment)
    _check_collected_output_plan(group, environment)
    result = subprocess.run(_generator_arguments(group) + ["--output-dir", str(plan.output_dir)],
                            env=environment, check=False)
    if result.returncode:
        raise ValueError(f"config generation failed for {group.source}")
    hashes = _read_output_hashes(plan, group, validate_toml=True)
    _remove_stale_outputs(plan, group, owned)
    _write_owned_paths(plan, group, set(group.outputs.values()))
    _write_json_atomically(_record_path(plan, group, "success"),
                          {"group": group.identifier,
                           "registration": _registration_fingerprint(plan, group),
                           "outputs": hashes})


def _verify_group(plan: _plan, group: _group) -> None:
    path = _record_path(plan, group, "success")
    if not path.is_file():
        raise ValueError(f"no successful generation record for {group.source}; build configs first")
    record = _read_json_file(path)
    if (not isinstance(record, dict) or record.get("group") != group.identifier
            or record.get("registration") != _registration_fingerprint(plan, group)):
        raise ValueError(f"generation registration changed for {group.source}; build configs again")
    if record.get("outputs") != _read_output_hashes(plan, group, validate_toml=False):
        raise ValueError(f"generated configs changed since successful generation: {group.source}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("command", choices=("validate-plan", "invalidate", "generate", "verify"))
    parser.add_argument("--plan", type=Path, required=True, help="configured build plan")
    parser.add_argument("--group", help="generation group identifier")
    args = parser.parse_args(argv)
    if args.command in {"invalidate", "generate"} and args.group is None:
        parser.error(f"{args.command} requires --group")
    try:
        plan = _read_build_plan(args.plan)
        if args.group is not None and args.group not in plan.groups:
            raise ValueError(f"unknown generation group: {args.group}")
        groups = ([plan.groups[args.group]] if args.group is not None else list(plan.groups.values()))
        for group in groups:
            if args.command == "invalidate":
                _invalidate_success(plan, group)
            elif args.command == "generate":
                _generate_group(plan, group)
            elif args.command == "verify":
                _verify_group(plan, group)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"tcfg_build: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
