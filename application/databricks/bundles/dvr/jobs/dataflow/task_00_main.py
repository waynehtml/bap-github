# Databricks notebook source
# MAGIC %md
# MAGIC ## Main Task
# MAGIC - Initialize shared business parameters from job context.
# MAGIC - Publish task values used by downstream workflow stages.

# COMMAND ----------

# DBTITLE 1,Show widget for development purpose
# Development-only widgets.
dbutils.widgets.text("debug", "True")
dbutils.widgets.text("rundate", "")
dbutils.widgets.text("args", "")

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../../common

# COMMAND ----------

# DBTITLE 1,Import libraries
# Standard-library imports
import logging
from pathlib import Path

from oeds.domain.utils.calendar import CalendarManager

# COMMAND ----------

# DBTITLE 1,Init logging and context
logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

calendar = CalendarManager.get_instance()

# The rundate parameter supports historical workflow runs and defaults to today.
rundate = parse_date(job_ctx["rundate"], job_ctx["python_date_format"])
logger.info(f"rundate: {rundate}")
# Publish the normalized rundate for curated processing and status records.
dbutils.jobs.taskValues.set(key="rundate", value=rundate.isoformat())

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exit workflow on holidays
# MAGIC - Complete the workflow gracefully on holidays
# MAGIC - Remove the following code if holiday check is not required.

# COMMAND ----------

if calendar.is_holiday(rundate):
    logger.info(
        "rundate %s is a holiday. Completing workflow without downstream processing.",
        rundate,
    )
    dbutils.jobs.taskValues.set(key="flow_action", value="complete")
    dbutils.notebook.exit(f"Workflow completed because rundate {rundate} is a holiday.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Prepare shared task values
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC **Prepare file_date**
# MAGIC - `file_date` identifies the processing batch in paths and file names.
# MAGIC - Adjust its derivation to match project-specific business rules.

# COMMAND ----------

# Use the previous business day as the source-system file date.
file_date = calendar.business_day_prev(rundate).isoformat()
logger.info(f"file_date: {file_date}")
# Publish the processing date so every downstream stage uses the same raw batch.
dbutils.jobs.taskValues.set(key="file_date", value=file_date)

# COMMAND ----------

# DBTITLE 1,Landing directory
# land_dir is the landing directory for the current batch.
land_dir = str(Path(job_ctx.get("land_root")) / file_date)
logger.info(f"land_dir: {land_dir}")
dbutils.jobs.taskValues.set(key="land_dir", value=land_dir)

# COMMAND ----------

# DBTITLE 1,Raw directory
# raw_dir is the raw-zone directory for the current batch.
raw_dir = str(Path(job_ctx.get("raw_root")) / file_date)
logger.info(f"raw_dir: {raw_dir}")
dbutils.jobs.taskValues.set(key="raw_dir", value=raw_dir)
