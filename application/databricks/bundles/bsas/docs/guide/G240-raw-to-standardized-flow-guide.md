# Raw To Standardized Flow Guide

This guide explains how to convert one raw file batch into a validated standardized Delta table in the Dataforge template. It follows the reference implementation in `task_30_raw_to_std.py` and uses the shared DataKit and Dataforge APIs directly.

## Processing Contract

The `raw_to_std` stage follows these rules:

1. Process the same logical batch selected by the `main` task.
2. Resolve input format, schema, reader options, and relative path from the datafile registry.
3. Read raw data strictly and surface malformed input at the extraction boundary.
4. Capture source file metadata before projections remove access to hidden Spark metadata.
5. Normalize and transform the source into the standardized table shape.
6. Add stable batch audit fields and a run-specific load identifier.
7. Complete business validation before writing any standardized records.
8. Resolve the target through the schema registry and use an intentional Delta write mode.
9. Record a successful operation only after the standardized Delta write commits.

The reference task reads raw files without modifying or deleting them.


## Key Locations

- [task_30_raw_to_std.py](../../jobs/dataflow/task_30_raw_to_std.py): reference task and execution order.
- [file_sample.py](../../conf/oeds/config/datafile/file_sample.py): sample raw-file registry entry.
- [datafile_utils.py](../../src/oeds/domain/utils/datafile/datafile_utils.py): `DatafileManager` and `DatafileRegistry`.
- [DataKit file-reader API](../reference/datakit/api/file_reader.md): strict file loading.
- [DataKit DataFrame-utility API](../reference/datakit/api/df_utils.md): column selection and normalization.
- [DataKit DataFrame-validator API](../reference/datakit/api/df_validator.md): business-rule execution.
- [DataKit Unity Catalog API reference](../reference/datakit/api/uc_utils.md): Delta batch writes.
- [tbl_sample.py](../../conf/oeds/config/schema/tbl_sample.py): sample standardized-table registry entry.
- [DataFrame Validator Guide](G245-dataframe-validator-guide.md): complete validator catalog and result contract.

## Resolve The Batch Boundary

Read the processing date and raw zone root:

```python
from datetime import date

file_date = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="file_date",
    debugValue=date.today().isoformat(),
)
raw_root = job_ctx.get("raw_root")
```

`file_date` identifies the logical batch and later becomes `audit_batch_id`. The
reference raw-to-standard task composes its source as
`raw_root/file_date/datafile.path`; the registry path does not contain a date
template.

Use `job_ctx["job_run_id"]` as `audit_load_id`. It identifies the execution that loaded the batch, while `audit_batch_id` stays stable across retries.

## Define And Prepare Raw Inputs

Each module in `oeds.config.datafile` contributes one registry entry. The module name is the reference used by `DatafileManager`.

```python
DEFINITION = {
    "path": "tbl_sample.csv",
    "format": "csv",
    "options": {
        "encoding": "windows-1252",
        "header": "true",
    },
    "schema": SCHEMA,
}
```

Resolve the registry and complete raw path before reading:

```python
from oeds.domain.utils.datafile import DatafileManager

raw_file_ref = "file_sample"
datafile_manager = DatafileManager.get_instance()
raw_file_config = datafile_manager.find(raw_file_ref)
raw_file_path = (
    f"{str(raw_root).rstrip('/')}/{str(file_date).strip('/')}/"
    f"{str(raw_file_config.path).lstrip('/')}"
)
```

| API | Purpose |
| --- | --- |
| `DatafileManager.find(name)` | Return a `DatafileRegistry` containing `path`, `format`, `options`, and `schema`. |

The task owns the date segment and final path composition. The registry path is
used literally. Keep source-specific parsing details in the registry instead of
scattering format options and schemas through task notebooks.

## Read Raw Data Strictly

Pass the resolved registry values to `load_file_failfast`:

```python
from oeds.core.file_reader import load_file_failfast

raw_df = load_file_failfast(
    raw_file_path,
    raw_file_config.format,
    schema=raw_file_config.schema,
    options=raw_file_config.options,
)
```

For CSV, JSON, and XML, the helper reads in Spark `FAILFAST` mode and materializes the DataFrame before returning. If strict parsing fails, it performs a diagnostic-only permissive read to report corrupt records; permissive rows are never returned. Parquet and Delta are read directly and materialized once so schema and I/O errors still surface in this stage.

The supported formats are CSV, JSON, XML, Parquet, and Delta. The helper owns parser mode and corrupt-record options, so caller-provided `mode` and `columnNameOfCorruptRecord` values are ignored.

### Capture Source File Metadata

Promote the hidden Spark source path before selecting or rebuilding columns:

```python
from pyspark.sql import functions as F

raw_df = raw_df.withColumn(
    "audit_source_file_path",
    F.col("_metadata.file_path").cast("string"),
)
```

Later projections may remove access to `_metadata`. Capturing the path immediately preserves record-level lineage in the standardized table.

## Standardize And Transform

The DataKit DataFrame helpers provide predictable technical normalization:

```python
from oeds.core.df_utils import (
    normalize_column_names,
    normalize_nulls,
    select_columns,
)

standardized_df = normalize_column_names(
    raw_df,
    lowercase=True,
    replace_spaces=True,
    replace_hyphens=True,
    remove_special=True,
    collapse_underscores=True,
    strip_underscores=True,
)

standardized_df = select_columns(
    standardized_df,
    [
        "number",
        "category",
        "country",
        "amount",
        "minimum_amount",
        "audit_source_file_path",
    ],
)

standardized_df = normalize_nulls(
    standardized_df,
    null_values=["", "N/A", "NA", "NULL", "None"],
)
```

| API | Important behavior |
| --- | --- |
| `normalize_column_names` | Normalizes selected top-level and nested field names. It fails if normalization creates an empty or duplicate name. |
| `select_columns` | Validates that every requested top-level column exists and returns them in the requested order. |
| `normalize_nulls` | Trims and case-normalizes configured string markers before replacing them with Spark nulls, including nested values. |

After technical normalization, use explicit Spark expressions for source-specific casts, code mappings, date and timestamp parsing, derived values, and field renames. Build the final DataFrame in the same order and types expected by the standardized table definition.

## Add Audit Columns

Every standardized record should carry batch, load, timestamp, and source lineage fields:

```python
audit_batch_id = str(file_date).strip()
audit_load_id = str(job_ctx.get("job_run_id") or "").strip()
if not audit_batch_id:
    raise RawToStdTaskError("file_date is required for audit_batch_id")
if not audit_load_id:
    raise RawToStdTaskError("job_run_id is required for audit_load_id")

audit_timestamp = F.current_timestamp()
standardized_df = standardized_df.select(
    "number",
    "category",
    "country",
    "amount",
    "minimum_amount",
    F.lit(audit_batch_id).cast("string").alias("audit_batch_id"),
    F.lit(audit_load_id).cast("string").alias("audit_load_id"),
    audit_timestamp.alias("audit_created_ts"),
    audit_timestamp.alias("audit_last_update_ts"),
    F.col("audit_source_file_path").cast("string").alias("audit_source_file_path"),
)
```

Use one timestamp expression so the created and updated timestamps agree for the initial load. Do not populate an identity or generated target key in this DataFrame; let the Delta table definition own it.

## Validate Business Rules

Define stable, explicitly named rules and run them after the standardized shape is complete:

```python
from oeds.core.df_validator import Rules, validate_df

business_rules = [
    Rules.not_null("number", name="number_required"),
    Rules.unique("number", name="number_unique"),
    Rules.in_set(
        "category",
        ["retail", "enterprise", "public"],
        name="category_supported",
    ),
    Rules.gte_col(
        "amount",
        "minimum_amount",
        name="amount_meets_minimum",
    ),
]

validation_result = validate_df(standardized_df, business_rules)
if not validation_result.success:
    failed_rules = [
        result.expectation
        for result in validation_result.results
        if not result.success
    ]
    raise RawToStdTaskError(
        f"Business validation failed for {len(failed_rules)} rule(s): "
        f"{', '.join(failed_rules)}"
    )
```

A business-rule mismatch returns a structured `DataFrameValidationResult`; the task decides to fail before writing. Invalid rule configuration and execution failures raise exceptions. See the [DataFrame Validator Guide](G245-dataframe-validator-guide.md) for all rule factories, null behavior, conditional rules, nested paths, and secure handling of sample rows.

Log failed rule names and counts at normal operational levels. Validation messages and sample rows may contain source values, so expose row-level diagnostics only through an approved secure workflow.

## Resolve And Load The Target

The standardized table definition owns its catalog, database, table name, schema, SQL, and generated-column metadata. Resolve it through the cached schema manager loaded by `common.py`:

```python
from oeds.core.uc_utils import delta_batch_update
from oeds.domain.utils.operation import OperationStatusManager

standardized_table = SchemaManager.get_instance().find("tbl_sample")

delta_batch_update(
    standardized_df,
    standardized_table.full_name,
    mode="replace",
    batch_column="audit_batch_id",
    batch_id=audit_batch_id,
)

OperationStatusManager().record_status(
    dataset=job_ctx["dataset"],
    layer="standardization",
    batch_id=audit_batch_id,
    job_run_id=job_ctx.get("job_run_id"),
    job_name=job_ctx.get("job_name"),
    job_id=job_ctx.get("job_id"),
    job_trigger_type=job_ctx.get("job_trigger_type"),
    job_context=job_ctx,
)
```

The target table must be deployed before this workflow runs. See the [Schema Guide](G211-schema-guide.md) for table definitions and release-time creation.

Keep these as separate failure boundaries. Read, validation, or Delta-write
failures must not create an operation-status row. Once the Delta write commits,
the marker records that the dataset, layer, and batch completed successfully.
If marker persistence fails, log that the data load committed, wrap the failure
in `RawToStdTaskError`, and fail the task so downstream dependency checks do not
mistake a missing marker for a completed batch.

| Mode | Behavior | Batch arguments |
| --- | --- | --- |
| `append` | Add every DataFrame row. | Must be omitted. |
| `replace` | Atomically replace rows matching `batch_column = batch_id` using Delta `replaceWhere`. | Required. |
| `overwrite` | Replace the complete table. | Not used. |

`replace` is the recommended template mode because a retry replaces the same logical batch instead of duplicating it. The batch column must exist in the DataFrame, and the Python type of `batch_id` must match a supported Spark string, integer, or date column. An empty DataFrame in `replace` mode removes the matching target batch, so decide whether that behavior is acceptable before allowing an empty standardized result.

`evolve_schema` defaults to `False`. Enable it only when the schema change is intentional and compatible with the table contract.

## Failure Boundaries

Keep the orchestration readable and wrap each major boundary with `RawToStdTaskError` while preserving the original exception:

- Raw-path resolution and strict input loading.
- Source metadata capture.
- Source-specific transformation and audit-column construction.
- Business-validation execution and failed business rules.
- Target-registry lookup and Delta write.
- Successful-operation marker persistence after the Delta write commits.

Use `logger.exception` inside exception handlers so stack traces remain available. Include file references, batch IDs, load IDs, and target names in messages, but do not log sensitive payload contents.

Validation must finish before the Delta write begins. Delta batch replacement is transactional, but earlier Spark transformations are lazy; keep explicit materialization at the read and validation boundaries so failures occur in the intended task stage.

## Implementation Checklist

- `file_date`, the resolved raw batch directory, and `job_run_id` are present and identify the intended batch and run.
- The datafile registry owns the relative path, format, schema, and Spark reader options.
- `load_file_failfast` materializes and validates the raw input.
- Source file metadata is promoted before column projections.
- Standardized fields are normalized, selected, transformed, and ordered intentionally.
- Audit batch, load, timestamp, and source-path columns are populated.
- Business rules have stable names and complete before any table write.
- The target resolves through `SchemaManager.get_instance()` and already exists.
- The Delta write mode and rerun behavior are intentional.
- The operation-status marker is written only after the Delta write commits.
- Exceptions preserve causes and logs contain actionable identifiers without sensitive values.
- Raw source files are not modified or deleted.

## Related Guides

- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand how `raw_to_std` fits into the `DATAFLOW` workflow.
- [Datafile Module Developer Guide](G225-datafile-developer-guide.md): define and resolve the source file contract used by this flow.
- [Land To Raw Flow Guide](G230-land-to-raw-flow-guide.md): prepare the raw file batch consumed by this flow.
- [DataFrame Validator Guide](G245-dataframe-validator-guide.md): define and interpret standardized-record validation rules.
- [Schema Guide](G211-schema-guide.md): define and deploy standardized Delta tables.
