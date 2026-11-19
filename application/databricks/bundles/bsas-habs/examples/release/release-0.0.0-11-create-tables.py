# Databricks notebook source
# MAGIC %md
# MAGIC ### Run this notebook in the job with following parameters:
# MAGIC - task: releases/release-001-11-create-tables
# MAGIC - args: {"ref":"tbl_sample","replace":true}

# COMMAND ----------

# DBTITLE 1,Widgets for Development parameters
# For development only
dbutils.widgets.text("log", "debug")
dbutils.widgets.text("args", '{}')

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Get job context
# Standard libraries
import logging

# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug("Initialized job context with keys: %s", sorted(job_ctx))

# COMMAND ----------

from oeds.domain.utils.schema.schema_deployment_utils import SchemaDeploymentManager

schema_deployment_manager = SchemaDeploymentManager.initialize(
    job_ctx.get("env")
).get_instance()

# Parse args
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

# Table reference
ref = str(args.get("ref") or "").strip()
logger.info(f"ref: {ref}")
if not ref:
    raise ValueError("args.ref is required")

# replace flag
replace = args.get("replace","true")
logger.info(f"Replace: {replace}")

# COMMAND ----------

logger.info(f"Creating table: {ref}")
schema_deployment_manager.create_table(ref, replace=replace)

