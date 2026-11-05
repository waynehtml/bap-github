# Unity Catalog and Delta Lake

## When to use this capability

Use `uc_utils` for Unity Catalog metadata inspection, bounded SQL result extraction, and controlled Delta Lake writes or row mutations from a Spark workload.

## Choose the public API

| Need | Choose |
| --- | --- |
| Resolve a logical catalog or inspect table metadata | `resolve_catalog`, `table_exists`, `extract_table_schema`, `get_identity_column`, or `get_partition_columns` |
| Find table names by glob | `find_matching_tables` |
| Execute SQL without retrying | `delta_execute_sql` |
| Fetch one scalar, one row, or one result column | `delta_fetch_scalar`, `delta_fetch_first_row`, or `delta_fetch_column` |
| Append or replace a batch/table | `delta_batch_update` |
| Upsert a DataFrame | `delta_merge` |
| Insert, update, or delete mapping-based rows | `delta_insert`, `delta_update`, or `delta_delete` |
| Retry a known transient Spark/Delta call | `safe_write_to_delta` or `safe_run_sql`, only after assessing idempotency |

Prefer the `delta_*` query and batch helpers for new code. `get_single_val_sql`, `get_col_val_sql`, `get_first_row_sql`, and `batch_update` are legacy compatibility helpers with looser validation.

## Restrictions and side effects

These APIs expect Spark and, for Delta operations, Delta Lake. `find_matching_tables` changes the active Spark catalog/schema with `USE` and does not restore it. `get_partition_columns` suppresses metadata-strategy errors, so an empty list can mean no partitioning or inaccessible metadata. Result-column helpers bring values to the driver; keep queries bounded.

!!! danger "Destructive catalog and Delta operations"

    `delete_table`, `create_table(..., replace=True)`, legacy `batch_update`, `delta_batch_update` in replace/overwrite modes, `delta_merge`, `delta_insert`, `delta_delete`, and `delta_update` mutate persistent data. A replace with an empty DataFrame can delete the selected batch. These helpers add no confirmation or rollback.

Identifiers and predicates accepted as strings may be interpolated into Spark SQL. Use trusted identifiers and predicates only. `safe_run_sql` can retry a mutating statement, and `safe_write_to_delta` can repeat a write; neither adds idempotency. `delta_merge` requires the caller to prevent multiple source rows from matching one target row.

## Short example

```python
from oeds.core.uc_utils import delta_fetch_scalar, table_exists

orders_table = "example_catalog.example_schema.orders"
if not table_exists(orders_table):
    raise RuntimeError("Required table is missing")

row_count = delta_fetch_scalar(
    f"SELECT COUNT(*) AS row_count FROM {orders_table}",
    column="row_count",
)
print(row_count)
```

## Related examples

- [Read-only example in this guide](#short-example)
