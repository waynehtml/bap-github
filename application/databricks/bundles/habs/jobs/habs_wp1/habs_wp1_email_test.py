# Databricks notebook source
# MAGIC %run ../../common

# COMMAND ----------

import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)
job_ctx = get_job_context()
email_manager = initialize_email_manager(job_ctx)

# COMMAND ----------

# Select a status before running this cell to test each completion-email outcome.
dbutils.widgets.dropdown(
    "test_status",
    "FAILED",
    ["SUCCEEDED", "FAILED", "INCOMPLETE", "SKIPPED - NON-BUSINESS DAY"],
)
test_status = dbutils.widgets.get("test_status")

status_styles = {
    "FAILED": ("#b42318", "#fff1f0"),
    "SKIPPED - NON-BUSINESS DAY": ("#8a5d00", "#fff8e1"),
    "INCOMPLETE": ("#8a5d00", "#fff8e1"),
    "SUCCEEDED": ("#146c34", "#edf8f0"),
}
status_color, status_background = status_styles[test_status]
task_summary = pd.DataFrame(
    [
        {"task": "Business day check", "status": "SUCCEEDED"},
        {"task": "Raw build", "status": "SUCCEEDED"},
        {"task": "Dimension build", "status": "SUCCEEDED"},
        {"task": "Fact build", "status": test_status},
    ]
)

# COMMAND ----------

email_manager.send_email(
    template_ref="wp1_completion",
    variables={
        "ENV": f"Test-{job_ctx.get('env', 'dev').upper()}",
        "job_name": "BAP-HABS-WORKPACKAGE1",
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "job_run_id": "email-test",
        "status": test_status,
        "status_color": status_color,
        "status_background": status_background,
        "email_table_html": email_manager.df_to_email_table(task_summary),
    },
)

logger.info("Sent WP1 completion email test with status: %s", test_status)
