# Databricks notebook source
# MAGIC %run ../../common

# COMMAND ----------

# Standard libraries
import logging

import pandas as pd

from oeds.domain.utils.email import EmailManager

# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

# Create a caller-owned manager from the configuration loaded by common.py.
email_manager = EmailManager.get_instance()

# COMMAND ----------

# Preview the configured email registry entry resolved from the packaged config.
email_definition = email_manager.get_email_registry("failure")
logger.info(f"email_definition: {email_definition}")
print("resolved recipients:", email_definition["recipients"])
print("template:", email_definition["template"])
print("subject:", email_definition["subject"])

# COMMAND ----------

# Build sample variables for the packaged failure template.
variables = {
    "ENV": job_ctx.get("env", "dev").upper(),
    "audit_skey": "123456789",
    "code": "EXAMPLE_FAILURE",
    "state": "FAILED",
    "message": "This is a template bundle example email.",
}

# Optional attachment content can be a pandas DataFrame, string, or bytes.
attachment_content = pd.DataFrame(
    [
        {
            "step": "extract",
            "status": "completed",
            "details": "Example upstream task finished successfully.",
        },
        {
            "step": "load",
            "status": "failed",
            "details": "Example validation failed before publish.",
        },
    ]
)

# Convert a DataFrame to styled HTML when an email body template needs a table.
email_table_html = email_manager.df_to_email_table(attachment_content)
variables["email_table_html"] = email_table_html

print("variables:", variables)
print("attachment rows:", len(attachment_content))

# COMMAND ----------

# Send the packaged failure email template using the configured job recipients.
email_manager.send_email(
    template_ref="failure",
    variables=variables,
    attachments=[
        {
            "name": "email-example-details.csv",
            "content": attachment_content,
            "content_type": "text/csv",
        }
    ],
)
