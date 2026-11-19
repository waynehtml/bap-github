# Databricks notebook source

# COMMAND ----------

# Standard libraries
import logging

# Get logger
logger = logging.getLogger(__name__)

# COMMAND ----------
catalog_name = dbutils.widgets.get("catalog")
dbutils.widgets.text("schema_to_be_clean", "")
schema_name = dbutils.widgets.get("schema_to_be_clean")

# COMMAND ----------

# 1. Define your target schema
full_schema_path = f"{catalog_name}.{schema_name}"

spark.sql(f"USE CATALOG {catalog_name}")

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
