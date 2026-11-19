# Databricks notebook source
# MAGIC %md
# MAGIC ## Integrate
# MAGIC This reference integration reads one standardized batch, disseminates a
# MAGIC sample time series, and delivers a business CSV through DataBridge.

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
import posixpath

from pyspark.sql import functions as F

from oeds.core.file_utils import write_csv_file
from oeds.domain.utils.ingest.ingest_utils import (
    DisConnectionOptions,
    FileVerificationOptions,
    run_ingest,
)
from oeds.domain.utils.timeseries import TimeSeriesUtils

# COMMAND ----------

logger = logging.getLogger(__name__)
job_ctx = get_job_context()

rundate_str = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="rundate",
    debugValue=job_ctx["rundate"],
)
run_date = parse_date(rundate_str, job_ctx["python_date_format"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Extract curated data
# MAGIC - Load the curated table based on run_date


# COMMAND ----------

curated_table = SchemaManager.get_instance().find("tbl_sample")
curated_df = (
    spark.table(curated_table.full_name)
    .where(F.col("audit_batch_id") == run_date.isoformat())
)
record_count = curated_df.count()
if record_count == 0:
    raise ValueError(
        f"No curated records found in '{curated_table.full_name}' "
        f"for rundate '{run_date.isoformat()}'"
    )

logger.info(
    "Loaded %s curated record(s) from '%s' for rundate '%s'",
    record_count,
    curated_table.full_name,
    run_date,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Disseminate time series
# MAGIC - Compose the observation from the curated data
# MAGIC - Insert the observation into the time series table
# COMMAND ----------

default_date = run_date

# Compose the observation from the curated data
observation_row = curated_df.orderBy("number").select("amount").first()
if observation_row is None or observation_row["amount"] is None:
    raise ValueError(f"Amount is unavailable for rundate '{run_date}'")

observations = [
    {
        "time_series_name": "template.ts1#boc",
        "value": float(observation_row["amount"]),
    }
]

# Initialize the time series utility
timeseries_context = {
    "metadata_catalog": job_ctx.get("metadata_catalog"),
    "pipeline_name": job_ctx.get("job_name"),
    "notebook_path": job_ctx.get("current_notebook_path"),
    "current_user": job_ctx.get("current_user"),
    "job_id": job_ctx.get("job_id"),
    "job_runid": job_ctx.get("job_run_id"),
    "job_trigger_type": job_ctx.get("job_trigger_type"),
}
timeseries_utils = TimeSeriesUtils(tsm_ctx=timeseries_context)

# Get the full table name for the time series table
timeseries_table = SchemaManager.get_instance().find("tbl_ts")

# Insert the observation into the time series table
metadata_audit_skey = timeseries_utils.write_observations(
    observations=observations,
    full_table_name=timeseries_table.full_name,
    default_date=default_date,
)

logger.info(
    "Registered time-series audit batch '%s' for automatic WebMart "
    "publishing for rundate '%s'",
    metadata_audit_skey,
    run_date,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Deliver outbound CSV through DataBridge
# MAGIC - Select only the business-facing columns required by the file consumer.
# MAGIC - Write one predictable CSV filename in the outbound directory. 
# MAGIC - Let DataBridge read the staged file and deliver to the external destination

# COMMAND ----------

# Conclude file_date from run_date
file_date = run_date

# Prepare the outbound DataFrame with only the business-facing columns
outbound_df = curated_df.select(
    "number",
    "category",
    "country",
    "amount",
    "minimum_amount",
)

# Determine the outbound file path/name and write one CSV file
outbound_root = str(job_ctx.get("outbound_root") or "").strip().rstrip("/")
if not outbound_root:
    raise ValueError("outbound_root is required")

outbound_file_name = f"{file_date.isoformat()}.csv"
outbound_file_path = posixpath.join(
    outbound_root,
    file_date.isoformat(),
    outbound_file_name,
)

# Write one CSV file for DataBridge to read and deliver to the external destination.
write_csv_file(
    dataframe=outbound_df,
    destination_path=outbound_file_path,
    include_header=True,
)

service_spn_id = dbutils.secrets.get(
    scope=job_ctx["secrete_scope"],
    key=job_ctx["service_spn_id_key"],
)
service_spn_secret = dbutils.secrets.get(
    scope=job_ctx["secrete_scope"],
    key=job_ctx["service_spn_secrete_key"],
)

# The runner loads the packaged template, resolves client parameters, and deliver
outbound_delivery_result = run_ingest(
    connection=DisConnectionOptions(
        host=job_ctx.get("internal_databricks_workspace_url"),
        azure_tenant_id=job_ctx.get("azure_tenant_id"),
        azure_client_id=service_spn_id,
        azure_client_secret=service_spn_secret,
        azure_workspace_resource_id=job_ctx.get("internal_databricks_resource_id"),
        dis_job_id=int(job_ctx.get("internal_dis_job_id")),
    ),
    config_file="outbound.json",
    template_params={
        "outbound_root": outbound_root,
        "file_date": file_date.isoformat(),
        "file_name": outbound_file_name,
    },
)

# log the ingest and verification results for auditing and troubleshooting
ingest_result = outbound_delivery_result.ingest_result
verify_result = outbound_delivery_result.verify_result
logger.info(
    "Delivered outbound CSV '%s' through DataBridge: status=%s job_run_id=%s "
    "task_run_id=%s verification_status=%s matched_files=%s",
    outbound_file_path,
    ingest_result.get_status(),
    ingest_result.get_job_run_id(),
    ingest_result.get_task_run_id(),
    verify_result.status if verify_result else None,
    len(verify_result.matched) if verify_result else 0,
)
