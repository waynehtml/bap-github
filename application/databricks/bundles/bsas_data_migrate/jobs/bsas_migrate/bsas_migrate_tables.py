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

# Set source catelog and detination catelog and schema
# The source schema and table are in the config file
env=job_ctx["env"]
source_catalog = job_ctx["bsas_catalog"]
source_schema  = "dbo"
target_catalog = job_ctx["catalog"]
target_schema  = "bsas_db"

job_run_id=job_ctx["job_run_id"]
config_root = job_ctx["config_root"]

AUDIT_COLS = {"audit_load_id", "audit_create_ts", "audit_last_update_ts"}

tables_df = spark.sql(f"SHOW TABLES IN {target_catalog}.{target_schema}")
table_names = [row.tableName for row in tables_df.collect() if not row.isTemporary]

for target_table in table_names:
    source_table = target_table[4:]
    target_full = f"`{target_catalog}`.`{target_schema}`.`{target_table}`"
    source_full = f"`{source_catalog}`.`{source_schema}`.`{source_table}`"

    # Check the SOURCE exists (target is known to exist from SHOW TABLES)
    if not source_table or not spark.catalog.tableExists(f"{source_catalog}.{source_schema}.{source_table}"):
        print(f"Source {source_full} does not exist - skipping {target_full}")
        continue

    # Source columns, excluding audit columns to avoid duplicates
    source_cols = [c for c in spark.table(source_full).columns if c.lower() not in AUDIT_COLS]
    insert_cols = ", ".join(f"`{c}`" for c in source_cols)

    # Build per table (replace with your mapping logic if needed)
    select_expr = ", ".join(f"src.`{c}`" for c in source_cols)
    mapping_joins = ""   # per-table joins, if any

    sql = f"""
        INSERT OVERWRITE {target_full}
        (
            {insert_cols},
            audit_load_id
        )
        SELECT
            {select_expr},
            '{job_run_id}' AS audit_load_id
        FROM {source_full} AS src
        {mapping_joins}
    """

    try:
        print(f"Loading table {target_full} from {source_full}")
        logger.debug(sql)
        spark.sql(sql)
    except Exception as e:
        print(f"Error: {e} Table: {target_full}")
        raise