# Databricks notebook source
# MAGIC %md
# MAGIC ## Apply direct table and view permissions
# MAGIC Copy this sample into `releases/` and run it after creating the objects.
# MAGIC - task: releases/release-0.0.0-13-apply-permissions.py
# MAGIC - args: {"schema_ref":""}
# MAGIC
# MAGIC An empty `schema_ref` selects all configured entries.
# MAGIC Uses the manager defaults: `default.json` from `oeds.config.permission`
# MAGIC with environment-first resolution, and `execute=True` to apply grants.
# MAGIC All selected permission entries are processed.
# MAGIC View dependencies receive no implicit grants. Existing grants remain.

# COMMAND ----------

# DBTITLE 1,Development parameters
dbutils.widgets.text("debug", "True")
dbutils.widgets.text("args", '{"schema_ref":""}')

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Apply configured permissions
import logging

from oeds.domain.utils.permission import PermissionManager

logger = logging.getLogger(__name__)
job_ctx = get_job_context()
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

schema_ref = str(args.get("schema_ref") or "").strip() or None

permission_manager = PermissionManager.initialize(job_ctx.get("env")).get_instance()
logger.info(
    "Applying direct permissions: env=%s, schema_ref=%s",
    permission_manager.env,
    schema_ref or "all",
)
permission_manager.apply_permissions(schema=schema_ref)
logger.info("Direct permission release step completed")
