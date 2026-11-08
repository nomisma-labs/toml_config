# toml_config tools

> **Documentation review draft — implementation pending.** This page defines the
> target contract. Commands and APIs below are implementation acceptance criteria,
> not claims that this checkout already supports them. See [status](../../TODO.md).

`config_path.sh` is available now and is copied unchanged from the JSON framework.
The remaining tools below are the implementation targets for this directory. Shared build and
maintenance tools live in [tools/kit](../kit/README.md).

| File | Purpose | Documentation |
|---|---|---|
| [config_path.sh](config_path.sh) | Sourceable Bash commands for selecting config search directories. | [Bash setup and commands](../../docs/toml_config/app_config_binding.md#selecting-search-directories-in-bash) |
| `tcfggen.py` | Command-line TOML config generator and metadata listing. | [Config generation](../../docs/toml_config/config_generation.md) |
| `tcfg.py` | Python engine that resolves tcfg sections into application TOML in memory. | [Python API](../../docs/toml_config/config_generation.md#python-api) |
| `tcfg_build.py` | Utility called by CMake to manage generation plans, output ownership, and successful build records. | [Build integration](../../docs/toml_config/build_system_integration.md) |

Run the generator from the repository root:

```bash
python3 tools/toml_config/tcfggen.py --help
```
