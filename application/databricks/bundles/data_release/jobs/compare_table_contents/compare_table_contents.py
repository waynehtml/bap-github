# Databricks notebook source
# MAGIC %run ../../common

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# Standard libraries
import logging

# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug(f"job_ctx: {job_ctx}")

# COMMAND ----------

import json


# 1. Fetch all parameters from the Databricks widgets
source_cat    = dbutils.widgets.get("source_catalog")
source_schema = dbutils.widgets.get("source_schema")
target_cat    = dbutils.widgets.get("target_catalog")
target_schema = dbutils.widgets.get("target_schema")

tables = json.loads(dbutils.widgets.get("tables_list"))

for source_table_name in tables:
    # Apply mapping rule: Prepend "tbl_" to get target table name
    target_table_name = f"tbl_{source_table_name}"

    # Build explicit 3-level fully qualified paths (catalog.schema.table)
    path_a = f"{source_cat}.{source_schema}.{source_table_name}"
    path_b = f"{target_cat}.{target_schema}.{target_table_name}" 

    print(f"\n=======================================================")
    print(f"Comparing Source Table: {path_a}")
    print(f"     to Target Table: {path_b}")
    print(f"=======================================================")

    # 2. Check if both tables actually exist in Unity Catalog
    if not spark.catalog.tableExists(path_a):
        print(f"❌ ERROR: Source table {path_a} does not exist. Skipping.")
        continue
    if not spark.catalog.tableExists(path_b):
        print(f"❌ ERROR: Target table {path_b} does not exist. Skipping.")
        continue

    # Load original DataFrames
    df_raw_a = spark.read.table(path_a)
    df_raw_b = spark.read.table(path_b)

    # 3. Filter out audit columns using a list comprehension
    cols_to_compare_a = [c for c in df_raw_a.columns if not (c.lower().startswith("md_") or c.lower().startswith("audit_"))]
    cols_to_compare_b = [c for c in df_raw_b.columns if not (c.lower().startswith("md_") or c.lower().startswith("audit_"))]

    # 4. Validate column names and sequence first
    if cols_to_compare_a != cols_to_compare_b:
        print(f"❌ SCHEMA SEQUENCE MISMATCH (Non-Audit Columns):")
        print(f"   Table A columns to compare: {cols_to_compare_a}")
        print(f"   Table B columns to compare: {cols_to_compare_b}")
        continue  # Stop and move to next table because subtract operation will fail
    else:
        print("✅ Column sequence and names match perfectly (Audit columns excluded).")

    # 5. Select only the non-audit columns for structural alignment
    df_a = df_raw_a.select(*cols_to_compare_a)
    df_b = df_raw_b.select(*cols_to_compare_b)

    # 6. Row Counts Check
    count_a = df_a.count()
    count_b = df_b.count()

    if count_a != count_b:
        print(f"❌ ROW COUNT MISMATCH: Source has {count_a} rows, but Target has {count_b} rows.")
    else:
        print(f"✅ Row counts match ({count_a} rows).")

    # 7. Data Discrepancy Check (Subtract)
    diff_a_minus_b = df_a.subtract(df_b)
    diff_b_minus_a = df_b.subtract(df_a)

    mismatches_in_target = diff_a_minus_b.count()
    extra_in_target = diff_b_minus_a.count()

    if mismatches_in_target == 0 and extra_in_target == 0:
        print("✅ DATA MATCH: Non-audit business data is 100% identical between both tables.")
    else:
        print(f"❌ DATA MISMATCH FOUND:")
        if mismatches_in_target > 0:
            print(f"   - {mismatches_in_target} rows found in Source but missing/different in Target.")
            diff_a_minus_b.show(5, truncate=False)
        if extra_in_target > 0:
            print(f"   - {extra_in_target} unexpected/extra rows found in Target.")
            diff_b_minus_a.show(5, truncate=False)

