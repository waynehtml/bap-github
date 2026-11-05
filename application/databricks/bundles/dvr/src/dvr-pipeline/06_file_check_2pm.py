# Databricks notebook source
# DBTITLE 1,SWIFT DVR 2 PM file check
# MAGIC %md
# MAGIC # DVR 2 PM File Check (06)
# MAGIC
# MAGIC Checks the processing log for today's valid SWIFT DVR files and sends an alert
# MAGIC when the expected inbound or outbound files are missing.
# MAGIC Uses OEDS `EmailManager` initialized by `common.py` with the `dvr_file_check` HTML template.

# COMMAND ----------

# DBTITLE 1,Initialize common
# MAGIC %run ../../common

# COMMAND ----------

# DBTITLE 1,Check for missing files and send alert via EmailManager
import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pyspark.sql import functions as F
from oeds.domain.utils.email.email_utils import EmailManager

CATALOG = _ctx["catalog"]  # job parameter, or this workspace's env (common.py)
PROCESSING_LOG = f"{CATALOG}.derived_db.tbl_dvr_file_processing_log"
today = datetime.now(ZoneInfo(_ctx.get("timezone", "America/Toronto"))).date()

# The business process expects one inbound and one outbound report per day.
expected_types = {"INBOUND", "OUTBOUND"}
try:
    processed = {
        row["file_type"]
        for row in (
            spark.table(PROCESSING_LOG)
            .where(F.to_date("file_date") == F.lit(today))
            .where(F.col("processing_status") == "VALID")
            .select("file_type")
            .distinct()
            .collect()
        )
        if row["file_type"]
    }
except Exception as exc:
    raise RuntimeError(f"Unable to query DVR processing log {PROCESSING_LOG}: {exc}") from exc

missing = sorted(expected_types - processed)
print(f"Report date: {today}; processed: {sorted(processed)}; missing: {missing}")

# --- Send alert via EmailManager (dvr_file_check template) ---
email_sent = False
if missing:
    try:
        em = EmailManager.get_instance()
        file_status = (
            [{"File Type": t, "Status": "MISSING"} for t in missing]
            + [{"File Type": t, "Status": "OK"} for t in sorted(processed)]
        )
        file_df = pd.DataFrame(file_status)

        variables = {
            "ENV": _ctx["env"].upper(),
            "report_date": str(today),
            "missing_count": str(len(missing)),
            "email_table_html": em.df_to_email_table(file_df),
        }
        em.send_email(template_ref="dvr_file_check", variables=variables)
        email_sent = True
        logger.info("2 PM file-check email sent (%d missing)", len(missing))
    except Exception as e:
        logger.error("2 PM notification failed: %s", e, exc_info=True)
else:
    logger.info("All expected file types processed — no alert needed.")

result = json.dumps({
    "report_date": str(today),
    "processed_types": sorted(processed),
    "missing_types": missing,
    "email_sent": email_sent,
})
print(result)
dbutils.notebook.exit(result)
