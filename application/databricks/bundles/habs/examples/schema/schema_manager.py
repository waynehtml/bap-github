# Databricks notebook source
# MAGIC %md
# MAGIC ## Schema manager examples
# MAGIC These examples resolve configured table and view references on demand.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

import logging

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context with keys: %s", sorted(job_ctx))

# COMMAND ----------

schema_manager = SchemaManager.get_instance()
print("schema module map:", schema_manager.get_module_map())

table_ref = "tbl_sample"
table_registry = schema_manager.find(table_ref)
print(f"{table_ref}: {table_registry.full_name}")

# COMMAND ----------

view_ref = "vw_sample"
view_registry = schema_manager.find(view_ref)
print(f"{view_ref}: {view_registry.full_name}")
