"""Schema definition for the operation_status table."""

from __future__ import annotations

from pyspark.sql.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
    IntegerType
)

SCHEMA = StructType(
    [
        StructField(
            "file_name",
            StringType(),
            False,
            metadata={"comment": "File name"},
        ),
        StructField(
            "process_error_msg",
            StringType(),
            True,
            metadata={"comment": "File processing error message"},
        ),
        StructField(
            "file_art_written_count",
            IntegerType(),
            True,
            metadata={"comment": "Number of artifacts written from file"},
        ),
        StructField(
            "batch_id",
            IntegerType(),
            False,
            metadata={"comment": "Batch ID"},
        ),
        StructField(
            "process_status_id",
            StringType(),
            False,
            metadata={"comment": "Process status ID"},
        ),
        StructField(
            "srce_sys_id",
            StringType(),
            False,
            metadata={"comment": "Source System ID"},
        ),
        StructField(
            "art_type_id",
            StringType(),
            False,
            metadata={"comment": "Artifact Type ID"},
        ),
        StructField(
            "audit_creation_user",
            StringType(),
            False,
            metadata={"comment": "Audit creation user"},
        ),
        StructField(
            "audit_creation_date",
            TimestampType(),
            False,
            metadata={"comment": "Audit creation date"},
        ),
        StructField(
            "audit_last_update_user",
            StringType(),
            False,
            metadata={"comment": "Audit last update user"},
        ),
        StructField(
            "audit_last_update_date",
            TimestampType(),
            False,
            metadata={"comment": "Audit last update date"},
        ),
        StructField(
            "audit_load_id",
            LongType(),
            True,
            metadata={"comment": "Databricks job run identifier"},
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
    "catalog": "banking_and_payments_cat",
    "database": "bsas_db",
    "name": "tbl_file_process",
    "kind": "table",
    "schema": SCHEMA,
    "sql": SQL,
}
