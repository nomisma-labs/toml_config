# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""tcfg interpretation and deterministic TOML generation."""

from .engine import config_error, document, dumps, load

__all__ = ["config_error", "document", "dumps", "load"]
