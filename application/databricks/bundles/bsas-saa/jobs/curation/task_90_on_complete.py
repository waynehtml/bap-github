# Databricks notebook source
# MAGIC %md
# MAGIC ## Curation Completion Handler
# MAGIC - Run final success-path actions.
# MAGIC - Add completion notifications, cleanup, or audit updates here.

# COMMAND ----------

# DBTITLE 1,Show widgets for development
dbutils.widgets.text("debug", "True")
dbutils.widgets.text("rundate", "")
dbutils.widgets.text("args", "")

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../../common

# COMMAND ----------

import logging

# COMMAND ----------

logger = logging.getLogger(__name__)
job_ctx = get_job_context()
logger.info(
    "Curation workflow completed for dataset %s and rundate %s",
    job_ctx.get("dataset"),
    job_ctx.get("rundate"),
)
