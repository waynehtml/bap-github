# DataForge Configuration Catalog

Project-owned configuration is packaged under the `oeds.config` namespace.
The `conf` directory is a Python source root alongside `src`; reusable workflow
code remains under `src/oeds/domain`.

| Area | Purpose |
|---|---|
| [`datafile`](datafile/) | Source-file paths, formats, options, and schemas. |
| [`email`](email/) | Email registries and HTML templates. |
| [`fileloader`](fileloader/) | File-to-table mappings, transforms, validation rules, and write behavior. |
| [`ingest`](ingest/) | DataBridge ingestion, outbound-delivery, and [`email.json`](ingest/email.json) email-job templates. |
| [`permission`](permission/) | Unity Catalog group and object grants with optional environment-specific resource overrides. |
| [`project`](project/) | Non-secret project files and environment-specific resource overrides. |
| [`schema`](schema/) | Table and view definitions. |
| [`timeseries`](timeseries/) | Time-series providers, datasets, series, and publishing metadata. |

Import configuration by its canonical package path, for example
`oeds.config.schema` or `oeds.config.email`. Keep secrets and environment-specific
credentials outside these source-controlled files.

Module-backed configuration consumers use `ConfigManager` to select direct
public modules. Place shared definitions directly under an area package and
optional overrides under `<area>/<environment>/`. An environment module
replaces the shared module with the same basename; environment-only and
shared-only modules are both retained. Overrides replace complete modules
rather than merging `DEFINITION` dictionaries.
