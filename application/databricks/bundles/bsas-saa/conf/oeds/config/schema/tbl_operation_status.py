"""Schema definition for the operation_status table."""

from __future__ import annotations

from pyspark.sql.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

SCHEMA = StructType(
    [
        StructField(
            "dataset",
            StringType(),
            False,
            metadata={"comment": "Unique logical dataset name"},
        ),
        StructField(
            "layer",
            StringType(),
            False,
            metadata={
                "comment": "STANDARDIZATION, CURATION, or INTEGRATION"
            },
        ),
        StructField(
            "batch_id",
            StringType(),
            False,
            metadata={"comment": "Dataset-specific data batch identifier"},
        ),
        StructField(
            "job_name",
            StringType(),
            True,
            metadata={"comment": "Databricks job name"},
        ),
        StructField(
            "job_id",
            LongType(),
            True,
            metadata={"comment": "Databricks job ID"},
        ),
        StructField(
            "job_run_id",
            LongType(),
            True,
            metadata={"comment": "Databricks job run ID"},
        ),
        StructField(
            "job_trigger_type",
            StringType(),
            True,
            metadata={"comment": "Databricks job.trigger.type value"},
        ),
        StructField(
            "job_context",
            StringType(),
            True,
            metadata={"comment": "Additional context stored as a JSON string"},
        ),
        StructField(
            "completed_at",
            TimestampType(),
            False,
            metadata={
                "comment": "Completion timestamp assigned by record_status"
            },
        ),
    ]
)

SQL = """
(
{schema}
)
USING DELTA
COMMENT 'Successful standardization, curation, and integration operations'
"""

DEFINITION = {
    "catalog": "application_cat",
    "database": "reference_db",
    "name": "operation_status",
    "kind": "table",
    "schema": SCHEMA,
    "sql": SQL,
}
