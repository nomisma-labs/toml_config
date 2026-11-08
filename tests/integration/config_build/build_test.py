# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
"""Run real CMake/Ninja config workflows in small, dependency-free projects."""

import json
import tomllib
from tools.toml_config import toml_codec
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


repository = Path(__file__).resolve().parents[3]
cmake = os.environ.get("TCFG_TEST_CMAKE", "cmake")
ctest = os.environ.get("TCFG_TEST_CTEST", "ctest")
compiler = os.environ.get("TCFG_TEST_CXX", "c++")
fixture_main = """#include <filesystem>
#include <string_view>

int main(int argc, char** argv)
{
    if (argc != 4 || std::string_view(argv[1]) != "--config"
        || std::string_view(argv[3]) != "--check-config") {
        return 1;
    }
    const std::filesystem::path config(argv[2]);
    return config.is_absolute() && std::filesystem::is_regular_file(config) ? 0 : 2;
}
"""


class config_build_tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="tcfg_build_test_")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.source = self.directory / "source"
        self.build = self.directory / "build"
        self.source.mkdir()
        self.environment = dict(os.environ)
        self.apps = []
        self.registration = ""
        self.install_index = 0

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_toml(self, path, content):
        return self.write(path, toml_codec.dumps({"sections": content} if isinstance(content, list) else content))

    def add_app(self, folder, *, names=None, excluded=False, document=None):
        self.apps.append(folder)
        names = [folder] if names is None else names
        directory = self.source / "apps" / folder
        self.write(directory / "main.cpp", fixture_main)
        options = " BUILD_FOR complete" if excluded else ""
        self.write(directory / "CMakeLists.txt", "\n".join(
            f"nom_app({name} SOURCES main.cpp{options})" for name in names))
        if document is None:
            document = {"tcfg": {"name": "dev"}, "value": "initial"}
        return self.write_toml(directory / "config" / f"{folder}_tcfg.toml", document)

    def register(self, app, source=None, sections="dev", environment="", build_with_app=False):
        source = source or f"{app}_tcfg.toml"
        options = f" SECTIONS {sections}" if sections is not None else ""
        if environment:
            options += f" ENVIRONMENT {environment}"
        if build_with_app:
            options += " BUILD_WITH_APP"
        return f"nom_tcfg_generate({app} SOURCE {source}{options})\n"

    def project(self):
        body = f"""cmake_minimum_required(VERSION 3.30)
project(fixture LANGUAGES CXX)
include("{repository}/cmake/kit/nom_kit.cmake")
nom_project_options()
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)
enable_testing()
include("{repository}/cmake/toml_config/config.cmake")
"""
        body += "\n".join(f"add_subdirectory(apps/{folder})" for folder in self.apps)
        body += "\n" + self.registration
        self.write(self.source / "CMakeLists.txt", body)

    def run_command(self, *arguments, success=True):
        result = subprocess.run([str(arg) for arg in arguments], cwd=self.directory,
                                env=self.environment, capture_output=True, text=True,
                                check=False, timeout=60)
        output = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
        return output

    def configure(self, *options, success=True):
        self.project()
        return self.run_command(cmake, "-S", self.source, "-B", self.build, "-G", "Ninja",
                                f"-DCMAKE_CXX_COMPILER={compiler}", "-DNOM_BUILD_PRESET=dev",
                                "-DFIXTURE_INSTALL=ON", *options, success=success)

    def build_targets(self, *targets, success=True):
        selection = ["--target", *targets] if targets else []
        return self.run_command(cmake, "--build", self.build, "--parallel", "8",
                                *selection, success=success)

    def install(self, *, success=True):
        self.install_index += 1
        prefix = self.directory / f"install_{self.install_index}"
        self.run_command(cmake, "--install", self.build, "--prefix", prefix, success=success)
        return prefix

    def generated(self, name):
        return self.build / "genconfig" / name

    def read_generated(self, name):
        return tomllib.loads(self.generated(name).read_text(encoding="utf-8"))

    def test_apps_disabled_skip_unconditional_generation_and_config_tests(self):
        self.add_app("capture")
        self.registration = self.register("capture", source="../absent.toml")
        self.registration += """nom_tcfg_generate(absent)
nom_tcfg_test(capture dev)
nom_tcfg_test(absent missing)
"""
        self.configure("-DFIXTURE_BUILD_APPS=OFF", "-DFIXTURE_BUILD_TESTS=ON")
        self.build_targets("config")
        self.build_targets()
        self.assertFalse((self.build / "config").exists())
        self.assertFalse(self.generated("dev/capture.toml").exists())
        self.assertFalse(any((self.build / "bin").glob("*")))
        tests = json.loads(self.run_command(ctest, "--test-dir", self.build, "--show-only=json-v1"))
        self.assertEqual(tests["tests"], [])
        self.build_targets("fixture_generate_tcfg_capture", success=False)
        prefix = self.install()
        self.assertFalse(list(prefix.rglob("*.toml")))

    def test_tests_and_install_disabled_leave_app_config_generation_enabled(self):
        self.add_app("capture")
        self.registration = self.register("capture", build_with_app=True)
        self.registration += """nom_tcfg_test(capture dev)
nom_tcfg_test(capture missing)
nom_tcfg_test(absent missing)
"""
        self.configure("-DFIXTURE_BUILD_APPS=ON", "-DFIXTURE_BUILD_TESTS=OFF",
                       "-DFIXTURE_INSTALL=OFF")
        self.build_targets()
        self.assertTrue((self.build / "bin/capture").is_file())
        self.assertTrue((self.build / "config/capture/capture_tcfg.toml").is_file())
        self.assertEqual(self.read_generated("dev/capture.toml"), {"value": "initial"})
        tests = json.loads(self.run_command(ctest, "--test-dir", self.build, "--show-only=json-v1"))
        self.assertEqual(tests["tests"], [])
        prefix = self.install()
        self.assertFalse(list(prefix.rglob("*.toml")))
        self.assertFalse((prefix / "bin/capture").exists())

    def test_host_options_do_not_enable_dependency_apps_generation_or_tests(self):
        self.add_app("host")
        self.registration = self.register("host")
        self.registration += """add_subdirectory(dependency)
if(NOT nom_build_apps OR NOT nom_build_tests)
    message(FATAL_ERROR "Dependency options changed the host settings")
endif()
nom_tcfg_test(host dev)
"""
        dependency = self.source / "dependency"
        self.write(dependency / "CMakeLists.txt", """project(dependency LANGUAGES CXX)
nom_project_options()
add_subdirectory(apps/child)
nom_tcfg_generate(child SOURCE absent.toml)
nom_tcfg_test(child dev)
nom_c2test(unit SOURCES absent_test.cxx)
""")
        self.write(dependency / "apps/child/CMakeLists.txt", "nom_app(child SOURCES main.cpp)\n")
        self.write(dependency / "apps/child/main.cpp", fixture_main)
        self.write_toml(dependency / "apps/child/config/child_tcfg.toml", {
            "tcfg": {"name": "dev"}, "value": "dependency",
        })
        self.configure("-DFIXTURE_BUILD_APPS=ON", "-DFIXTURE_BUILD_TESTS=ON")
        self.build_targets("host", "config")
        self.assertEqual(self.read_generated("dev/host.toml"), {"value": "initial"})
        self.assertFalse((self.build / "config/child").exists())
        self.assertFalse(self.generated("dev/child.toml").exists())
        self.assertFalse((self.build / "dependency/bin/child").exists())
        tests = json.loads(self.run_command(ctest, "--test-dir", self.build, "--show-only=json-v1"))
        self.assertEqual([test["name"] for test in tests["tests"]], ["fixture_host_config_dev"])
        self.run_command(ctest, "--test-dir", self.build, "--output-on-failure")

    def test_config_aggregate_collects_excluded_and_ordinary_apps_without_compiling(self):
        self.add_app("capture", document=[
            {"tcfg": {"name": "dev"}, "value": 1},
            {"tcfg": {"name": "prod", "extend": "dev"}, "value": 2},
        ])
        plain = self.add_app("plain")
        plain.unlink()
        self.write_toml(plain.parent / "plain.toml", {"ordinary": True})
        self.add_app("excluded", excluded=True)
        self.registration = self.register("capture", sections="dev prod") + self.register("excluded")
        self.registration += "nom_tcfg_test(capture prod)\n"
        self.configure()
        self.build_targets("config")
        for app, filename in (("capture", "capture_tcfg.toml"), ("plain", "plain.toml"),
                              ("excluded", "excluded_tcfg.toml")):
            self.assertTrue((self.build / "config" / app / filename).is_file())
        for output in ("dev/capture.toml", "prod/capture.toml", "dev/excluded.toml"):
            self.assertTrue(self.generated(output).is_file())
        self.assertFalse(any((self.build / "bin").glob("*")))
        tests = json.loads(self.run_command(ctest, "--test-dir", self.build, "--show-only=json-v1"))
        self.assertEqual(len(tests["tests"]), 1)
        self.build_targets("capture")
        self.run_command(ctest, "--test-dir", self.build, "--output-on-failure")
        self.assertTrue((self.build / "bin/capture").is_file())
        self.assertFalse((self.build / "bin/plain").exists())
        self.assertFalse((self.build / "bin/excluded").exists())

    def test_literal_all_false_like_and_leading_dash_sections_with_collector_like_app_name(self):
        self.add_app("capture", names=["capture_copy_capture_config"], document=[
            {"tcfg": {"name": "off"}, "value": "parent"},
            {"tcfg": {"name": "-prod", "extend": "off"}, "value": "child"},
            {"tcfg": {"name": "ALL", "extend": "off"}, "value": "literal section"},
        ])
        self.registration = self.register("capture_copy_capture_config", source="capture_tcfg.toml", sections="off")
        self.configure()
        self.build_targets("config")
        self.assertEqual(self.read_generated("off/capture.toml"), {"value": "parent"})
        self.assertFalse((self.build / "bin/capture_copy_capture_config").exists())
        self.registration = self.register("capture_copy_capture_config", source="capture_tcfg.toml", sections="-prod")
        self.project()
        self.build_targets("config")
        self.assertEqual(self.read_generated("-prod/capture.toml"), {"value": "child"})
        self.assertFalse(self.generated("off/capture.toml").exists())
        self.assertFalse((self.build / "bin/capture_copy_capture_config").exists())
        self.registration = self.register("capture_copy_capture_config", source="capture_tcfg.toml", sections="ALL")
        self.project()
        self.build_targets("config")
        self.assertEqual(self.read_generated("ALL/capture.toml"), {"value": "literal section"})
        self.assertFalse(self.generated("-prod/capture.toml").exists())
        self.assertFalse(self.generated("off/capture.toml").exists())

    def test_omitted_sections_follow_added_renamed_removed_and_suppressed_sections(self):
        base = {"tcfg": {"name": "base", "generate": False}, "value": "inherited"}
        dev = {"tcfg": {"name": "dev", "extend": "base"}}
        prod = {"tcfg": {"name": "prod", "extend": "dev"}}
        source = self.add_app("capture", document=[base, dev, prod])
        self.registration = self.register("capture", sections=None)
        self.configure()
        original_cmake = (self.source / "CMakeLists.txt").read_bytes()
        self.build_targets("config")
        self.assertEqual(self.read_generated("dev/capture.toml"), {"value": "inherited"})
        self.assertEqual(self.read_generated("prod/capture.toml"), {"value": "inherited"})
        self.assertFalse(self.generated("base/capture.toml").exists())
        unrelated = self.write_toml(self.generated("unrelated/keep.toml"), {"keep": True})

        sim = {"tcfg": {"name": "sim", "extend": "dev"}, "value": "simulation"}
        self.write_toml(source, [base, dev, prod, sim])
        self.build_targets("config")
        self.assertEqual(self.read_generated("sim/capture.toml"), {"value": "simulation"})
        self.assertTrue(self.generated("prod/capture.toml").is_file())

        live = {"tcfg": {"name": "live", "extend": "dev"}}
        self.write_toml(source, [base, dev, live])
        self.build_targets("config")
        self.assertEqual(self.read_generated("live/capture.toml"), {"value": "inherited"})
        self.assertFalse(self.generated("prod/capture.toml").exists())
        self.assertFalse(self.generated("sim/capture.toml").exists())

        self.write_toml(source, [base, {"tcfg": {"name": "dev", "extend": "base", "generate": False}}])
        self.build_targets("config")
        self.assertFalse(self.generated("dev/capture.toml").exists())
        self.assertFalse(self.generated("live/capture.toml").exists())
        self.assertTrue(unrelated.is_file())
        self.assertEqual((self.source / "CMakeLists.txt").read_bytes(), original_cmake)
        self.assertFalse(any((self.build / "bin").glob("*")))

    def test_omitted_sections_allow_an_initially_suppressed_source(self):
        self.add_app("capture", document={
            "tcfg": {"name": "base", "generate": False}, "value": "abstract config",
        })
        self.registration = self.register("capture", sections=None)
        self.configure()
        self.build_targets("fixture_generate_tcfg_capture")
        self.assertTrue((self.build / "config/capture/capture_tcfg.toml").is_file())
        self.assertFalse(list((self.build / "genconfig").rglob("*.toml")))
        self.assertFalse((self.build / "bin/capture").exists())
        self.build_targets("capture", "config")
        prefix = self.install()
        self.assertTrue((prefix / "bin/capture").is_file())
        self.assertFalse(list((prefix / "genconfig").rglob("*.toml")))

    def test_readable_app_generation_target_collects_only_that_app_without_compiling(self):
        for app in ("first", "second"):
            self.add_app(app)
            self.registration += self.register(app, sections=None)
        self.configure()
        self.build_targets("fixture_generate_tcfg_first")
        self.assertEqual(self.read_generated("dev/first.toml"), {"value": "initial"})
        self.assertTrue((self.build / "config/first/first_tcfg.toml").is_file())
        self.assertFalse((self.build / "config/second").exists())
        self.assertFalse(self.generated("dev/second.toml").exists())
        self.assertFalse(any((self.build / "bin").glob("*")))
        output = self.build_targets("fixture_generate_tcfg_second")
        self.assertEqual(self.read_generated("dev/second.toml"), {"value": "initial"})
        self.assertNotIn("Generating configs from first/first_tcfg.toml", output)
        self.assertFalse(any((self.build / "bin").glob("*")))

    def test_default_app_and_all_builds_collect_without_resolving_generation_inputs(self):
        source = self.add_app("capture", document={
            "tcfg": {"name": "dev", "import": "donor.toml"},
            "environment": "{tcfg:gen-var TCFG_BUILD_TEST_MISSING}",
        })
        self.write_toml(source.parent / "capture.toml", {"ordinary": "development config"})
        self.environment.pop("TCFG_BUILD_TEST_MISSING", None)
        self.registration = self.register("capture")
        self.configure()
        for targets in (("capture",), ()):
            with self.subTest(targets=targets):
                self.build_targets(*targets)
                collected = self.build / "config/capture/capture.toml"
                self.assertEqual(tomllib.loads(collected.read_text()), {"ordinary": "development config"})
                self.assertTrue((self.build / "bin/capture").is_file())
                self.assertFalse(self.generated("dev/capture.toml").exists())
        self.build_targets("config", success=False)
        self.write_toml(source.parent / "donor.toml", {"value": "from donor"})
        self.build_targets("config", success=False)
        self.environment["TCFG_BUILD_TEST_MISSING"] = "available"
        self.build_targets("config")
        self.assertEqual(self.read_generated("dev/capture.toml"), {
            "value": "from donor", "environment": "available",
        })

    def test_opted_in_app_build_refreshes_source_configs_without_recompiling(self):
        source = self.add_app("capture")
        removed = self.write_toml(source.parent / "removed.toml", {"old": True})
        self.registration = self.register("capture", build_with_app=True)
        self.configure()
        self.build_targets("capture")
        binary = self.build / "bin/capture"
        binary_time = binary.stat().st_mtime_ns
        output = self.generated("dev/capture.toml")
        os.utime(output, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
        output_time = output.stat().st_mtime_ns
        self.build_targets("capture")
        self.assertEqual(output.stat().st_mtime_ns, output_time)
        self.assertEqual(binary.stat().st_mtime_ns, binary_time)
        self.write_toml(source, {"tcfg": {"name": "dev"}, "value": "updated"})
        removed.unlink()
        self.build_targets("capture")
        self.assertEqual(self.read_generated("dev/capture.toml"), {"value": "updated"})
        self.assertEqual(binary.stat().st_mtime_ns, binary_time)
        self.assertFalse((self.build / "config/capture/removed.toml").exists())

    def test_generation_observes_external_donors_and_process_environment_changes(self):
        library = self.directory / "shared configs"
        donor = self.write_toml(library / "donor.toml", {"external": "first"})
        self.add_app("capture", document={
            "tcfg": {"name": "dev", "import": "{tcfg:gen-var NOM_CONFIG_LIB}/donor.toml"},
            "environment": "{tcfg:gen-var TCFG_BUILD_TEST_VALUE}",
            "literal": "{tcfg:gen-var TCFG_BUILD_TEST_LITERAL}",
        })
        self.registration = self.register("capture", environment=(
            f'"NOM_CONFIG_LIB={library}" "TCFG_BUILD_TEST_LITERAL=one;two with spaces"'))
        self.environment["TCFG_BUILD_TEST_VALUE"] = "first"
        self.configure()
        self.build_targets("config")
        self.assertEqual(self.read_generated("dev/capture.toml"), {
            "external": "first", "environment": "first", "literal": "one;two with spaces",
        })
        self.write_toml(donor, {"external": "second"})
        self.environment["TCFG_BUILD_TEST_VALUE"] = "second"
        self.build_targets("config")
        self.assertEqual(self.read_generated("dev/capture.toml"), {
            "external": "second", "environment": "second", "literal": "one;two with spaces",
        })

    def test_metadata_refresh_and_deselection_prune_only_owned_outputs(self):
        source = self.add_app("capture", document=[
            {"tcfg": {"name": "dev"}},
            {"tcfg": {"name": "prod", "extend": "dev"}},
        ])
        self.registration = self.register("capture", sections="dev prod")
        self.configure()
        self.build_targets("config")
        unrelated = self.write_toml(self.generated("unrelated/keep.toml"), {"keep": True})
        self.write_toml(source, [
            {"tcfg": {"name": "dev", "gen_file": "renamed.toml"}},
            {"tcfg": {"name": "prod", "extend": "dev"}},
        ])
        self.build_targets("config")
        self.assertFalse(self.generated("dev/capture.toml").exists())
        self.assertFalse(self.generated("prod/capture.toml").exists())
        self.assertTrue(self.generated("dev/renamed.toml").is_file())
        self.assertTrue(self.generated("prod/renamed.toml").is_file())
        self.write_toml(source, [
            {"tcfg": {"name": "dev", "gen_file": "renamed.toml"}},
            {"tcfg": {"name": "live", "extend": "dev"}},
        ])
        self.registration = self.register("capture", sections="dev live")
        self.project()
        self.build_targets("config")
        self.assertFalse(self.generated("prod/renamed.toml").exists())
        self.assertTrue(self.generated("live/renamed.toml").is_file())
        self.registration = self.register("capture", sections="dev")
        self.project()
        self.build_targets("config")
        self.assertFalse(self.generated("live/renamed.toml").exists())
        self.assertTrue(self.generated("dev/renamed.toml").is_file())
        self.assertTrue(unrelated.is_file())

    def test_shared_source_generation_is_optional_for_each_app(self):
        self.add_app("shared", names=["first", "second"])
        self.registration = (self.register("first", source="shared_tcfg.toml")
                             + self.register("first", source="shared_tcfg.toml")
                             + self.register("second", source="shared_tcfg.toml", build_with_app=True))
        self.configure()
        self.build_targets("first")
        self.assertFalse(self.generated("dev/shared.toml").exists())
        output = self.build_targets("fixture_generate_tcfg_first", "fixture_generate_tcfg_second")
        self.assertEqual(output.count("Generating configs from shared/shared_tcfg.toml"), 1)
        self.assertEqual(self.read_generated("dev/shared.toml"), {"value": "initial"})
        self.assertFalse((self.build / "bin/second").exists())
        output = self.build_targets("first", "second")
        self.assertEqual(output.count("Generating configs from shared/shared_tcfg.toml"), 1)
        self.assertEqual(self.read_generated("dev/shared.toml"), {"value": "initial"})
        self.assertTrue((self.build / "bin/first").is_file())
        self.assertTrue((self.build / "bin/second").is_file())
        self.assertEqual(sorted(path.name for path in (self.build / "config").iterdir()), ["shared"])

    def test_readable_generation_target_cannot_reuse_an_existing_app_target(self):
        self.add_app("shared", names=["capture", "fixture_generate_tcfg_capture"])
        self.registration = (self.register("fixture_generate_tcfg_capture", source="shared_tcfg.toml")
                             + self.register("capture", source="shared_tcfg.toml"))
        diagnostic = self.configure(success=False)
        self.assertIn("target fixture_generate_tcfg_capture already exists", " ".join(diagnostic.split()))

    def test_conflicting_shared_registration_is_rejected(self):
        self.add_app("shared", names=["first", "second"], document=[
            {"tcfg": {"name": "dev"}},
            {"tcfg": {"name": "prod", "extend": "dev"}},
        ])
        self.registration = (self.register("first", source="shared_tcfg.toml", sections="dev")
                             + self.register("second", source="shared_tcfg.toml", sections="prod"))
        self.configure(success=False)

    def test_different_sources_cannot_claim_the_same_output(self):
        for app in ("first", "second"):
            self.add_app(app, document={"tcfg": {"name": "dev", "gen_file": "shared.toml"}})
            self.registration += self.register(app)
        self.configure(success=False)

    def test_duplicate_directory_basenames_are_rejected_for_collection_only_apps(self):
        for name in ("first", "second"):
            folder = f"{name}/shared"
            self.apps.append(folder)
            directory = self.source / "apps" / folder
            self.write(directory / "main.cpp", fixture_main)
            self.write(directory / "CMakeLists.txt", f"nom_app({name} SOURCES main.cpp)\n")
            self.write_toml(directory / "config/settings.toml", {"app": name})
        diagnostic = self.configure(success=False)
        self.assertIn("basenames must be unique", diagnostic)

    def test_output_reassignment_preserves_the_new_owners_config(self):
        first = self.add_app("first", document={
            "tcfg": {"name": "dev", "gen_file": "shared.toml"}, "owner": "first",
        })
        second = self.add_app("second", document={"tcfg": {"name": "dev"}, "owner": "second"})
        self.registration = (self.register("first", build_with_app=True)
                             + self.register("second", build_with_app=True))
        self.configure()
        self.build_targets("config")
        self.write_toml(first, {"tcfg": {"name": "dev", "gen_file": "first.toml"}, "owner": "first"})
        self.write_toml(second, {"tcfg": {"name": "dev", "gen_file": "shared.toml"}, "owner": "second"})
        # Publish the new owner's config before the old owner gets to prune its files.
        self.build_targets("second")
        self.build_targets("first")
        self.assertEqual(self.read_generated("dev/shared.toml"), {"owner": "second"})
        self.assertFalse(self.generated("dev/second.toml").exists())
        self.build_targets("config")
        self.assertEqual(self.read_generated("dev/shared.toml"), {"owner": "second"})
        self.assertEqual(self.read_generated("dev/first.toml"), {"owner": "first"})

    def test_shared_source_installs_when_only_the_later_app_is_selected(self):
        self.add_app("shared", names=["excluded", "selected"])
        self.write(self.source / "apps/shared/CMakeLists.txt",
                   "nom_app(excluded SOURCES main.cpp BUILD_FOR complete)\n"
                   "nom_app(selected SOURCES main.cpp)\n")
        self.registration = (self.register("excluded", source="shared_tcfg.toml")
                             + self.register("selected", source="shared_tcfg.toml"))
        self.configure()
        self.build_targets("selected", "config")
        prefix = self.install()
        self.assertTrue((prefix / "bin/selected").is_file())
        self.assertFalse((prefix / "bin/excluded").exists())
        self.assertTrue((prefix / "config/shared/shared_tcfg.toml").is_file())
        self.assertTrue((prefix / "genconfig/dev/shared.toml").is_file())

    def test_install_checks_outputs_and_excludes_unselected_apps(self):
        source = self.add_app("capture")
        self.add_app("excluded", excluded=True)
        self.registration = self.register("capture") + self.register("excluded")
        self.configure()
        self.build_targets("config", "capture")
        prefix = self.install()
        self.assertTrue((prefix / "bin/capture").is_file())
        self.assertTrue((prefix / "config/capture/capture_tcfg.toml").is_file())
        self.assertTrue((prefix / "genconfig/dev/capture.toml").is_file())
        self.assertFalse((prefix / "bin/excluded").exists())
        self.assertFalse((prefix / "config/excluded").exists())
        self.assertFalse((prefix / "genconfig/dev/excluded.toml").exists())
        self.build_targets("capture")
        self.assertTrue(self.generated("dev/capture.toml").is_file())
        self.install(success=False)
        self.build_targets("config")
        self.install()
        self.write_toml(self.generated("dev/capture.toml"), {"value": "tampered"})
        self.install(success=False)
        self.build_targets("config")
        self.generated("dev/capture.toml").unlink()
        self.install(success=False)
        self.build_targets("config")
        previous = self.generated("dev/capture.toml").read_bytes()
        self.write_toml(source, {"tcfg": {"name": "dev", "import": "missing.toml"}})
        self.build_targets("config", success=False)
        self.assertEqual(self.generated("dev/capture.toml").read_bytes(), previous)
        self.install(success=False)

    def test_install_requires_a_success_record_even_when_output_files_exist(self):
        self.add_app("capture")
        self.registration = self.register("capture")
        self.configure()
        self.build_targets("capture", "config")
        saved = {path.relative_to(self.build): path.read_bytes()
                 for directory in ("config", "genconfig")
                 for path in (self.build / directory).rglob("*") if path.is_file()}
        self.build_targets("clean_config")
        for relative, content in saved.items():
            destination = self.build / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        self.install(success=False)

    def test_collection_failure_invalidates_previous_generation_success(self):
        self.add_app("capture")
        self.registration = self.register("capture")
        self.configure()
        self.build_targets("capture", "config")
        collected = self.build / "config"
        backup = self.directory / "collected_backup"
        shutil.copytree(collected, backup)
        previous = self.generated("dev/capture.toml").read_bytes()
        shutil.rmtree(collected)
        collected.write_text("blocks collection", encoding="utf-8")
        self.build_targets("config", success=False)
        collected.unlink()
        shutil.copytree(backup, collected)
        self.assertEqual(self.generated("dev/capture.toml").read_bytes(), previous)
        # Restore the collected inputs so installation can fail only on stale generation state.
        self.install(success=False)
        self.build_targets("config")
        self.install()

    def test_install_rejects_a_success_record_from_a_previous_plan(self):
        self.add_app("capture", document={
            "tcfg": {"name": "dev"}, "value": "{tcfg:gen-var TCFG_BUILD_TEST_VALUE}",
        })
        self.registration = self.register("capture", environment="TCFG_BUILD_TEST_VALUE=first")
        self.configure()
        self.build_targets("capture", "config")
        self.registration = self.register("capture", environment="TCFG_BUILD_TEST_VALUE=second")
        self.configure()
        self.install(success=False)
        self.build_targets("capture", "config")
        self.assertEqual(self.read_generated("dev/capture.toml"), {"value": "second"})
        self.install()

    def test_clean_targets_remove_all_config_trees_and_allow_regeneration(self):
        source = self.add_app("capture")
        original = source.read_bytes()
        self.registration = self.register("capture")
        self.configure()
        self.build_targets("config")
        for target in ("clean_config", "clean"):
            with self.subTest(target=target):
                self.write_toml(self.build / "config/removed_app/old.toml", {"old": True})
                self.write_toml(self.generated("removed_section/old.toml"), {"old": True})
                self.build_targets(target)
                self.assertFalse((self.build / "config").exists())
                self.assertFalse((self.build / "genconfig").exists())
                self.assertEqual(source.read_bytes(), original)
                self.build_targets("config")
                self.assertEqual(self.read_generated("dev/capture.toml"), {"value": "initial"})

    def test_cleanup_remains_available_after_all_apps_are_removed(self):
        source = self.add_app("capture")
        self.registration = self.register("capture")
        self.configure()
        self.build_targets("config")
        self.apps = []
        self.registration = ""
        self.configure()
        self.build_targets("clean_config")
        self.assertFalse((self.build / "config").exists())
        self.assertFalse((self.build / "genconfig").exists())
        self.assertTrue(source.is_file())
        self.build_targets("config")


if __name__ == "__main__":
    unittest.main()
