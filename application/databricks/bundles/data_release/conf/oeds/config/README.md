# DataForge Configuration Catalog

Project-owned configuration is packaged under the `oeds.config` namespace.
The `conf` directory is a Python source root alongside `src`; reusable workflow
code remains under `src/oeds/domain`.

| Area | Purpose |
|---|---|
| [`datafile`](datafile/) | Source-file paths, formats, options, and schemas. |
| [`email`](email/) | Email registries and HTML templates. |
| [`fileloader`](fileloader/) | File-to-table mappings, transforms, validation rules, and write behavior. |
| [`ingest`](ingest/) | DataBridge ingestion and outbound-delivery request templates. |
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

DataForge Testbench case definitions are not packaged under `oeds.config`.
Testbench loads `cases/default.json` from the bundle's configured `case_root`;
a run may select another `case_root` or `case_name`. Parquet table data remains
under `fixtures/<table>/`, input data under `inputs/`, and expected data under
`expected/<verification-name>/`. Cases may define repeated non-secret string
values once under `variables` and reference them from JSON string values with
`{{ variable_name }}`. Variable definitions must be literal and cannot
reference one another. After relative `extends` inheritance, matching non-null
string values from SERVICE `args` override the merged defaults before the config
is rendered in one Jinja2 pass. See the
[Integration Test Guide](../../../docs/guide/G401-integration-test-guide.md)
for the complete storage and case-definition contract.
