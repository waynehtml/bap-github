# Land To Raw Flow Guide

This guide explains how to copy a file batch from the landing zone to the raw zone in the Dataforge template. Validation is optional. Landing files remain in place after both successful and failed runs.

## Processing Contract

The `land_to_raw` stage follows four rules:

1. Read from a durable landing batch and write to the corresponding raw batch.
2. Run technical file validation before copying when the source requires it.
3. Use a copy function from DataKit. Do not use the move or delete functions for durable landing data.
4. Leave landing-zone cleanup to the storage retention policy.

See [Landing Zone Best Practices](../standards-and-practices/landing_zone_best_practices.md) for the required landing layout, governed Unity Catalog Volume access, rerun behavior, and retention guidance.


## Key Locations

- [task_20_land_to_raw.py](../../jobs/dataflow/task_20_land_to_raw.py): template task that resolves batch paths, validates landed files, and performs a selected copy.
- [DataKit file-validator API](../reference/datakit/api/file_validator.md): shared discovery and technical validation functions.
- [DataKit file-utility API](../reference/datakit/api/file_utils.md): shared copy functions.
- [Landing Zone Best Practices](../standards-and-practices/landing_zone_best_practices.md): authoritative landing layout and retention guidance.

## Resolve One Batch

Resolve `land_dir` and `raw_dir` for the same logical batch before validation or copy. The template task uses the processing date published by the `main` task and builds both paths from `job_ctx`:

```python
from pathlib import Path

land_dir = str(Path(job_ctx.get("land_root")) / file_date)
raw_dir = str(Path(job_ctx.get("raw_root")) / file_date)
```

Keep provider, dataset, and ingestion date or timestamp in the landing path. Use the raw layout required by downstream processing, but keep the mapping deterministic so a rerun targets the same logical raw batch.

## Optional File Validation

Discover the batch once with `find_files`, then pass the returned immutable file metadata to each required validator. A normal rule mismatch returns `FileValidationResult(success=False)`; invalid configuration and storage failures raise exceptions.

```python
from oeds.core.file_validator import (
    find_files,
    validate_file_count,
    validate_file_extensions,
    validate_file_names,
    validate_non_empty_files,
)
from oeds.domain.exceptions import LandToRawTaskError

landed_files = find_files(land_dir, pattern="*", recursive=True)

validation_results = (
    validate_file_count(landed_files, minimum_count=1),
    validate_non_empty_files(landed_files),
    validate_file_names(
        landed_files,
        allowed_patterns=(r"transactions_\d{8}\.csv(?:\.gz)?",),
    ),
    validate_file_extensions(
        landed_files,
        allowed_extensions=(".csv", ".csv.gz"),
    ),
)

failed_results = [result for result in validation_results if not result.success]
if failed_results:
    messages = [
        result.error_message or f"Validation rule failed: {result.rule}"
        for result in failed_results
    ]
    raise LandToRawTaskError("; ".join(messages))
```

Only configure rules that the source needs. Remove the entire validation block when no technical validation is required.

| Function | Use | Important behavior |
| --- | --- | --- |
| `find_files` | Discover file metadata once | `pattern` is a filename glob; `recursive=True` includes subdirectories. |
| `validate_file_count` | Require an exact, minimum, or maximum count | An optional `name_pattern` is a case-sensitive regular expression evaluated with `re.fullmatch`. |
| `validate_non_empty_files` | Reject zero-byte files | Optional include and exclude patterns are regular expressions; exclusions take precedence. |
| `validate_file_names` | Allow only expected filename formats | Every filename must fully match at least one case-sensitive regular expression. |
| `validate_file_extensions` | Allow only expected suffixes | Matching is case-insensitive and supports compound suffixes such as `.csv.gz`. |

On failure, `result.files` contains the files relevant to that rule. Log detailed file paths at `debug` level when needed, raise `LandToRawTaskError`, and do not begin the copy.

## Choose A Copy Strategy

Use exactly one copy strategy for a batch.

| Strategy | Function | Best for | Selection and layout | Return value |
| --- | --- | --- | --- | --- |
| Full tree | `copy_full_folder` | Every file and subdirectory belongs in raw | Copies the entire directory recursively. | `None` |
| Selected files | `copy_selected_files` | A glob identifies the files to promote | Matches filenames and preserves relative subdirectories when recursive. | Destination paths |
| Resolver-based grouping | `copy_files_by_group` | Code must choose a raw subfolder for each file | Passes each relative source path to a resolver and keeps the original filename. | Destination paths |

All three functions copy data. They do not remove files from the landing zone.

### Full Tree Copy

Use a full copy when the whole landing batch belongs in the same raw batch.

```python
import oeds.core.file_utils as fileutils

fileutils.copy_full_folder(land_dir, raw_dir)
```

`copy_full_folder` recursively copies the directory tree. The source must exist and be a directory, and the destination must not be an existing file.

### Selected Copy

Use a selected copy when filenames determine which files are promoted. This is the default template pattern.

```python
copied_files = fileutils.copy_selected_files(
    src_dir=land_dir,
    dst_dir=raw_dir,
    pattern="*.csv",
    recursive=True,
)
```

The glob is applied to each filename, not the complete relative path. With `recursive=True`, matching files in subdirectories retain their relative subdirectory structure under `raw_dir`.

### Resolver-Based Copy

Use a resolver when each file must be routed to a computed raw subfolder.

```python
from pathlib import PurePosixPath

def resolve_entity(relative_path: str) -> str | None:
    file_name = PurePosixPath(relative_path).name
    if file_name.startswith("customer_"):
        return "customer"
    if file_name.startswith("account_"):
        return "account"
    return None

copied_files = fileutils.copy_files_by_group(
    src_dir=land_dir,
    dst_dir=raw_dir,
    resolver=resolve_entity,
    file_pattern="*.csv",
    policy="fail",
    recursive=True,
)
```

The resolver receives a source path relative to `land_dir`. The `file_pattern` glob is also evaluated against that relative path. The resolver must return a relative destination subfolder or `None`; it does not return the destination filename.

| Policy | Behavior when the resolver returns `None` |
| --- | --- |
| `default` | Copy the file directly under `raw_dir`. |
| `skip` | Do not copy the file. |
| `fail` | Raise `ValueError` and fail the transfer. |

Resolver output must not start with `/` and must not contain empty, `.` or `..` path segments. The copy preserves each basename but does not automatically preserve the original directory tree. Ensure two source files with the same basename cannot resolve to the same destination path.

## Failure And Rerun Behavior

- Complete validation before starting the copy so a validation failure leaves raw unchanged.
- Wrap discovery, validation, and copy errors in `LandToRawTaskError` while preserving the original exception as the cause.
- Log the source, destination, selected strategy, and copied file count at `info` level. Put verbose file lists in `debug` logs.
- Treat a copy retry as a rerun of the same logical batch. Confirm the destination overwrite behavior is acceptable for the project.
- A copy operation can fail after some files have reached raw. Make the raw layout rerunnable and verify the copied outputs when partial I/O is a concern.
- Never call `move_single_file`, `move_selected_files`, `move_full_folder`, `move_files_by_group`, `delete_selected_files`, or `delete_folder` against durable landing data.
- Do not add landing cleanup to success or failure handlers. The storage retention policy owns cleanup.

## Implementation Checklist

- Landing storage is accessed through an approved Unity Catalog Volume.
- Landing folders follow the provider, dataset, and date or timestamp convention.
- `land_dir` and `raw_dir` identify the same logical batch.
- Validation is either intentionally omitted or runs before copy.
- Exactly one copy strategy is selected.
- Glob and resolver behavior is tested against nested paths and unexpected files.
- Real failures raise `LandToRawTaskError` with useful context.
- Landing files are neither moved nor deleted by the pipeline.
- Storage retention, not pipeline logic, manages landing cleanup.

## Related Guides

- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand how `land_to_raw` fits into the `DATAFLOW` workflow.
- [DataBridge Client User Guide](G220-ingest-client-guide.md): ingest source files into the landing zone.
- [Landing Zone Best Practices](../standards-and-practices/landing_zone_best_practices.md): follow landing layout, reload, audit, and retention requirements.
