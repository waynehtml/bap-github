# Databricks notebook source
# MAGIC %md
# MAGIC ## List Unity Catalog catalogs
# MAGIC This example uses the current notebook or job identity.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

import logging

from databricks_tools_core.unity_catalog.catalogs import list_catalogs

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

catalogs = list_catalogs()

logger.info("Found %s catalogs", len(catalogs))

catalog_rows = [
    {
        "name": catalog.name,
        "owner": catalog.owner,
        "comment": catalog.comment,
        "storage_root": catalog.storage_root,
    }
    for catalog in catalogs
]

# COMMAND ----------

for catalog in catalogs:
    print(catalog.name)
