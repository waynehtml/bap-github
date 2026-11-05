# Databricks notebook source
# MAGIC %md
# MAGIC ## Curate
# MAGIC - Run project-specific curation logic.
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

import logging

from oeds.domain.utils.operation import OperationStatusManager

# COMMAND ----------

logger = logging.getLogger(__name__)
job_ctx = get_job_context()

# COMMAND ----------

# DBTITLE 1,Resolve curation parameters
# Parse the JSON argument object before resolving supported curation options.
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

# Mode specifies the data range to be curated.
# The default is "regular" which curates the current batch of data.
# The "full" mode curates all data in the dataset.
mode = args.get("mode", "regular")
if not isinstance(mode, str):
    raise TypeError("args.mode must be a string")
mode = mode.strip().lower()
supported_modes = ("full", "regular")
if mode not in supported_modes:
    supported_text = ", ".join(supported_modes)
    raise ValueError(f"args.mode must be one of: {supported_text}")
logger.info(f"mode is {mode}")

# Reuse the normalized rundate published by main
rundate = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="rundate",
    debugValue=job_ctx["rundate"],
)
logger.info(f"rundate is {rundate}")

# COMMAND ----------

# DBTITLE 1,Record successful curation
try:
    OperationStatusManager().record_status(
        dataset=job_ctx["dataset"],
        layer="curation",
        batch_id=rundate,
        job_run_id=job_ctx.get("job_run_id"),
        job_name=job_ctx.get("job_name"),
        job_id=job_ctx.get("job_id"),
        job_trigger_type=job_ctx.get("job_trigger_type"),
        job_context=job_ctx,
    )
except Exception:
    logger.exception(
        "Curation completed for dataset '%s' and rundate '%s', but failed "
        "to record the successful operation",
        job_ctx["dataset"],
        rundate,
    )
    raise
