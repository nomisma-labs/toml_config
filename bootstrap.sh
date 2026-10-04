#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
#
# Template-owned. Validate this checkout using the existing presets and quality checks.
set -uo pipefail

if [[ $# -gt 1 ]]; then
    printf 'Expected at most one preset. Usage: %s [preset | --help]\n' "$0" >&2
    exit 2
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1

# Let CMake resolve includes, inheritance, conditions and CMakeUserPresets.json.
# Bootstrap needs matching configure/build/test names and the repo's build/<preset> layout.
if ! command -v cmake > /dev/null 2>&1; then
    printf 'Missing required tool: cmake (needed to discover presets).\n' >&2
    exit 1
fi
if ! preset_listing=$(cmake --list-presets=all); then
    printf 'Could not discover CMake presets; no build outputs were changed.\n' >&2
    exit 1
fi
configure_presets=()
declare -A build_presets=() test_presets=()
preset_kind=
while IFS= read -r line; do
    case "$line" in
        'Available configure presets:') preset_kind=configure ;;
        'Available build presets:') preset_kind=build ;;
        'Available test presets:') preset_kind=test ;;
        'Available '*':') preset_kind= ;;
    esac
    if [[ $line =~ ^[[:space:]]+\"([^\"]+)\" ]]; then
        preset_name=${BASH_REMATCH[1]}
        case "$preset_kind" in
            configure) configure_presets+=("$preset_name") ;;
            build) build_presets["$preset_name"]=1 ;;
            test) test_presets["$preset_name"]=1 ;;
        esac
    fi
done <<< "$preset_listing"

available_presets=()
presets=()
for preset in "${configure_presets[@]}"; do
    if [[ -n ${build_presets["$preset"]:-} && -n ${test_presets["$preset"]:-} ]]; then
        available_presets+=("$preset")
        # Release validation remains opt-in; new paired presets join the default run.
        if [[ $preset != release ]]; then
            presets+=("$preset")
        fi
    fi
done

show_help() {
    cat <<'HELP'
Usage: ./bootstrap.sh [preset]
       ./bootstrap.sh --help

With no preset, validate all discovered presets except release (which is opt-in).
With a preset, validate only that preset (for example: ./bootstrap.sh release).
Each run clears the selected build/<preset> directories and previous bootstrap logs,
initializes missing submodules, then configures/builds/tests from scratch.
Other build directories are preserved.

Python compatibility/imports, SPDX headers and formatting are checked on every run.
Naming is included when clang is selected.
Each step reports PASS, FAIL or SKIP; failures return exit code 1.
Current logs are kept in build/bootstrap/.

Install the tools listed in docs/build.md first. No packages are installed.
Build concurrency defaults to available CPU cores minus one, with a minimum of one.
Set CMAKE_BUILD_PARALLEL_LEVEL to override it.
CLANG_FORMAT and RUN_CLANG_TIDY overrides are respected by the existing checks.

Available presets (matching configure/build/test names, discovered by CMake):
HELP
    if (( ${#available_presets[@]} )); then
        printf '  %s\n' "${available_presets[@]}"
    else
        printf '  (none)\n'
    fi
}

if [[ $# -eq 1 && ( $1 == --help || $1 == -h ) ]]; then
    show_help
    exit 0
fi
if [[ $# -eq 1 ]]; then
    preset_found=false
    for available in "${available_presets[@]}"; do
        if [[ $1 == "$available" ]]; then
            preset_found=true
            break
        fi
    done
    if [[ $preset_found != true ]]; then
        printf 'Unknown preset: %s. Use --help to list available presets.\n' "$1" >&2
        exit 2
    fi
    presets=("$1")
fi

if (( ${#presets[@]} == 0 )); then
    printf 'No presets selected. Use --help to list available presets.\n' >&2
    exit 2
fi
for preset in "${presets[@]}"; do
    # Preset names become directory and log names; keep cleanup within build/.
    if [[ ! $preset =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ || $preset == bootstrap ]]; then
        printf 'Unsupported bootstrap preset name: %s; no outputs were changed.\n' "$preset" >&2
        exit 2
    fi
done
next_preset=${presets[0]}
if [[ -z ${CMAKE_BUILD_PARALLEL_LEVEL:-} ]]; then
    bootstrap_cores=$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || printf '1')
    CMAKE_BUILD_PARALLEL_LEVEL=$((bootstrap_cores > 1 ? bootstrap_cores - 1 : 1))
fi
export CMAKE_BUILD_PARALLEL_LEVEL

results=()
failed=0
passed=0
skipped=0
step_number=0

record() {
    local status=$1 label=$2 detail=${3:-}
    results+=("[$status] $label${detail:+ — $detail}")
    printf '[%s] %s%s\n' "$status" "$label" "${detail:+ — $detail}"
    case "$status" in
        PASS) passed=$((passed + 1)) ;;
        FAIL) failed=$((failed + 1)) ;;
        SKIP) skipped=$((skipped + 1)) ;;
    esac
}

run_step() {
    local label=$1 log_file status
    shift
    step_number=$((step_number + 1))
    log_file="$log_dir/step-$step_number.log"
    printf '\n[RUN] %s\n' "$label"
    printf 'Command:' > "$log_file"
    printf ' %q' "$@" >> "$log_file"
    printf '\n' >> "$log_file"
    if "$@" >> "$log_file" 2>&1; then
        record PASS "$label"
        return 0
    else
        status=$?
        record FAIL "$label" "exit $status; $log_file"
        tail -n 20 "$log_file"
        return "$status"
    fi
}

have_tools() {
    local tool missing=0
    for tool in "$@"; do
        if ! command -v "$tool" > /dev/null 2>&1; then
            printf 'Missing required tool: %s\n' "$tool" >&2
            missing=1
        fi
    done
    return "$missing"
}

check_python_environment() {
    local preset
    python3 tools/check_python.py || return
    for preset in "${presets[@]}"; do
        if [[ $preset == clang ]]; then
            # This runner may use a different interpreter through its shebang.
            "${RUN_CLANG_TIDY:-run-clang-tidy-19}" --help > /dev/null || return
            printf 'Clang-tidy runner starts successfully: %s\n' "${RUN_CLANG_TIDY:-run-clang-tidy-19}"
        fi
    done
}

prepare_dependencies() {
    local status
    status=$(git submodule status --recursive) || return
    # Do not reset a developer's submodule checkout to a different commit.
    if [[ $status == +* || $status == U* || $status == *$'\n+'* || $status == *$'\nU'* ]]; then
        printf '%s\n' "$status"
        printf 'Submodules differ from their recorded commits or have conflicts. Resolve them before rerunning.\n'
        return 1
    fi
    git submodule update --init --recursive
}

run_tests() {
    local preset=$1 manifest="$log_dir/$1-tests.json" count
    # A freshly initialized repository legitimately has no tests yet. Report that explicitly.
    if ! ctest --preset "$preset" --show-only=json-v1 > "$manifest" 2> "$manifest.err"; then
        record FAIL "$preset: discover tests" "see $manifest.err"
        return
    fi
    if ! count=$(python3 -c 'import json, sys; print(len(json.load(open(sys.argv[1]))["tests"]))' "$manifest"); then
        record FAIL "$preset: discover tests" "invalid test listing in $manifest"
        return
    fi
    if [[ $count == 0 ]]; then
        record SKIP "$preset: tests" 'no tests registered; add tests using docs/howto.md'
    else
        run_step "$preset: tests ($count registered, unit and integration tests where present)" \
            ctest --preset "$preset" --output-on-failure --no-tests=error
    fi
}

# Remove only this script's outputs. Refuse a symlinked parent so cleanup cannot
# follow build/ into another directory; rm removes individual symlinks themselves.
printf '[RUN] Clean previous bootstrap results and validation builds\n'
if [[ -L build ]]; then
    record FAIL 'Clean previous bootstrap results and validation builds' 'build/ is a symlink; use a local build directory'
    exit 1
fi
build_dirs=()
for preset in "${presets[@]}"; do
    build_dirs+=("build/$preset")
done
if rm -rf -- build/bootstrap "${build_dirs[@]}"; then
    record PASS 'Clean previous bootstrap results and validation builds'
else
    record FAIL 'Clean previous bootstrap results and validation builds' 'cleanup failed; no builds were started'
    exit 1
fi
mkdir -p build/bootstrap || exit 1
log_dir=$(mktemp -d "$PWD/build/bootstrap/run.XXXXXX") || exit 1
printf 'Validating %s\nLogs: %s\n' "$PWD" "$log_dir"
printf 'Presets: %s\n' "${presets[*]}"
required_tools=(git cmake ctest python3 "${CLANG_FORMAT:-clang-format-19}")
for preset in "${presets[@]}"; do
    if [[ $preset == clang ]]; then
        required_tools+=(clang-tidy-19 "${RUN_CLANG_TIDY:-run-clang-tidy-19}")
    fi
done
run_step 'Required tools' have_tools "${required_tools[@]}"

python_ready=false
if have_tools python3 git; then
    if run_step 'Python environment' check_python_environment; then
        python_ready=true
    fi
else
    record SKIP 'Python environment' 'requires python3 and git'
fi

dependencies_ready=false
if have_tools git; then
    if run_step 'Dependencies (initialize missing submodules)' prepare_dependencies; then
        dependencies_ready=true
    fi
else
    record SKIP 'Dependencies' 'git is unavailable'
fi

clang_selected=false
clang_ready=false
for preset in "${presets[@]}"; do
    if [[ $preset == clang ]]; then
        clang_selected=true
    fi
    # CMake checks the compiler and generator specified by the actual preset.
    if [[ $dependencies_ready != true || $python_ready != true ]] || ! have_tools cmake ctest; then
        record SKIP "$preset: configure, build and tests" 'required tools, Python environment or dependencies failed'
        continue
    fi
    if ! run_step "$preset: configure" cmake --preset "$preset"; then
        record SKIP "$preset: build and tests" 'configuration failed'
        continue
    fi
    if ! run_step "$preset: build" cmake --build --preset "$preset"; then
        record SKIP "$preset: tests" 'build failed'
        continue
    fi
    if [[ $preset == clang ]]; then
        clang_ready=true
    fi
    run_tests "$preset"
done

if [[ $python_ready == true ]]; then
    run_step 'SPDX headers' python3 tools/check_headers.py
else
    record SKIP 'SPDX headers' 'Python environment check did not pass'
fi
if have_tools git "${CLANG_FORMAT:-clang-format-19}"; then
    run_step 'Formatting' bash tools/check_format.sh
else
    record SKIP 'Formatting' 'required tools failed'
fi
if [[ $clang_selected == true ]]; then
    if [[ $clang_ready == true ]] && have_tools clang-tidy-19 "${RUN_CLANG_TIDY:-run-clang-tidy-19}"; then
        run_step 'Naming' bash tools/check_naming.sh
    else
        record SKIP 'Naming' 'requires a successful Clang build and clang-tidy tools'
    fi
fi

printf '\nSummary\n'
printf '%s\n' "${results[@]}"
printf '\n%s passed, %s failed, %s skipped.\nLogs: %s\n' "$passed" "$failed" "$skipped" "$log_dir"
if (( failed > 0 )); then
    printf '\nValidation failed. Fix the failures above, then rerun ./bootstrap.sh%s.\n' "${1:+ $1}"
    printf 'Toolchain and build instructions: docs/build.md\n'
    printf 'Formatting fixes: tools/check_format.sh --fix\n'
    exit 1
fi

printf '\nValidation passed for the checks run.\n'
if (( skipped > 0 )); then
    printf 'Review the skipped checks above.\n'
fi
printf '\nNext steps:\n'
if [[ -f tools/init_project.py ]]; then
    printf '  Create a repository from this template: docs/new_repo.md\n'
fi
printf '  Add a library, app or tests: docs/howto.md\n'
printf '  Build and tests: cmake --workflow --preset %s\n' "$next_preset"
printf '  Executables: build/%s/bin/\n' "$next_preset"
