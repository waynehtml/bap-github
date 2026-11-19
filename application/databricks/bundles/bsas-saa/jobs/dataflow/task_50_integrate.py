# Databricks notebook source
# MAGIC %md
# MAGIC ## Integration Task
# MAGIC - Run project-specific integration logic.
# MAGIC - Replace the reference placeholder with the intended implementation.

# COMMAND ----------

# DBTITLE 1,Show widgets for development
dbutils.widgets.text("debug", "True")
dbutils.widgets.text("rundate", "")
dbutils.widgets.text("args", "")

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../../common

# COMMAND ----------

import json
import logging

# COMMAND ----------

logger = logging.getLogger(__name__)
job_ctx = get_job_context()

rundate = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="rundate",
    debugValue=job_ctx["rundate"],
)
logger.info("No project integration logic is configured for rundate %s", rundate)

result = {
    "dataset": job_ctx.get("dataset"),
    "rundate": rundate,
    "status": "not_configured",
}
dbutils.notebook.exit(json.dumps(result, separators=(",", ":"), sort_keys=True))
