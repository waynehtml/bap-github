# Operation Status

Use `OperationStatusManager` to append successful processing records to the
configured Delta operation-status table and lazily query recorded operations.
The presence of a row means the identified dataset batch completed
successfully; failed attempts do not create rows.

## Usage

Run `common.py` before constructing the manager so `SchemaManager` is available.
Resolve the default `tbl_operation_status` table reference when the project
uses the packaged definition:

```python
from oeds.domain.utils.operation import OperationStatusManager

operation_status_manager = OperationStatusManager()
operation_status_manager.record_status(
    dataset="example_dataset",
    layer="standardization",
    batch_id="2026-08-16",
    job_run_id="12345",
    job_context={"source": "example"},
)
```

Pass another logical table ref when the project uses a different packaged
definition:

```python
operation_status_manager = OperationStatusManager(
    table_ref="tbl_custom_operation_status"
)
```

The constructor resolves `table_ref` through `SchemaManager` and requires it to
identify a table. Each construction returns an independent manager.

The manager normalizes supported layer values, converts job identifiers to
signed BIGINT-compatible integers, serializes `job_context` to compact JSON,
extracts the deployed table schema through `oeds.core.uc_utils`, adds the Spark
current timestamp, and appends exactly one Delta row. It does not deduplicate
or retry writes.

## Finding successful operations

Plain strings use exact equality. Wrap a Spark/Java-compatible regular
expression in `RegexFilter` to use case-insensitive `rlike` matching on any
text filter. All supplied filters are combined with logical AND.

```python
from datetime import date

from oeds.domain.utils.operation import RegexFilter, TimeFilter

latest_statuses = operation_status_manager.find_statuses(
    dataset="example_dataset",
    batch_id=RegexFilter(r"^2026-08-\d{2}$"),
    completed_at=TimeFilter(on=date(2026, 8, 16)),
)

all_statuses = operation_status_manager.find_statuses(
    latest_only=False,
    dataset="example_dataset",
)
```

`TimeFilter` accepts one of these forms:

- `on=date(...)` selects one complete calendar day.
- `start=date(...)` starts at the beginning of that day.
- `end=date(...)` includes the complete ending day.
- `start=datetime(...)` and `end=datetime(...)` use inclusive timestamp
  boundaries.
- Either range boundary may be supplied alone.

Dates and naive datetimes use the active Spark session timezone. A filter
cannot combine `on` with `start` or `end`, and closed ranges must use compatible
timezone awareness and have a non-reversed order.

`find_statuses` returns a lazy Spark DataFrame containing every table column.
By default, it returns at most one row: the newest match across all supplied
filters. Set `latest_only=False` to return every match ordered by
`completed_at` from newest to oldest. An unfiltered default call therefore
returns the newest successful operation in the table, while an unfiltered call
with `latest_only=False` returns the complete table. `job_context` is not
searchable through this API.

When matching rows share the newest `completed_at`, latest-only selection uses
descending `job_run_id` as a tie-breaker. If that value is also equal or null,
Spark may select either tied row. The `latest_only` value must be a boolean.

## Finding one successful operation

Use `find_latest_status` when client code needs one typed record instead of a
DataFrame:

```python
latest_batch_status = operation_status_manager.find_latest_status(
    dataset="example_dataset",
    layer="standardization",
    batch_id="2026-08-16",
)

latest_status_for_day = operation_status_manager.find_latest_status(
    dataset="example_dataset",
    completed_at=TimeFilter(on=date(2026, 8, 16)),
)
```

The method accepts the same field and time filters as `find_statuses`, always
uses latest-only ordering, and returns an `OperationStatusRecord` or `None`.
It is eager because it executes a Spark action to retrieve the first matching
row. The record contains every operation-status table field and preserves
`job_context` as its stored JSON string. An unfiltered call returns the newest
record across the table. Validation, table-read, regex, and Spark-action errors
propagate unchanged.

## Resolving dependencies

Pass one criteria mapping to `resolve_dependency` when a client needs to check
whether an upstream successful operation exists:

```python
criteria = {
    "dataset": "upstream_dataset",
    "layer": "standardization",
    "batch_id": rundate,
}
result = operation_status_manager.resolve_dependency(criteria)

if result is None:
    raise RuntimeError("The upstream dependency has no successful operation")
```

`criteria` requires non-null `dataset` and `layer` values and accepts the
`find_latest_status` filters. The mapping is copied and validated before the
lookup. `resolve_dependency` performs one eager lookup and returns an
`OperationStatusRecord`, or `None` when no successful operation matches.
