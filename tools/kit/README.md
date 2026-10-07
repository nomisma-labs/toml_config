# tools/kit

The shared tools every Nomisma repo gets from `cmake_template`. They are template-owned: change
them in `cmake_template`, and `sync_template.py` brings them to the other repos. A repo's own
tools go in `tools/`, outside the kit.

| Tool | Use |
|---|---|
| `checks/python.py` | Python version, script syntax and imports; bootstrap runs it before builds |
| `checks/headers.py` | the SPDX header in every source file |
| `checks/format.sh` | C++ formatting against `.clang-format`; `--fix` reformats |
| `checks/naming.sh` | naming rules from `.clang-tidy`, over a `clang` build of every app |
| `checks/version.py` | prints the version in `project()`, or checks a release tag against it |
| `sync_template.py` | brings the template-owned files up to a `cmake_template` release |
| `add_sandbox_app.py` | adds an experiment in `apps/sandbox/` |
| `python_package_requirements.txt` | pinned tools for optional Python wheel builds |

`./bootstrap.sh` and CI run the checks ([docs/kit/build.md](../../docs/kit/build.md#checks-and-ci)).
[docs/kit/new_repo.md](../../docs/kit/new_repo.md#keeping-repos-in-sync) describes the sync.
