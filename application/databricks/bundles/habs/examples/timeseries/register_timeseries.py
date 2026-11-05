# Databricks notebook source
# MAGIC %md
# MAGIC ## Register time series example
# MAGIC This example registers the packaged time-series provider, dataset, and series definitions.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

# Standard libraries
import logging

# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug("Initialized job context with keys: %s", sorted(job_ctx))

# COMMAND ----------

from oeds.domain.utils.schema.schema_utils import SchemaManager
from oeds.domain.utils.timeseries.timeseries_utils import TimeSeriesUtils

# COMMAND ----------

# Initialize context for the time series manager
tsm_ctx = {
    "metadata_catalog": job_ctx.get("metadata_cat"),
    "pipeline_name": job_ctx.get("job_name"),
    "notebook_path": job_ctx.get("current_notebook_path"),
    "current_user": job_ctx.get("current_user"),
    "job_id": job_ctx.get("job_id"),
    "job_runid": job_ctx.get("job_run_id"),
    "job_trigger_type": job_ctx.get("job_trigger_type"),
}

# Create a caller-owned schema manager.
schema_manager = SchemaManager.get_instance()

# COMMAND ----------

# Initialize TimeSeriesUtils
timeseries_utils = TimeSeriesUtils(
    tsm_ctx=tsm_ctx,
)

full_table_name = schema_manager.find("tbl_ts").full_name
audit_log_skey = timeseries_utils.register_time_series(
    config_file="default.json",
    params={"destination_uc_table": full_table_name},
)
print({"audit_log_skey": audit_log_skey})

