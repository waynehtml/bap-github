# Databricks notebook source
# MAGIC %md
# MAGIC ## Create and refresh a materialized view
# MAGIC Pre-create `tbl_sample` during release. Choose one compute route and keep
# MAGIC it for subsequent refreshes. This notebook defaults to the job-context
# MAGIC warehouse; the alternative below requires supported serverless compute.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

from oeds.domain.utils.schema.schema_deployment_utils import SchemaDeploymentManager

ctx = get_job_context()
deployment = SchemaDeploymentManager.initialize(ctx["env"]).get_instance()
warehouse_id = ctx["sql_warehouse_serverless_large_id"]

# COMMAND ----------

# MAGIC %md
# MAGIC To use serverless notebook compute instead, set `warehouse_id = None`
# MAGIC before running the remaining cells. This omits the warehouse argument.

# COMMAND ----------

execution_options = {} if warehouse_id is None else {"warehouse_id": warehouse_id}
deployment.create_materialized_view(
    "mv_sample", if_not_exists=True, **execution_options
)

# COMMAND ----------

deployment.refresh_materialized_view("mv_sample", **execution_options)

# COMMAND ----------

# MAGIC %md
# MAGIC Optional full recomputation: run the following call when needed.
# MAGIC ```python
# MAGIC deployment.refresh_materialized_view(
# MAGIC     "mv_sample", full=True, **execution_options
# MAGIC )
# MAGIC ```
