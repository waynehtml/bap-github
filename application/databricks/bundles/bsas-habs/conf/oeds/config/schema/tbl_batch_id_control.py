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
            "next_batch_id",
            IntegerType(),
            False,
            metadata={"comment": "Next batch ID"},
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
            metadata={"comment": "Audit last update date/time"},
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
"""

DEFINITION = {
    "catalog": "banking_and_payments_cat",
    "database": "bsas_db",
    "name": "tbl_batch_id_control",
    "kind": "table",
    "schema": SCHEMA,
    "sql": SQL,
}