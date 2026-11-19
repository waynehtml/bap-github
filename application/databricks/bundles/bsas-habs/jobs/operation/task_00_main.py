# Databricks notebook source
# MAGIC %md
# MAGIC ## Operation Main Task
# MAGIC - Initialize the shared job context.
# MAGIC - Validate operation arguments.
# MAGIC - Replace the placeholder result with project operation logic.

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

args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

logger.info("No project operation logic is configured")
result = {
    "dataset": job_ctx.get("dataset"),
    "job_name": job_ctx.get("job_name"),
    "message": "No project operation logic is configured",
    "status": "not_configured",
}
dbutils.notebook.exit(json.dumps(result, separators=(",", ":"), sort_keys=True))
