# Databricks notebook source
# MAGIC %md
# MAGIC ## Datafile manager example
# MAGIC This example resolves one packaged Datafile registry entry on demand.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

import logging

from oeds.domain.utils.datafile import DatafileManager

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

datafile_manager = DatafileManager.get_instance()
print("datafile module map:", datafile_manager.get_module_map())
datafile_ref = "file_sample"
datafile_registry = datafile_manager.find(datafile_ref)

print("registry ref:", datafile_registry.ref)
print("registry path:", datafile_registry.path)
print("format:", datafile_registry.format)
print("options:", datafile_registry.options)
print("schema:", datafile_registry.schema)
