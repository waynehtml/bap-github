# Databricks notebook source
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
from oeds.domain.utils.timeseries import TimeSeriesUtils

# COMMAND ----------

# Initialize context for TimeSeries manager
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

# Insert time series
full_table_name = schema_manager.find("tbl_ts").full_name
observations = [
    {
        "time_series_name": "template.ts1#boc",
        "value": 4.25,
    }
]
metadata_audit_skey = timeseries_utils.write_observations(
    observations=observations,
    full_table_name=full_table_name,
)
logger.info(
    "Registered time-series audit batch '%s' for automatic WebMart publishing",
    metadata_audit_skey,
)
