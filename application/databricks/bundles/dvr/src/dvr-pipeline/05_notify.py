# Databricks notebook source
# DBTITLE 1,DVR Notification
# MAGIC %md
# MAGIC # DVR Notification (05)
# MAGIC
# MAGIC Sends email notifications based on reconciliation results.
# MAGIC Uses the OEDS `EmailManager` initialized by `common.py` with HTML templates from `conf/oeds/config/email/`.

# COMMAND ----------

# DBTITLE 1,Initialize common + read upstream results
# MAGIC %run ../../common

# COMMAND ----------

# DBTITLE 1,Read upstream results and determine notification type
import json
import html
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pyspark.sql import functions as F
from oeds.domain.utils.email.email_utils import EmailManager

# --- Tables (derived from job context) ---
CATALOG = _ctx["catalog"]  # job parameter, or this workspace's env (common.py)
RECON_TABLE = f"{CATALOG}.derived_db.tbl_swift_habs_recon_results_fact"
PROCESSING_LOG = f"{CATALOG}.derived_db.tbl_dvr_file_processing_log"

# --- Read upstream task results (taskValues, then table fallback) ---
try:
    validation_json = dbutils.jobs.taskValues.get(
        taskKey="validate_swift_files", key="result", debugValue=""
    )
    validation = json.loads(validation_json) if validation_json else {}
except Exception:
    validation = {}

try:
    recon_json = dbutils.jobs.taskValues.get(
        taskKey="reconcile", key="result", debugValue=""
    )
    recon = json.loads(recon_json) if recon_json else {}
except Exception:
    recon = {}

# Validate ran and found nothing in the inbox (no valid or rejected files):
# nothing new to report. Do not fall back to today's processing log, which
# would re-send results for files that earlier runs already reported.
# Rejected-only runs still continue and send the validation email.
if validation and not validation.get("total_processed"):
    print("No files in the inbox for this run; no notification sent.")
    dbutils.jobs.taskValues.set(key="status", value="SKIPPED")
    dbutils.notebook.exit(json.dumps({
        "notification_type": "NONE", "email_sent": False, "emails_sent": 0,
        "files_notified": [], "reason": "No files in the inbox",
    }))

today = datetime.now(ZoneInfo(_ctx.get("timezone", "America/Toronto"))).date()
report_date_str = str(today)


def _run_recon_rows():
    """This run's reconciliation rows, selected by the job run ID that
    04_reconcile stamped on them. Falls back to the audit date for interactive
    runs or rows written without a run ID."""
    try:
        run_id = dbutils.jobs.taskValues.get(
            taskKey="reconcile", key="job_run_id", debugValue=""
        ) or ""
    except Exception:
        run_id = ""
    recon_all = spark.table(RECON_TABLE)
    if run_id.isdigit():
        rows = recon_all.where(F.col("md_workflow_execution_skey") == F.lit(int(run_id)))
        if rows.limit(1).count() > 0:
            return rows
    return recon_all.where(F.to_date("audit_create_ts") == F.lit(today))

# Table fallback when taskValues are empty
if not validation.get("total_processed"):
    try:
        log_df = spark.table(PROCESSING_LOG).where(
            F.to_date("processing_start_ts") == F.lit(today)
        )
        total = log_df.count()
        invalid_df = log_df.where(F.col("processing_status") != "VALID")
        valid_df = log_df.where(F.col("processing_status") == "VALID")
        invalid = invalid_df.count()
        validation = {
            "total_processed": total,
            "invalid_count": invalid,
            "invalid_files": [
                {"filename": row.filename, "errors": [{
                    "Additional_Details": row.error_description or "Validation failed"
                }]}
                for row in invalid_df.select("filename", "error_description").collect()
            ],
            "valid_files": [
                {"filename": row.filename}
                for row in valid_df.select("filename").collect()
            ],
        }
        logger.info("Read from processing log: %d processed, %d invalid", total, invalid)
    except Exception as e:
        logger.warning("Could not read processing log: %s", e)

if not recon.get("total_reconciled"):
    try:
        recon_df = _run_recon_rows()
        total_r = recon_df.count()
        warnings_r = recon_df.where(F.col("recon_result") == "Warning").count()
        success_r = recon_df.where(F.col("recon_result") == "Success").count()
        recon = {"total_reconciled": total_r, "warnings": warnings_r, "success": success_r}
        logger.info("Read from recon table: %d total, %d matched", total_r, success_r)
    except Exception as e:
        logger.warning("Could not read recon table: %s", e)

# --- Build one notification record per file ---
TEMPLATE_MAP = {
    "SUCCESS": "dvr_success",
    "WARNINGS": "dvr_warnings",
    "VALIDATION_ERROR": "dvr_validation_error",
    "NO_FILES": "dvr_file_check",
    "PIPELINE_FAILURE": "dvr_processing_error",
}

invalid_count = validation.get("invalid_count", 0)
total_processed = validation.get("total_processed", 0)
valid_files = validation.get("valid_files", [])
invalid_files = validation.get("invalid_files", [])


def unique_file_records(records):
    """Keep one notification record per filename in a batch."""
    unique = []
    seen = set()
    for record in records:
        filename = record.get("filename", "") if isinstance(record, dict) else str(record)
        if filename in seen:
            continue
        seen.add(filename)
        unique.append(record)
    return unique


# Defensively deduplicate task values and table-fallback results. This prevents
# duplicate emails when the processing log contains multiple rows for the same
# file or when an older deployed validation task does not provide task values.
valid_files = unique_file_records(valid_files)
invalid_files = unique_file_records(invalid_files)

# Older validation results only returned invalid filenames. Keep those results
# compatible while using the richer per-file error data when available.
invalid_records = []
for item in invalid_files:
    if isinstance(item, str):
        invalid_records.append({"filename": item, "errors": []})
    else:
        invalid_records.append(item)

file_notifications = []
for invalid in invalid_records:
    error_rows = []
    for error in invalid.get("errors", []):
        error_rows.append({
            "filename": invalid.get("filename", ""),
            "error_code": error.get("Error_Code", ""),
            "error": error.get("Additional_Details", error.get("Description", "")),
        })
    file_notifications.append({
        "filename": invalid.get("filename", ""),
        "notification_type": "VALIDATION_ERROR",
        "total_reconciled": 0,
        "success": 0,
        "warnings": 0,
        "error_rows": error_rows,
    })

# Reconciliation rows retain source_filename so a mixed batch can produce
# independent success/warning notifications for each valid file.
try:
    recon_by_file = _run_recon_rows()
except Exception as e:
    logger.warning("Could not read per-file reconciliation results: %s", e)
    recon_by_file = None

def _task_status(task_key):
    """Return the status task value an upstream task set, or '' if it failed/was skipped."""
    try:
        return dbutils.jobs.taskValues.get(taskKey=task_key, key="status", debugValue="") or ""
    except Exception:
        return ""


# Every pipeline task publishes a "status" task value when it succeeds, so a
# missing value means the task failed or was skipped. copy_legacy_r_drive
# publishes its copy outcome (SUBMITTED / NO_VALID_FILES / SKIPPED_NO_R_DRIVE_PATH)
# instead of PASSED; any non-empty value counts as success.
PIPELINE_TASKS = [
    "validate_swift_files", "copy_legacy_r_drive", "parse_load_swift",
    "load_habs_message", "reconcile", "generate_reports",
]
failed_tasks = [task_key for task_key in PIPELINE_TASKS if not _task_status(task_key)]
reconcile_ran = _task_status("reconcile") == "PASSED"
if failed_tasks:
    logger.warning("Pipeline task(s) failed or were skipped: %s", failed_tasks)

# Rule:
#   - any task failed  -> PIPELINE_FAILURE email, still including the
#                         reconciliation warnings when reconcile ran
#   - all tasks passed -> WARNINGS if the data does not match, else SUCCESS
for valid in valid_files:
    filename = valid.get("filename", "") if isinstance(valid, dict) else str(valid)
    if reconcile_ran and recon_by_file is not None:
        # Deduplicate in case the same file was reconciled by an earlier run today.
        file_recon = recon_by_file.where(F.col("source_filename") == filename).dropDuplicates(
            ["report_date", "inbound_outbound_ind", "transaction_reference",
             "swift_gen_message_type", "recon_result"]
        )
        total = file_recon.count()
        warnings = file_recon.where(F.col("recon_result") == "Warning").count()
        success = file_recon.where(F.col("recon_result") == "Success").count()
    else:
        # Reconciliation did not run for this file, so there are no counts to report.
        total, warnings, success = "Not available", "Not available", "Not available"

    if failed_tasks:
        file_type = "PIPELINE_FAILURE"
    elif warnings > 0 or total == 0:
        file_type = "WARNINGS"
    else:
        file_type = "SUCCESS"

    file_notifications.append({
        "filename": filename,
        "notification_type": file_type,
        "total_reconciled": total,
        "success": success,
        "warnings": warnings,
        "error_rows": [],
    })

if not file_notifications and total_processed == 0:
    # A failed run with no file list (e.g. validation itself failed) is a
    # failure, not a "no files received" reminder.
    file_notifications.append({
        "filename": "",
        "notification_type": "PIPELINE_FAILURE" if failed_tasks else "NO_FILES",
        "total_reconciled": 0,
        "success": 0,
        "warnings": 0,
        "error_rows": [],
    })

notification_type = (
    "MIXED" if len({item["notification_type"] for item in file_notifications}) > 1
    else file_notifications[0]["notification_type"]
)
logger.info("Prepared %d per-file notification(s), overall type: %s", len(file_notifications), notification_type)
print(f"Report date: {report_date_str}")
print(f"Notification count: {len(file_notifications)}")
print(f"Overall notification type: {notification_type}")

# Include task outcomes in every notification. A missing status indicates that
# the task failed or did not run before notify executed with ALL_DONE.
task_statuses = {
    "validate_swift_files": "FAILED/NOT RUN",
    "copy_legacy_r_drive": "FAILED/NOT RUN",
    "parse_load_swift": "FAILED/NOT RUN",
    "load_habs_message": "FAILED/NOT RUN",
    "reconcile": "FAILED/NOT RUN",
    "generate_reports": "FAILED/NOT RUN",
}
for task_key in task_statuses:
    try:
        status = dbutils.jobs.taskValues.get(
            taskKey=task_key, key="status", debugValue=""
        )
        if status:
            task_statuses[task_key] = status
    except Exception:
        pass
task_status_html = "<h2>Pipeline Task Results</h2><table>"
task_status_html += "<tr><th>Task</th><th>Status</th></tr>"
for task_key, status in task_statuses.items():
    task_status_html += (
        f"<tr><td>{html.escape(task_key)}</td>"
        f"<td><strong>{html.escape(status)}</strong></td></tr>"
    )
task_status_html += "</table>"

# HABS not refreshed yet (03_load_habs_message): explain the warnings up front.
try:
    habs_not_refreshed_dates = json.loads(dbutils.jobs.taskValues.get(
        taskKey="load_habs_message", key="habs_not_refreshed_dates", debugValue="[]"
    ) or "[]")
except Exception:
    habs_not_refreshed_dates = []
if habs_not_refreshed_dates:
    task_status_html = (
        "<p style=\"padding:10px;background:#fff3cd;border:1px solid #ffeeba;\">"
        "<strong>HABS not refreshed yet</strong> for business date(s) "
        f"{html.escape(', '.join(habs_not_refreshed_dates))}. "
        "BAP-HABS-WORKPACKAGE1 had not loaded HABS when this file was processed, so "
        "SWIFT transactions show as warnings. Upload the file again after HABS is refreshed.</p>"
        + task_status_html
    )

# COMMAND ----------

# DBTITLE 1,Send email via EmailManager
# ---------------------------------------------------------------------------
# Send email via EmailManager (initialized by common.py)
# No fallback needed — oeds is always available via cluster/requirements.txt
# ---------------------------------------------------------------------------
email_sent = False
emails_sent = 0
email_errors = []
em = EmailManager.get_instance()

for item in file_notifications:
    file_type = item["notification_type"]
    template_ref = TEMPLATE_MAP.get(file_type)
    if not template_ref:
        logger.warning("Unknown notification type for %s: %s", item["filename"], file_type)
        continue

    try:
        error_df = pd.DataFrame(
            item["error_rows"],
            columns=["filename", "error_code", "error"],
        )
        variables = {
            "ENV": _ctx["env"].upper(),
            "filename": item["filename"] or "No files received",
            "report_date": report_date_str,
            "total_reconciled": str(item["total_reconciled"]),
            "success": str(item["success"]),
            "warnings": str(item["warnings"]),
            "invalid_count": "1" if file_type == "VALIDATION_ERROR" else "0",
            "email_table_html": (
                em.df_to_email_table(error_df) if not error_df.empty else ""
            ),
            "task_status_html": task_status_html,
            "failed_tasks": ", ".join(failed_tasks) if failed_tasks else "None",
        }
        em.send_email(template_ref=template_ref, variables=variables)
        emails_sent += 1
        email_sent = True
        logger.info(
            "Email sent for file %s via EmailManager (template: %s)",
            item["filename"] or "<none>",
            template_ref,
        )
    except Exception as e:
        email_errors.append(f"{item['filename'] or '<none>'}: {e}")
        logger.error("EmailManager failed for file %s: %s", item["filename"], e, exc_info=True)

print(f"Notification type: {notification_type}, Emails sent: {emails_sent}")

if email_errors:
    raise RuntimeError(
        f"Failed to send {len(email_errors)} DVR notification(s): "
        + "; ".join(email_errors)
    )

# COMMAND ----------

# DBTITLE 1,Notebook exit
result = json.dumps({
    "notification_type": notification_type,
    "email_sent": email_sent,
    "emails_sent": emails_sent,
    "files_notified": [item["filename"] for item in file_notifications],
})
print(f"Notebook result: {result}")
dbutils.notebook.exit(result)
