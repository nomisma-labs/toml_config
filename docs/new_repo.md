# New repos from the template

New Nomisma C++ repos are created from `cmake_template` with GitHub's *template repository*
feature, then emptied by `tools/init_project.py`.

## How the feature works

- The new repo gets the template's files as **one initial commit**: no history, and no link back
  to the template.
- Only the default branch is copied. Leave "Include all branches" off.
- Submodules come across as they are (`.gitmodules` and the pinned commits). Relative URLs such as
  `../config.git` resolve within the same organization.
- Files stored in Git LFS are not supported (we don't use LFS).
- Repo settings are not copied: branch protection, Actions secrets and variables, access, webhooks.

## One-time setup

1. Create the GitHub organization. Pick a lowercase name: container image names must be lowercase.
2. Push `cmake_template` as a private repo. Set `url` in `.template_ref` to its clone URL.
   The template leaves `url` and `sha` blank until then; do not put a placeholder URL there.
3. **Settings → General → Template repository** (needs admin rights on the repo).
4. Run the `ci-image` workflow (Actions tab, or push a change under `docker/ci/`). Then make the
   `ci` package public (the organization's Packages page → `ci` → Package settings → Change
   visibility). It holds only public tools, and a public image needs no per-repo access.
5. Check that the template's `ci` workflow is green.
6. Tag the first release, `v0.1.0` ([build.md](build.md#versioning)).

## Creating a repo

```bash
gh repo create <org>/<name> --private --template <org>/cmake_template --clone
cd <name>
python3 tools/init_project.py <name>
./bootstrap.sh
git push
```

(In the browser: "Use this template" → "Create a new repository", then clone and continue from
`python3 tools/init_project.py`.)

`tools/init_project.py <name>` turns the copy into an empty repo. It removes the template's example
code instead of renaming it:

- deletes the example code (`core/example/`, `apps/hello/`, the example unit tests and the library usage
  test project, the nlohmann submodule), the lab (the sandbox experiments, `docs/lab/`) and the
  template-only files (`docker/`, the `ci-image` workflow, and itself);
- retains the Metal v2.1.4 submodule and `nom_find_metal()` call as the shared dependency baseline;
- deletes the lines and blocks the template marks as template-only;
- sets the name and version `0.1.0` in `project()`; the options and the package name derive from it;
- puts the name and a TODO description into `README.md` and `AGENTS.md`, and starts an empty
  `CHANGELOG.md`;
- resolves the template URL and commit, records both in `.template_ref`, and commits. If the
  URL is unset or unreachable, it stops without changing the new repo. You can provide
  `--template-url <url>` instead of setting the URL in the template.

It checks everything first and stops without changing anything if the repo doesn't look like a
fresh copy of the template. `./bootstrap.sh` validates the initialized repo locally; its regular
`ci` workflow validates it on GitHub. The new repo starts without example tests; add your own
code and tests with the recipes in [howto.md](howto.md), then run bootstrap again.
Define new Nomisma library APIs in named modules and import them in apps and tests.
Keep macro headers and third-party dependency headers where needed.

## Per-repo settings

- **Branch protection** on `master` (pull requests only, CI must pass): private repos need the
  GitHub Team plan. On the Free plan, keep to the same discipline by hand.
- **Private submodules in CI:** the token GitHub Actions gives each job can read only its own
  repo, so checking out one of our private repos (for example `external/config`) fails. Use an
  organization-owned GitHub App with read-only access to repository contents:
  - before adding the first private dependency, add token support in `cmake_template` and sync
    it into derived repos: each workflow gets a short-lived token with
    `actions/create-github-app-token` and passes it to `actions/checkout` (`token:`, with
    `submodules: recursive`);
  - the App's ID and private key are Actions secrets. On the Free plan private repos can't use
    organization secrets, so each repo needs its own copy.

  The template itself has only public submodules, so it doesn't need this yet.

## Keeping repos in sync

Template-owned paths are `bootstrap.sh`, `cmake/kit/`, `tools/`, the shared docs (`docs/build.md`,
`docs/conventions.md`, `docs/howto.md`, this file), `.clang-format`, `.clang-tidy`, `.clangd`,
`.editorconfig` and `.github/workflows/ci.yml`. Change them only in `cmake_template`. To bring a
repo up to date:

```bash
python3 tools/sync_template.py        # or --to <template release tag>, such as --to v0.2.0
git diff --cached                     # review staged template changes
git diff -- .template_ref             # review the new upstream revision
git add .template_ref                 # the script leaves this file unstaged
git commit -m "Sync with cmake_template"
```

The script diffs the template-owned paths between the template commit in `.template_ref` and the
template's newest commit (or the given tag), applies the difference with `git apply --3way`, and
updates `.template_ref`.

The sync transfers shared build rules and guidance, not repository-owned code. A change to the
composition policy therefore has two parts: sync the template-owned paths, then migrate the
repo's `core/`, apps, tests and CMake target declarations to that policy. For the native module
transition, move library declarations into interfaces or partitions, and make all consumers
import the primary module. Keep macro and dependency
headers where their boundary requires them, and validate source and installed-package usage.

The script syncs committed template revisions, not uncommitted working-tree changes. While
reviewing an unpublished template change, keep its shared files in the template checkout;
assess the repo-specific migration separately and perform the recorded sync once the template
revision is available.

Dependency migrations also update repository-owned files: sync supplies `nom_find_metal()`,
but existing repos add or retain the Metal submodule in `.gitmodules`, call the helper from their
top-level `CMakeLists.txt`, and use `nom::metal` in place of local adapters. Public dependency
declarations in installed packages use `nom_metal`.
