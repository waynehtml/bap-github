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

dbutils.widgets.text("schema_to_be_clean", "")
schema = dbutils.widgets.get("schema_to_be_clean")

# COMMAND ----------

# 1. Define your target schema
env=job_ctx["env"]
catalog = job_ctx["catalog"]
full_schema_path = f"{catalog}.{schema}"

spark.sql(f"USE CATALOG {catalog}")

# 2. Drop all Views
views = spark.sql(f"SHOW VIEWS IN {full_schema_path}")
for row in views.collect():
    view_name = row['viewName']
    spark.sql(f"DROP VIEW IF EXISTS {full_schema_path}.{view_name}")
    print(f"Dropped view: {view_name}")

# 3. Drop all Tables
tables = spark.sql(f"SHOW TABLES IN {full_schema_path}")
for row in tables.collect():
    table_name = row['tableName']
    # Skip temporary tables if any exist
    if not row['isTemporary']:
        spark.sql(f"DROP TABLE IF EXISTS {full_schema_path}.{table_name}")
        print(f"Dropped table: {table_name}")
