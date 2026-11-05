# Databricks notebook source
# MAGIC %run ../../common

# COMMAND ----------

import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)
job_ctx = get_job_context()
email_manager = initialize_email_manager(job_ctx)

task_states = {
    "Business day check": dbutils.widgets.get("check_business_day_state"),
    "Raw build": dbutils.widgets.get("build_raw_state"),
    "Dimension build": dbutils.widgets.get("build_dim_state"),
    "Fact build": dbutils.widgets.get("build_fact_state"),
}
run_pipeline = dbutils.widgets.get("run_pipeline")
normalized_task_states = {
    task_name: str(task_state).strip().upper()
    for task_name, task_state in task_states.items()
}
normalized_run_pipeline = str(run_pipeline).strip()

if any(state == "FAILED" for state in normalized_task_states.values()):
    status = "FAILED"
elif normalized_run_pipeline == "0":
    status = "SKIPPED - NON-BUSINESS DAY"
elif any(
    state in {"EXCLUDED", "UPSTREAM_FAILED"}
    for state in normalized_task_states.values()
):
    status = "INCOMPLETE"
else:
    status = "SUCCEEDED"

status_styles = {
    "FAILED": ("#b42318", "#fff1f0"),
    "SKIPPED - NON-BUSINESS DAY": ("#8a5d00", "#fff8e1"),
    "INCOMPLETE": ("#8a5d00", "#fff8e1"),
    "SUCCEEDED": ("#146c34", "#edf8f0"),
}
status_color, status_background = status_styles[status]

task_summary = pd.DataFrame(
    [{"task": task_name, "status": task_state} for task_name, task_state in task_states.items()]
)

email_manager.send_email(
    template_ref="wp1_completion",
    variables={
        "ENV": job_ctx.get("env", "dev").upper(),
        "job_name": job_ctx.get("job_name", "BAP-HABS-WORKPACKAGE1"),
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "job_run_id": job_ctx.get("job_run_id", "unknown"),
        "status": status,
        "status_color": status_color,
        "status_background": status_background,
        "email_table_html": email_manager.df_to_email_table(task_summary),
    },
)

logger.info("Sent WP1 completion notification with status: %s", status)
