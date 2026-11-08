# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

"""Exercise incremental CMake generation and a relocated, installed generator."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib


def run(*command: str) -> str:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(
            f"Command failed ({result.returncode}): {command!r}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def read_config(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmake", required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tcfg generation ") as directory:
        root = Path(directory)
        source = root / "source"
        fixture = args.source / "tests" / "integration" / "generation" / "fixture"
        shutil.copytree(fixture, source)
        build = root / "build"
        helper = args.source / "cmake" / "toml_config" / "tcfg.cmake"
        run(
            args.cmake, "-Werror=dev", "-S", str(source), "-B", str(build), "-G", "Ninja",
            f"-DTCFG_HELPER={helper}",
        )
        run(args.cmake, "--build", str(build))
        output = build / "result config.toml"
        settings = read_config(output)["application"]
        assert settings == {"name": "from CMake", "port": 7000, "labels": ["a;b"]}, settings
        original_timestamp = output.stat().st_mtime_ns

        # A no-op build must skip the generator entirely.
        log = run(args.cmake, "--build", str(build))
        assert "Generating TOML configuration" not in log, log
        assert output.stat().st_mtime_ns == original_timestamp

        # Transitive content changes trigger rebuilding through the compiler-style depfile.
        leaf = source / "leaf.toml"
        leaf.write_text("[application]\nport = 7001\n", encoding="utf-8")
        run(args.cmake, "--build", str(build))
        assert read_config(output)["application"]["port"] == 7001
        changed_timestamp = output.stat().st_mtime_ns

        # An irrelevant comment triggers evaluation, preserving unchanged output timestamps.
        leaf.write_text(leaf.read_text(encoding="utf-8") + "# no semantic change\n", encoding="utf-8")
        run(args.cmake, "--build", str(build))
        assert output.stat().st_mtime_ns == changed_timestamp
        log = run(args.cmake, "--build", str(build))
        assert "Generating TOML configuration" not in log, log

        # Removed includes leave the depfile, so deleted and later changed files cannot linger.
        (source / "base config.tcfg").write_text(
            "[tcfg]\nversion = 1\n[application]\nport = 7002\n", encoding="utf-8"
        )
        leaf.unlink()
        run(args.cmake, "--build", str(build))
        assert read_config(output)["application"]["port"] == 7002
        assert "leaf.toml" not in Path(str(output) + ".d").read_text(encoding="utf-8")
        leaf.write_text("deliberately invalid TOML", encoding="utf-8")
        log = run(args.cmake, "--build", str(build))
        assert "Generating TOML configuration" not in log, log

        # An installed helper uses its adjacent Python package after the prefix is moved.
        prefix = root / "install"
        run(args.cmake, "--install", str(build), "--prefix", str(prefix))
        assert read_config(prefix / "config" / "demo" / output.name) == read_config(output)
        assert not (build / "excluded config.toml").exists()
        assert not (prefix / "config" / "excluded").exists()
        # Explicitly building an excluded target must not opt it into installation.
        run(args.cmake, "--build", str(build), "--target", "excluded_configs")
        assert (build / "excluded config.toml").exists()
        run(args.cmake, "--install", str(build), "--prefix", str(prefix))
        assert not (prefix / "config" / "excluded").exists()
        relocated = root / "relocated prefix"
        prefix.rename(relocated)
        installed_helper = relocated / "share" / "toml_config" / "cmake" / "toml_config" / "tcfg.cmake"
        installed_build = root / "installed build"
        run(
            args.cmake, "-Werror=dev", "-S", str(source), "-B", str(installed_build), "-G", "Ninja",
            f"-DTCFG_HELPER={installed_helper}",
        )
        run(args.cmake, "--build", str(installed_build))
        assert read_config(installed_build / output.name) == read_config(output)

        # The kit's install toggle suppresses both generated configs and bundled tooling.
        disabled_build = root / "install disabled build"
        run(
            args.cmake, "-Werror=dev", "-S", str(source), "-B", str(disabled_build), "-G", "Ninja",
            f"-DTCFG_HELPER={helper}", "-Dnom_install=OFF",
        )
        run(args.cmake, "--build", str(disabled_build))
        assert (disabled_build / output.name).exists()
        disabled_prefix = root / "disabled install"
        run(args.cmake, "--install", str(disabled_build), "--prefix", str(disabled_prefix))
        assert not disabled_prefix.exists()

        # Reconfiguration changes the command signature; removing a SET option drops its key.
        options_build = root / "changed options build"
        for enabled in (True, False):
            run(
                args.cmake, "-Werror=dev", "-S", str(source), "-B", str(options_build), "-G", "Ninja",
                f"-DTCFG_HELPER={helper}", f"-DTCFG_EXTRA_SET={'ON' if enabled else 'OFF'}",
            )
            run(args.cmake, "--build", str(options_build))
            settings = read_config(options_build / output.name)["application"]
            assert ("extra" in settings) == enabled, settings

        # Canonical path ownership catches normalization, symlink and depfile collisions.
        for scenario in ("normalized", "symlink", "dangling_symlink", "depfile"):
            duplicate_build = root / f"{scenario} duplicate build"
            duplicate_build.mkdir()
            if scenario == "symlink":
                alias = root / "build alias"
                alias.symlink_to(duplicate_build, target_is_directory=True)
                duplicate_output = alias / output.name
            elif scenario == "dangling_symlink":
                duplicate_output = root / "output alias.toml"
                duplicate_output.symlink_to(duplicate_build / output.name)
            elif scenario == "depfile":
                duplicate_output = duplicate_build / f"{output.name}.d"
            else:
                duplicate_output = duplicate_build / "unused" / ".." / output.name
            result = subprocess.run(
                [
                    args.cmake, "-Werror=dev", "-S", str(source), "-B", str(duplicate_build), "-G", "Ninja",
                    f"-DTCFG_HELPER={helper}", f"-DTCFG_DUPLICATE_OUTPUT={duplicate_output}",
                ],
                check=False, text=True, capture_output=True,
            )
            assert result.returncode != 0, f"{scenario} output collision was accepted"
            assert "already belongs to TARGET" in result.stderr, result.stderr
            assert "generated_configs" in result.stderr, result.stderr
            assert "other_configs" in result.stderr, result.stderr
    print("Incremental, relocated, installation-selection and output-ownership checks passed.")


if __name__ == "__main__":
    main()
