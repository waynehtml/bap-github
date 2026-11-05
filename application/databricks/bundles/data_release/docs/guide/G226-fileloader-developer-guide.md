# Fileloader Developer Guide

This guide explains how to define and run Dataforge file-to-table load mappings. A mapping connects a registered source file to a registered target table and owns the normalization, optional transformation, validation, and Delta write policy for that relationship.

Use `FileLoader` for controlled single-file-to-single-table loads. Use a dedicated workflow task when processing requires joins, aggregations, multiple outputs, quarantine handling, or other orchestration.

## Processing Model

`FileLoader` executes one mapping in a fixed order:

1. Resolve the source through `DatafileManager` and the target through `SchemaManager`.
2. Read the source with its registered format, options, and schema.
3. Apply configured column-name and null-value normalization.
4. Call the optional full-DataFrame transform.
5. Evaluate configured DataFrame validation rules.
6. Write the resulting DataFrame using the effective write mode.

The Datafile registry remains the source-read contract. The Schema registry remains the target-table contract. The Fileloader mapping owns only the relationship and processing policy between them.

## Define A Mapping

Create one Python module under `conf/oeds/config/fileloader`. The module filename becomes its load ref. Use a `load_` prefix because the definition represents the complete load operation, not only a column mapping.

```python
from typing import Any

from oeds.core.df_validator import Rules
from pyspark.sql import DataFrame, functions as F


def transform_reference_data(
    df: DataFrame,
    context: dict[str, Any] | None,
) -> DataFrame:
    runtime_context = (context or {}).get("_runtime", {})
    batch_column = runtime_context.get("batch_column")
    batch_id = runtime_context.get("batch_id")

    transformed_df = df.select(
        F.col("number").cast("long").alias("number"),
        F.upper(F.col("country")).cast("string").alias("country"),
    )
    if batch_column and batch_id is not None:
        transformed_df = transformed_df.withColumn(batch_column, F.lit(batch_id))
    return transformed_df


DEFINITION = {
    "file_ref": "file_sample",
    "tbl_ref": "tbl_sample",
    "normalize": {
        "column_names": True,
        "null_values": ["", "N/A", "NA", "NULL", "None"],
    },
    "transform": transform_reference_data,
    "rules": [
        Rules.not_null("number", name="number_required"),
        Rules.in_set("country", ["CA", "US"], name="country_supported"),
    ],
    "write": {
        "mode": "overwrite",
        "batch_column": "audit_batch_id",
    },
}
```

| Field | Required | Purpose |
| --- | --- | --- |
| `file_ref` | Yes | Datafile registry ref used to resolve and read the source. |
| `tbl_ref` | Yes | Schema registry ref used to resolve the target table. |
| `normalize` | No | Column-name and null-value normalization applied before transformation. |
| `transform` | No | Callable that converts the normalized DataFrame to the target shape. |
| `rules` | No | Sequence of `Rule` objects evaluated after transformation. |
| `write` | No | Delta write policy. Its mode defaults to `overwrite`. |

The deprecated top-level `mode` field remains accepted for compatibility. New mappings should use `write.mode`; configuring both fields is an error.

### Configuration Discovery

Run `common.py` to initialize `ConfigManager`, `SchemaManager`, and
`DatafileManager`. FileLoader is intentionally not initialized by bootstrap;
each consumer may call `FileLoader.initialize(env).get_instance()`. That
initialization discovers an immutable map of effective
`oeds.config.fileloader` module names. A
mapping under `oeds.config.fileloader.<environment>` replaces the shared
mapping with the same module basename. Environment-only and shared-only
mappings are both retained, and overrides replace complete modules rather than
merging fields.

Every `get_instance()` call returns a new caller-owned loader using the stored
module-map snapshot and fresh SchemaManager and DatafileManager dependencies.
The three environments must match. `find(ref)` imports and validates only the
requested mapping through `ModuleMap.import_module()`. Storage belongs to each
`load_file` call rather than the loader instance. `get_module_map()` returns a
printable defensive `dict` of discovered refs and their selected full module
names for diagnostics; reading it does not import definition modules.

## Normalization

The optional `normalize` object supports:

| Field | Type | Default | Behavior |
| --- | --- | --- | --- |
| `column_names` | `bool` | `False` | Apply the shared default recursive column-name normalization. |
| `null_values` | Collection of strings | Not configured | Convert matching trimmed, case-insensitive string values to null. |

Omitting `normalize` leaves the source DataFrame unchanged. An unknown
normalization field or invalid field type fails when that mapping is requested.

## Transform Contract

The transform retains the existing interface:

```python
def transform(
    df: DataFrame,
    context: dict[str, Any] | None,
) -> DataFrame:
    ...
```

`df` is the normalized source DataFrame. The callable must return a PySpark `DataFrame`; returning another type fails the load. It should implement target projection, renaming, casting, and derived columns without writing tables or moving files.

`FileLoader` copies the caller context and adds a reserved `_runtime` object before invoking the transform:

```python
{
    # caller-provided context values remain at the top level
    "_runtime": {
        "ref": "load_sample",
        "file_ref": "file_sample",
        "tbl_ref": "tbl_sample",
        "mode": "replace",
        "batch_column": "audit_batch_id",
        "batch_id": "2026-07-22",
    },
}
```

The resolved mode is always present. `batch_column` and `batch_id` are included only when provided. Callers must not supply the reserved `_runtime` key themselves.

## Validation

Define validation with the shared `Rules` factories. Rules run against the final transformed DataFrame, so column paths refer to target-shaped names.

```python
"rules": [
    Rules.not_null("number", name="number_required"),
    Rules.unique("number", name="number_unique"),
]
```

If any rule fails, `FileLoader` logs the failed rule names, raises `RuntimeError`, and does not write the DataFrame. Detailed invalid values remain in the validator result rather than normal operational logs.

## Write Modes

The `write` object supports:

| Mode | Behavior | Batch configuration |
| --- | --- | --- |
| `append` | Add every row to the target. | `batch_id` must be omitted. |
| `overwrite` | Replace the complete target table. | `batch_id` must be omitted. |
| `replace` | Atomically replace rows for one logical batch. | `write.batch_column` and runtime `batch_id` are required. |

Configure the normal default on the mapping:

```python
"write": {
    "mode": "replace",
    "batch_column": "audit_batch_id",
}
```

`batch_column` may also be configured on an `append` or `overwrite` mapping so a runtime mode override can select `replace`. The transformed DataFrame must contain that column, and its Spark type must be compatible with the runtime `batch_id`.

## Run A Mapping

```python
from oeds.domain.utils.fileloader import FileLoader

file_loader = FileLoader.initialize(job_ctx["env"]).get_instance()
print(file_loader.get_module_map())

file_loader.load_file(
    ref="load_sample",
    file_base_uri=land_root,
    mode="replace",
    batch_id=str(file_date),
    context=job_ctx,
)
```

The runtime `mode` overrides `write.mode`. Resolution order is:

1. Nonblank `load_file(mode=...)` value.
2. Configured `write.mode`.
3. Default `overwrite`.

`batch_id` follows `mode` in the keyword-only API. It accepts the string, integer, or `datetime.date` type required by the configured batch column and the shared Delta writer.

`ref` is required. When `file_base_uri` is provided, FileLoader joins it to the
path in the referenced Datafile registry. When it is omitted or blank, FileLoader
uses the registry path unchanged. FileLoader does not substitute path parameters;
the caller must prepare parameterized paths before invoking it. One call processes
one mapping and returns `None`; task notebooks own any compact completion metadata
they emit.

## Developer Checklist

- The module uses a stable `load_` ref.
- `file_ref` and `tbl_ref` identify the intended source and target contracts.
- Normalization is enabled only when its behavior matches the source.
- The transform returns a target-shaped DataFrame and has no write side effects.
- Validation rules use explicit names and target-shaped column paths.
- `write.mode` is one of `append`, `overwrite`, or `replace`.
- Replace-capable mappings configure `write.batch_column`.
- Replace calls supply a compatible runtime `batch_id`.
- Caller context does not contain the reserved `_runtime` key.

## Related Guides

- [Datafile Module Developer Guide](G225-datafile-developer-guide.md): define source paths and read contracts.
- [Schema Guide](G211-schema-guide.md): define and deploy target tables.
- [DataFrame Validator Guide](G245-dataframe-validator-guide.md): select and interpret validation rules.
- [Service Job Guide](G202-service-job-guide.md): invoke operational utility notebooks.
