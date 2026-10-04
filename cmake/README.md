# cmake/

- `kit/`: the Nomisma CMake kit. It is **template-owned**: change it only in `cmake_template`,
  then pull the change into derived repos with `tools/sync_template.py`. Reference: `docs/build.md`.
- Anything else in this directory is repo-specific (for example, the config repo's
  `config_generator.cmake`) and is never touched by the sync.
