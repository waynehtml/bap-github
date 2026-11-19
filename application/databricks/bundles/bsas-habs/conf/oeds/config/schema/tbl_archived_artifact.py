"""Schema definition for the tbl_archived_artifact table."""

from __future__ import annotations

from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
    DateType,
    BinaryType
)

SCHEMA = StructType(
    [
        StructField(
            "srce_sys_id",
            StringType(),
            True,
            metadata={"comment": "Source System ID"},
        ),
        StructField(
            "art_type_id",
            StringType(),
            False,
            metadata={"comment": "Art Type ID"},
        ),
        StructField(
            "batch_id_process_file",
            IntegerType(),
            False,
            metadata={"comment": "Batch file process ID"},
        ),
        StructField(
            "keyw1_srce_tran_id",
            StringType(),
            False,
            metadata={"comment": "Key source transaction ID"},
        ),
        StructField(
            "keyw2_srce_tran_effect_date",
            TimestampType(),
            True,
            metadata={"comment": "Source transaction effect date"},
        ),
        StructField(
            "keyw3_srce_prime_party_id",
            IntegerType(),
            True,
            metadata={"comment": "Source prime party ID"},
        ),
        StructField(
            "keyw4_boc_doc_title",
            StringType(),
            True,
            metadata={"comment": "BOC document title"},
        ),
        StructField(
            "keyw5_boc_doc_creator",
            StringType(),
            True,
            metadata={"comment": "BOC document creator"},
        ),
        StructField(
            "keyw6_srce_account_id",
            StringType(),
            True,
            metadata={"comment": "Source account ID"},
        ),
        StructField(
            "keyw7_value",
            StringType(),
            True,
            metadata={"comment": "Key W7 value"},
        ),
        StructField(
            "keyw8_value",
            StringType(),
            True,
            metadata={"comment": "Key W8 value"},
        ),
        StructField(
            "keyw9_value",
            StringType(),
            True,
            metadata={"comment": "Key W9 value"},
        ),
        StructField(
            "keyw10_value",
            StringType(),
            True,
            metadata={"comment": "Key W10 value"},
        ),
        StructField(
            "art_archive_bytes",
            BinaryType(),
            True,
            metadata={"comment": "Art archive"},
        ),
        StructField(
            "srce_sys_creation_date",
            TimestampType(),
            True,
            metadata={"comment": "Source system creation date"},
        ),
        StructField(
            "purge_forward_date",
            TimestampType(),
            True,
            metadata={"comment": "Purge forward date"},
        ),
        StructField(
            "purge_hold_flag",
            StringType(),
            True,
            metadata={"comment": "Purge hold flag"},
        ),
        StructField(
            "audit_creation_user",
            StringType(),
            True,
            metadata={"comment": "Audit creation user name"},
        ),
        StructField(
            "audit_creation_date",
            TimestampType(),
            True,
            metadata={"comment": "Audit creation date"},
        ),
        StructField(
            "audit_last_update_user",
            StringType(),
            True,
            metadata={"comment": "Audit last update user"},
        ),
        StructField(
            "audit_last_update_date",
            TimestampType(),
            True,
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
    "name": "tbl_archived_artifact",
    "kind": "table",
    "schema": SCHEMA,
    "sql": SQL,
}