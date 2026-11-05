# Databricks notebook source
# MAGIC %md
# MAGIC ## Curation Main Task
# MAGIC - Initialize and validate the shared run context.
# MAGIC - Publish values used by later curation tasks.

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

rundate = parse_date(job_ctx["rundate"], job_ctx["python_date_format"])
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

normalized_rundate = rundate.isoformat()
logger.info("Initialized curation workflow for rundate %s", normalized_rundate)
dbutils.jobs.taskValues.set(key="rundate", value=normalized_rundate)
