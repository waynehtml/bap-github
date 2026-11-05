# File operations and validation

## When to use this capability

Use these helpers in Databricks workloads that need to discover storage entries, read files through Spark, validate a delivery before ingestion, or transfer files through `dbutils.fs`.

## Choose the public API

| Need | Choose |
| --- | --- |
| Check, list, copy, move, delete, construct a URI, or read or write a small document | A focused helper in `oeds.core.file_utils` |
| Write a bounded Spark DataFrame to one named CSV file | `write_csv_file` |
| Reject malformed CSV, JSON, or XML immediately | `load_file_failfast` |
| Preserve nested shape while reading leaves as strings, then cast with diagnostics | `load_file_stringleaf`, followed by `cast_stringleaf_to_schema` |
| Discover files once and apply technical delivery rules | `find_files`, then one or more `validate_*` functions |

## Restrictions and side effects

`file_utils` relies on Databricks `dbutils.fs`. Its discovery helpers suppress listing/access errors, so `False` or an empty result may mean missing, inaccessible, or simply unmatched. `is_dir` means “listable”; it does not independently prove the item is a directory. Recursive selection matches basenames and can skip an inaccessible subtree.

`write_csv_file`, `write_text_file`, and `write_json_file` support Unity
Catalog Volume paths and ADLS `abfss` URIs. They create missing parent
directories and overwrite existing destinations by default. Pass
`overwrite=False` when replacement is not intended. Workspace files, local
paths, and legacy DBFS root paths are outside the write contract.

CSV output remains Spark-native. The writer coalesces the DataFrame to one
partition, writes Spark output to a unique sibling staging directory, moves the
single `part-*.csv` to the requested filename, and removes the staging
directory. Use it only for bounded extracts: `coalesce(1)` limits scalability,
and destination replacement is not atomic. Additional `csv_options` may control
Spark formatting, but header, path, mode, compression, codec, and extension
remain controlled or prohibited by the helper.

Text and JSON writes are intended for small in-memory documents.
`write_text_file` preserves its string exactly and writes UTF-8 through
`dbutils.fs.put`. `write_json_file` serializes a JSON-compatible value before
delegating to the text writer. Pass already serialized JSON to
`write_text_file` so it is not encoded again as a JSON string.

!!! danger "Destructive file operations"

    `delete_selected_files`, `delete_folder`, and every `move_*` helper remove source content. They provide no rollback. Multi-file operations run one file at a time, so failure can leave a partially completed transfer. Resolve and log the intended source and destination before calling them.

Copy operations are non-destructive but can still partially complete, and destination collision behavior is delegated to `dbutils.fs`.

The file readers perform Spark actions. Strict row-format reads perform a diagnostic retry after a parse failure. String-leaf reads cache their DataFrame without explicitly releasing it. Cast failures can log compact source-row samples, so avoid using sensitive fields at a verbose log level. Text/JSON reads use Spark `binaryFile`; a glob or directory with multiple matches returns one unspecified file.

File validation treats a normal rule mismatch as `success=False`; it does not raise. Discovery still inherits the suppressed-error behavior of `file_utils.ls`, so validate that an empty discovery result is acceptable for the workflow.

## Short example

```python
from oeds.core.file_utils import write_csv_file, write_json_file

csv_path = write_csv_file(
    dataframe=outbound_df,
    destination_path=(
        "/Volumes/example_catalog/example_schema/outbound/2026-08-15.csv"
    ),
    csv_options={"sep": ",", "nullValue": ""},
)

metadata_path = write_json_file(
    value={"file": csv_path, "record_count": outbound_df.count()},
    destination_path=(
        "/Volumes/example_catalog/example_schema/outbound/2026-08-15.json"
    ),
)
```

For discovery and validation:

```python
from oeds.core.file_validator import (
    find_files,
    validate_file_count,
    validate_file_extensions,
    validate_non_empty_files,
)

files = find_files(
    "/Volumes/example_catalog/example_schema/example_volume/inbox",
    pattern="*",
)
checks = (
    validate_file_count(files, minimum_count=1),
    validate_file_extensions(files, allowed_extensions=(".csv", ".csv.gz")),
    validate_non_empty_files(files),
)

failures = [check for check in checks if not check.success]
if failures:
    raise RuntimeError("; ".join(check.error_message or check.rule for check in failures))
```

## Related examples

- [Strict and string-leaf reader example](../../examples/file_reader/load_and_cast_files.py)
- [File validation example](../../examples/file_validator/validate_directory_files.py)
