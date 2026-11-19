"""File load mapping for the sample source file."""

from __future__ import annotations

from typing import Any

from oeds.core.df_validator import Rules
from pyspark.sql import DataFrame, functions as F


def transform_sample(
    df: DataFrame,
    context: dict[str, Any] | None,
) -> DataFrame:
    """Return the sample source in the registered table shape.

    Args:
        df: Source DataFrame after configured normalization.
        context: Caller context enriched with ``_runtime`` execution values.

    Returns:
        Target-shaped DataFrame excluding the generated identity column.

    Raises:
        ValueError: If the batch or Databricks load identifier is unavailable.
    """
    resolved_context = context or {}
    runtime_context = resolved_context.get("_runtime", {})

    # A replace-mode batch ID must also populate the target batch column. Other
    # modes use the run date as the stable logical batch identifier.
    raw_batch_id = runtime_context.get("batch_id")
    if raw_batch_id is None:
        raw_batch_id = resolved_context.get("rundate")

    audit_batch_id = str(raw_batch_id).strip() if raw_batch_id is not None else ""
    audit_load_id = str(resolved_context.get("job_run_id") or "").strip()
    if not audit_batch_id:
        raise ValueError("context must provide rundate or _runtime.batch_id")
    if not audit_load_id:
        raise ValueError("context.job_run_id is required")

    # Select the complete writable target shape; the table generates its identity key.
    loaded_at = F.current_timestamp()
    return df.select(
        F.col("number").cast("int").alias("number"),
        F.col("category").cast("string").alias("category"),
        F.upper(F.col("country")).cast("string").alias("country"),
        F.col("amount").cast("int").alias("amount"),
        F.col("minimum_amount").cast("int").alias("minimum_amount"),
        F.lit(audit_batch_id).cast("string").alias("audit_batch_id"),
        F.lit(audit_load_id).cast("string").alias("audit_load_id"),
        loaded_at.alias("audit_created_ts"),
        loaded_at.alias("audit_last_update_ts"),
        F.lit(None).cast("string").alias("audit_source_file_path"),
    )


DEFINITION = {
    "file_ref": "file_sample",
    "tbl_ref": "tbl_sample",
    "normalize": {
        "column_names": True,
        "null_values": ["", "N/A", "NA", "NULL", "None"],
    },
    "transform": transform_sample,
    "rules": [
        Rules.not_null("number", name="number_required"),
    ],
    "write": {
        "mode": "overwrite",
        "batch_column": "audit_batch_id",
    },
}
