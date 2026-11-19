# Databricks notebook source
# MAGIC %md
# MAGIC ## Dependency Check
# MAGIC - Resolve each configured operation-status dependency sequentially.
# MAGIC - Fail after reporting every dependency with no matching success record.

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

from oeds.domain.utils.operation import (
    OperationStatusManager,
    TimeFilter,
)

# COMMAND ----------

logger = logging.getLogger(__name__)
job_ctx = get_job_context()

rundate = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="rundate",
    debugValue=job_ctx["rundate"],
)

# COMMAND ----------

# MAGIC %md
# MAGIC Configure project dependencies in the list below. For example:
# MAGIC
# MAGIC - `dataset` and `layer` are required and identify the dependency in logs.
# MAGIC - Add optional criteria such as `batch_id` or `completed_at` to narrow
# MAGIC   the lookup.
# MAGIC - Every operation-status row represents a successful operation. A
# MAGIC   dependency is missing when no row matches its criteria.
# MAGIC
# MAGIC ```python
# MAGIC dependencies = [
# MAGIC     {
# MAGIC         "dataset": "upstream_dataset",
# MAGIC         "layer": "standardization",
# MAGIC         "batch_id": rundate,
# MAGIC     },
# MAGIC     {
# MAGIC         "dataset": "daily_reference",
# MAGIC         "layer": "standardization",
# MAGIC         "completed_at": TimeFilter(
# MAGIC             on=parse_date(rundate, job_ctx["python_date_format"])
# MAGIC         ),
# MAGIC     },
# MAGIC ]
# MAGIC ```

# COMMAND ----------

# Keep this list empty when the curation workflow has no upstream dependencies.
# Add one criteria mapping per upstream dataset when checks are required.
dependencies: list[dict[str, object]] = []
operation_status_manager = OperationStatusManager()

# Resolve every dependency before failing so the task log identifies every
# missing upstream dataset rather than stopping at the first one.
missing_count = 0
for criteria in dependencies:
    result = operation_status_manager.resolve_dependency(criteria)
    identifier = f"{criteria['dataset']} in {criteria['layer']}"
    logger.info(
        "Resolved curation dependency: identifier=%s criteria=%s available=%s",
        identifier,
        criteria,
        result is not None,
    )
    if result is None:
        missing_count += 1

# Only recorded successes are available to downstream curation.
if missing_count:
    raise RuntimeError(
        f"Curation dependencies are not ready: {missing_count} missing"
    )

if dependencies:
    logger.info(
        "All %s curation dependencies succeeded for rundate %s",
        len(dependencies),
        rundate,
    )
else:
    logger.info("No curation dependencies configured for rundate %s", rundate)
