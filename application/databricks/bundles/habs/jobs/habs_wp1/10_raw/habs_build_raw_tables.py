# Databricks notebook source
# MAGIC %md
# MAGIC ## Configuration file
# MAGIC - habs_wp1_raw_tables_list.json
# MAGIC   - JSON file containing the list of raw source tables (`schema.table` format)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Processing Logic
# MAGIC
# MAGIC ### 1. Initialize Variables
# MAGIC - `target_catalog = job_ctx["catalog"]`  
# MAGIC - `target_schema  = "raw_db"`  
# MAGIC - `source_catalog = job_ctx["habs_catalog"]`  
# MAGIC
# MAGIC - The list of source tables (schema and table pairs) is defined in the JSON configuration file: **raw_table_list_file**.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 2. Data Pipeline Execution *(Copy Raw Tables — ingestion method: replace)*
# MAGIC - Iterate through each source table defined in the configuration file  
# MAGIC
# MAGIC - For each table:
# MAGIC   1. Parse **source schema** and **source table name** from `schema.table`  
# MAGIC   2. Determine **target table name** using the convention:  
# MAGIC      `<source_schema>_<source_table>`  
# MAGIC   3. **Create or replace** the target table from the source table
# MAGIC
# MAGIC - Notes:  
# MAGIC   - This approach ensures that target tables always contain the **latest data** from the source  
# MAGIC   - Safe for mission-critical OLTP systems when reading from **standby databases**  
# MAGIC   - Each table is processed independently, reducing risk of partial failures

# COMMAND ----------

# MAGIC %run ../../../common

# COMMAND ----------

# Standard libraries
if dbutils.widgets.get("build_raw") != "1":
    logger.info("Skipping RAW build.")
    dbutils.notebook.exit("SKIPPED")

import logging
job_ctx = get_job_context()
logger = logging.getLogger(__name__)
logger.debug(f"job_ctx: {job_ctx}")

# COMMAND ----------

env = job_ctx["env"]
target_catalog = job_ctx["catalog"]
target_schema  = "raw_db"
source_catalog = job_ctx["habs_catalog"]
config_root = job_ctx["config_root"]

config_habs_wp1_raw_tables_list = f"dbfs:{config_root}/habs/habs_wp1_raw_tables_list.json"
logger.debug(f"config_habs_wp1_raw_tables_list: {config_habs_wp1_raw_tables_list}")


# COMMAND ----------

import json

def read_json_from_volume(path):
    content = dbutils.fs.head(path)
    return json.loads(content)

tables = read_json_from_volume(config_habs_wp1_raw_tables_list)  

for t in tables:
    source_schema, source_table = t.split(".") 
    target_table = f"{source_schema}_{source_table}"
    
    # Drop table if it exists and then create the target table
    drop_sql = f"""
    DROP TABLE IF EXISTS {target_catalog}.{target_schema}.{target_table}
    """
    logger.debug(drop_sql)
    spark.sql(drop_sql)

    create_sql = f"""
    CREATE TABLE {target_catalog}.{target_schema}.{target_table}
    AS SELECT * FROM {source_catalog}.{source_schema}.{source_table}
    """
    logger.debug(create_sql)
    spark.sql(create_sql)
    