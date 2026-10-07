#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
#
# Checks C++ formatting against .clang-format. With --fix, reformats the files instead.
set -euo pipefail
cd "$(dirname "$0")/../../.."

clang_format=${CLANG_FORMAT:-clang-format-19}
# Skip paths git still lists but that are gone from the working tree (deleted or renamed, not yet staged).
mapfile -t files < <(git ls-files --cached --others --exclude-standard -- '*.h' '*.hpp' '*.ipp' '*.cpp' '*.cxx' '*.cppm' |
    while read -r file; do [[ -f "$file" ]] && echo "$file"; done)

if (( ${#files[@]} == 0 )); then
    exit 0 # a new repo has no C++ yet; clang-format would read stdin
elif [[ "${1:-}" == "--fix" ]]; then
    "$clang_format" -i "${files[@]}"
else
    "$clang_format" --dry-run --Werror "${files[@]}"
fi
