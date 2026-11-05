# Databricks notebook source

# COMMAND ----------

import json
from datetime import datetime

# 1. Get the current date formatted as YYYYMMDD (e.g., 20261023)
current_date_str = datetime.now().strftime("%Y%m%d")

catalog_name = dbutils.widgets.get("catalog")
tables = json.loads(dbutils.widgets.get("tables_list"))

for t in tables:
    source_schema, source_table_name = t.split(".")

    # Build the full paths accurately using your variable names
    full_source_path = f"{catalog_name}.{source_schema}.{source_table_name}"

    # Check if the source table exists
    if spark.catalog.tableExists(full_source_path):

        # Create backup table using deep clone or CTAS
        sql = f"DROP TABLE {full_source_path}"
        spark.sql(sql)
        print(f"Drop table {full_source_path} ")

    else:
        print(f"Table {full_source_path} does not exist. Skipping drop.")
