"""File registry definition for the sample source file."""

from __future__ import annotations

from pyspark.sql.types import IntegerType, StringType, StructField, StructType

SCHEMA = StructType(
    [
        StructField("number", IntegerType(), True),
        StructField("category", StringType(), True),
        StructField("country", StringType(), True),
        StructField("amount", IntegerType(), True),
        StructField("minimum_amount", IntegerType(), True),
    ]
)

DEFINITION = {
    "path": "tbl_sample.csv",
    "format": "csv",
    "options": {
        "encoding": "windows-1252",
        "header": "true",
    },
    "schema": SCHEMA,
}
