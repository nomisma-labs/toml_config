# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""A strict, standalone interpreter for the tcfg v1 composition contract."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import datetime
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
import tomllib


class config_error(ValueError):
    """Invalid TOML, tcfg instructions, dependencies, or runtime assignments."""


@dataclass(frozen=True)
class document:
    """Resolved application values and canonical dependencies in discovery order."""

    values: dict[str, Any]
    dependencies: tuple[Path, ...]


def _merge(base: dict[str, Any], layer: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in layer.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _validate_values(value: Any) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _validate_values(child)
    elif isinstance(value, list):
        for child in value:
            _validate_values(child)
    elif type(value) is int and not -(2**63) <= value < 2**63:
        raise config_error("TOML integers must fit in signed 64 bits")


def _parse(source: str, label: str) -> dict[str, Any]:
    try:
        def parse_float(token: str) -> float:
            result = float(token)
            if math.isinf(result) and token.lstrip("+-") != "inf":
                raise config_error("finite TOML float overflows binary64; use an explicit inf if intended")
            return result

        values = tomllib.loads(source, parse_float=parse_float)
        _validate_values(values)
        return values
    except (ValueError, RecursionError) as error:
        raise config_error(f"{label}: {error}") from error


def _path(value: Any, label: str, *, allow_empty: bool = False, allow_reserved: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise config_error(f"{label}: expected an array of string keys")
    if not value and not allow_empty:
        raise config_error(f"{label}: path must not be empty")
    if value and value[0] == "tcfg" and not allow_reserved:
        raise config_error(f"{label}: root key 'tcfg' is reserved")
    return value


def _select(values: Any, path: Sequence[str], label: str) -> Any:
    result = values
    for key in path:
        if not isinstance(result, dict) or key not in result:
            raise config_error(f"{label}: path {list(path)!r} does not exist or crosses a non-table")
        result = result[key]
    return result


def _assign(values: dict[str, Any], path: Sequence[str], value: Any, label: str) -> None:
    target = values
    for key in path[:-1]:
        if key not in target:
            target[key] = {}
        if not isinstance(target[key], dict):
            raise config_error(f"{label}: path {list(path)!r} crosses a non-table")
        target = target[key]
    target[path[-1]] = copy.deepcopy(value)


def _fields(values: Any, allowed: set[str], required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise config_error(f"{label}: expected a table")
    unknown = values.keys() - allowed
    if unknown:
        raise config_error(f"{label}: unknown fields: {', '.join(sorted(unknown))}")
    missing = required - values.keys()
    if missing:
        raise config_error(f"{label}: missing fields: {', '.join(sorted(missing))}")
    return values


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise config_error(f"{label}: expected an array")
    return value


def _string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise config_error(f"{label}: expected {'a nonempty' if nonempty else 'a'} string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise config_error(f"{label}: string must contain valid Unicode scalar values") from error
    return value


class _resolver:
    def __init__(self, environment: Mapping[str, str], max_depth: int):
        self.environment = environment
        self.max_depth = max_depth
        self.dependencies: dict[Path, None] = {}
        self.active: list[Path] = []

    def resolve(self, file: Path) -> dict[str, Any]:
        if "\0" in str(file):
            raise config_error("configuration file paths cannot contain NUL characters")
        try:
            canonical = file.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise config_error(f"{file}: cannot resolve configuration file: {error}") from error
        if canonical in self.active:
            chain = " -> ".join(str(item) for item in [*self.active, canonical])
            raise config_error(f"configuration dependency cycle: {chain}")
        if len(self.active) >= self.max_depth:
            raise config_error(f"{canonical}: dependency depth exceeds {self.max_depth}")
        if canonical.suffix not in (".tcfg", ".toml"):
            raise config_error(f"{canonical}: expected .tcfg or .toml extension")
        self.dependencies[canonical] = None
        self.active.append(canonical)
        try:
            try:
                body = _parse(canonical.read_bytes().decode("utf-8"), str(canonical))
            except (OSError, UnicodeError) as error:
                raise config_error(f"{canonical}: cannot read configuration: {error}") from error
            if canonical.suffix == ".toml":
                if "tcfg" in body:
                    raise config_error(f"{canonical}: root key 'tcfg' is reserved; use .tcfg for directives")
                return body
            metadata = _fields(body.pop("tcfg", None),
                               {"version", "extends", "import", "replace", "delete", "env"},
                               {"version"}, f"{canonical}: tcfg")
            if type(metadata["version"]) is not int or metadata["version"] != 1:
                raise config_error(f"{canonical}: tcfg.version must be integer 1")
            result: dict[str, Any] = {}
            for filename in _array(metadata.get("extends", []), "tcfg.extends"):
                filename = _string(filename, "tcfg.extends entry")
                result = _merge(result, self.resolve(canonical.parent / filename))
            for entry in _array(metadata.get("import", []), "tcfg.import"):
                entry = _fields(entry, {"file", "select", "into"}, {"file", "into"}, "tcfg.import")
                filename = _string(entry["file"], "tcfg.import.file")
                selection = _path(entry.get("select", []), "tcfg.import.select", allow_empty=True,
                                  allow_reserved=True)
                into = _path(entry["into"], "tcfg.import.into")
                imported = self.resolve(canonical.parent / filename)
                _assign(result, into, _select(imported, selection, "tcfg.import.select"), "tcfg.import.into")
            result = _merge(result, body)
            for path in _array(metadata.get("replace", []), "tcfg.replace"):
                path = _path(path, "tcfg.replace")
                _assign(result, path, _select(body, path, "tcfg.replace"), "tcfg.replace")
            for path in _array(metadata.get("delete", []), "tcfg.delete"):
                path = _path(path, "tcfg.delete")
                parent = _select(result, path[:-1], "tcfg.delete")
                if not isinstance(parent, dict) or path[-1] not in parent:
                    raise config_error(f"tcfg.delete: path {path!r} does not exist or crosses a non-table")
                del parent[path[-1]]
            for entry in _array(metadata.get("env", []), "tcfg.env"):
                entry = _fields(entry, {"name", "into", "default"}, {"name", "into"}, "tcfg.env")
                name = _string(entry["name"], "tcfg.env.name")
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                    raise config_error("tcfg.env.name must match [A-Za-z_][A-Za-z0-9_]*")
                into = _path(entry["into"], "tcfg.env.into")
                if "default" in entry:
                    _string(entry["default"], "tcfg.env.default", nonempty=False)
                if name in self.environment:
                    value = _string(self.environment[name], f"environment variable {name}", nonempty=False)
                elif "default" in entry:
                    value = entry["default"]
                else:
                    raise config_error(f"{canonical}: required environment variable {name!r} is unset")
                _assign(result, into, value, "tcfg.env.into")
            if "tcfg" in result:
                raise config_error(f"{canonical}: directives may not create reserved root key 'tcfg'")
            return result
        except config_error as error:
            if str(canonical) in str(error):
                raise
            raise config_error(f"{canonical}: {error}") from error
        finally:
            self.active.pop()


def load(path: str | os.PathLike[str], *, overlays: Sequence[str | os.PathLike[str]] = (),
         assignments: Sequence[str] = (), environment: Mapping[str, str] | None = None,
         max_depth: int = 64) -> document:
    """Interpret one file, merge overlays in order, and apply TOML assignments last.

    Relative dependencies use the declaring file's directory. Overlay paths use
    the caller's working directory, just like the root path. The environment is
    snapshotted once; pass an empty mapping for hermetic loading.
    """
    if type(max_depth) is not int or max_depth < 1:
        raise config_error("max_depth must be a positive integer")
    resolver = _resolver(dict(os.environ if environment is None else environment), max_depth)
    values = resolver.resolve(Path(path))
    for overlay in overlays:
        values = _merge(values, resolver.resolve(Path(overlay)))
    for assignment in assignments:
        override = _parse(assignment, "assignment")
        if not override:
            raise config_error("assignment: expected a nonempty TOML document patch")
        if "tcfg" in override:
            raise config_error("assignment: root key 'tcfg' is reserved")
        values = _merge(values, override)
    return document(values, tuple(resolver.dependencies))


def _quoted(value: str) -> str:
    result = ['"']
    escapes = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t", "\n": "\\n",
               "\f": "\\f", "\r": "\\r"}
    for character in value:
        codepoint = ord(character)
        if character in escapes:
            result.append(escapes[character])
        elif codepoint < 0x20 or codepoint == 0x7f:
            result.append(f"\\u{codepoint:04x}")
        elif 0xd800 <= codepoint <= 0xdfff:
            raise config_error("TOML strings cannot contain Unicode surrogate code points")
        else:
            result.append(character)
    result.append('"')
    return "".join(result)


def _table_keys(values: Mapping[str, Any]) -> list[str]:
    if any(not isinstance(key, str) for key in values):
        raise config_error("TOML table keys must be strings")
    return sorted(values)


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return _quoted(value)
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        _validate_values(value)
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "-inf" if value < 0 else "inf"
        return repr(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        if isinstance(value, datetime.time) and value.tzinfo is not None:
            raise config_error("TOML has no offset-time type; use a local time or offset datetime")
        if isinstance(value, datetime.datetime):
            offset = value.utcoffset()
            if offset is not None and offset % datetime.timedelta(minutes=1) != datetime.timedelta(0):
                raise config_error("TOML datetime offsets must be whole minutes")
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_quoted(key)} = {_literal(value[key])}" for key in _table_keys(value)) + " }"
    raise config_error(f"cannot serialize {type(value).__name__} as TOML")


def dumps(values: Mapping[str, Any]) -> str:
    """Serialize TOML data deterministically, retaining TOML scalar types."""
    if not isinstance(values, Mapping):
        raise config_error("TOML document must be a mapping")
    lines: list[str] = []

    def table(current: Mapping[str, Any], path: list[str]) -> None:
        keys = _table_keys(current)
        if path:
            if lines:
                lines.append("")
            lines.append("[" + ".".join(_quoted(part) for part in path) + "]")
        for key in keys:
            if not isinstance(current[key], dict):
                lines.append(f"{_quoted(key)} = {_literal(current[key])}")
        for key in keys:
            if isinstance(current[key], dict):
                table(current[key], [*path, key])

    table(values, [])
    return "\n".join(lines) + ("\n" if lines else "")
