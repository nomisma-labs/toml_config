# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""TOML 1.0 value validation and deterministic serialization for config tooling."""

from collections.abc import Mapping
import datetime
import math
from typing import Any
import tomllib


def _validate_values(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key.encode("utf-8")
            _validate_values(child)
    elif isinstance(value, list):
        for child in value:
            _validate_values(child)
    elif isinstance(value, str):
        value.encode("utf-8")
    elif type(value) is int and not -(2**63) <= value < 2**63:
        raise ValueError("TOML integers must fit in signed 64 bits")


def loads(source: str, label: str = "TOML") -> dict[str, Any]:
    try:
        source.encode("utf-8")
        def parse_float(token: str) -> float:
            result = float(token)
            if math.isinf(result) and token.lstrip("+-") != "inf":
                raise ValueError("finite TOML float overflows binary64; use an explicit inf if intended")
            return result

        values = tomllib.loads(source, parse_float=parse_float)
        _validate_values(values)
        return values
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError(f"{label}: {error}") from error


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
            raise ValueError("TOML strings cannot contain Unicode surrogate code points")
        else:
            result.append(character)
    result.append('"')
    return "".join(result)


def _table_keys(values: Mapping[str, Any]) -> list[str]:
    if any(not isinstance(key, str) for key in values):
        raise ValueError("TOML table keys must be strings")
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
            raise ValueError("TOML has no offset-time type; use a local time or offset datetime")
        if isinstance(value, datetime.datetime):
            offset = value.utcoffset()
            if offset is not None and offset % datetime.timedelta(minutes=1) != datetime.timedelta(0):
                raise ValueError("TOML datetime offsets must be whole minutes")
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_quoted(key)} = {_literal(value[key])}" for key in _table_keys(value)) + " }"
    raise ValueError(f"cannot serialize {type(value).__name__} as TOML")


def dumps(values: Mapping[str, Any]) -> str:
    """Serialize TOML data deterministically, retaining TOML scalar types."""
    if not isinstance(values, Mapping):
        raise ValueError("TOML document must be a mapping")
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
