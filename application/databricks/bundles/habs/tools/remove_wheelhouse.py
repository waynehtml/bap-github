# Databricks notebook source
# MAGIC %md
# MAGIC ## This notebook will remove the wheelhouse for Nexus caching. 
# MAGIC Run the job with following parameters 
# MAGIC - task: tools/remove_wheelhouse
# MAGIC - mode: sys

# COMMAND ----------

# MAGIC %run ../common

# COMMAND ----------

# Standard libraries
import logging
# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

import os

cluster_wheelhouse_path = os.environ.get("CLUSTER_WHEELHOUSE_PATH")
logger.info(f"cluster_wheelhouse_path is {cluster_wheelhouse_path}")

if not cluster_wheelhouse_path:
    raise Exception("CLUSTER_WHEELHOUSE_PATH is not defined ")

try:
    print(f"Removing wheelhouse folder: {cluster_wheelhouse_path}")
    dbutils.fs.rm(cluster_wheelhouse_path, True)
    print("Done.")
except Exception:
    print(f"Wheelhouse folder may not exist or is already removed: {cluster_wheelhouse_path}")
