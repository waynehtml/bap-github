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
from decimal import Decimal
from oeds.domain.utils.email.email_utils import EmailManager

# --- Tables (derived from job context) ---
CATALOG = _ctx["catalog"]  # job parameter, or this workspace's env (common.py)
RECON_TABLE = f"{CATALOG}.curated_db.tbl_swift_habs_recon_results_fact"
PROCESSING_LOG = f"{CATALOG}.standardized_db.tbl_dvr_file_processing_log"

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
        rows = recon_all.where(F.col("audit_run_id") == F.lit(int(run_id)))
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
        out_of_scope_r = recon_df.where(F.col("recon_result") == "Out of scope").count()
        recon = {"total_reconciled": total_r, "warnings": warnings_r, "success": success_r,
                 "out_of_scope": out_of_scope_r}
        logger.info("Read from recon table: %d total, %d matched, %d warning(s), %d out of scope",
                    total_r, success_r, warnings_r, out_of_scope_r)
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
# missing value means the task failed or was skipped. land_to_raw
# publishes its copy outcome (SUBMITTED / NO_FILES / SKIPPED_NO_R_DRIVE_PATH)
# instead of PASSED; any non-empty value counts as success.
PIPELINE_TASKS = [
    "validate_swift_files", "land_to_raw", "parse_load_swift",
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
# The email lists only the first few unmatched SWIFT rows to stay readable;
# the rest are summarised in one line and listed in the Excel attachment.
# --- Currency codes for per-currency totals ---
# Amounts stay in their own currency (ARM, 30 Oct), so totals are shown per
# currency instead of adding CAD, USD and GBP together. Same shared currency
# dimension as 02_parse_load_swift (USD is skey 0, CAD is skey 6).
CURRENCY_DIM_TABLE = f"{_ctx['env']}_financial_markets_cat.fmbo_unmodelled_views_db.vwu_finddw_currency_dim"
try:
    CURRENCY_CODES = {
        int(r["skey"]): r["code"]
        for r in spark.table(CURRENCY_DIM_TABLE).select(
            F.col("currency_skey").cast("long").alias("skey"),
            F.upper(F.trim(F.col("currency_name"))).alias("code"),
        ).where(F.col("skey").isNotNull()).collect()
    }
except Exception as e:
    logger.warning("Could not read currency dimension %s: %s", CURRENCY_DIM_TABLE, e)
    CURRENCY_CODES = {6: "CAD"}


def _ccy_code(skey):
    if skey is None or skey == -1:
        return "Unknown"
    return CURRENCY_CODES.get(int(skey), f"skey {skey}")


def _totals_by_currency(df, present, skey_col, amount_col):
    """[(currency, rows, amount)] for rows where `present` is true; CAD first."""
    out = [
        (_ccy_code(r["skey"]), int(r["n"]), r["amt"] or Decimal(0))
        for r in df.where(present).groupBy(F.col(skey_col).alias("skey")).agg(
            F.count("*").alias("n"), F.sum(amount_col).alias("amt")
        ).collect()
    ]
    return sorted(out, key=lambda t: (t[0] != "CAD", t[0]))

for valid in valid_files:
    filename = valid.get("filename", "") if isinstance(valid, dict) else str(valid)
    file_info = valid if isinstance(valid, dict) else {}
    if reconcile_ran and recon_by_file is not None:
        # SWIFT file rows (source_filename matches this file).
        file_recon = recon_by_file.where(F.col("source_filename") == filename).dropDuplicates(
            ["report_date", "inbound_outbound_ind", "transaction_reference",
             "swift_gen_message_type", "recon_result"]
        )
        # HABS-only rows for the same business date and direction.
        scope_date = file_info.get("file_date")
        scope_direction = file_info.get("file_type")
        if scope_date and scope_direction:
            habs_only_df = recon_by_file.where(
                F.col("source_filename").isNull()
                & (F.col("report_date") == F.to_date(F.lit(scope_date)))
                & (F.col("inbound_outbound_ind") == F.lit(scope_direction))
            ).dropDuplicates(
                ["report_date", "inbound_outbound_ind", "transaction_reference",
                 "swift_gen_message_type", "recon_result"]
            )
        else:
            habs_only_df = recon_by_file.where(F.lit(False))
        # Single aggregation over file + HABS-only rows.
        all_df = file_recon.unionByName(habs_only_df)
        _has_clob = F.coalesce(F.col("clob_transaction_cnt"), F.lit(0)) > 0
        _has_db = F.coalesce(F.col("db_transaction_cnt"), F.lit(0)) > 0
        _swift_warn_c = F.col("source_filename").isNotNull() & (F.col("recon_result") == "Warning")
        _reason_c = F.coalesce(F.col("warning_reason"), F.lit(""))
        _foreign_ccy_r = _reason_c.contains("Foreign currency")
        _db_loading_r = _reason_c.contains("HABS DB still loading")
        _missing_db_r = _reason_c.contains("Missing in HABS DB")
        agg = all_df.agg(
            F.sum(F.when(F.col("source_filename").isNotNull(), 1).otherwise(0)).alias("n_swift"),
            F.sum(F.when(
                F.col("source_filename").isNotNull() & (F.col("recon_result") == "Success"), 1
            ).otherwise(0)).alias("n_matched"),
            F.sum(F.when(
                F.col("source_filename").isNotNull() & (F.col("recon_result") == "Warning"), 1
            ).otherwise(0)).alias("n_unmatched"),
            F.sum(F.when(
                F.col("source_filename").isNotNull(), F.col("swift_amount")
            ).otherwise(0)).alias("swift_total"),
            # HABS-only warnings; internal-sender rows are counted separately.
            F.sum(F.when(
                F.col("source_filename").isNull() & (F.col("recon_result") != "Out of scope"), 1
            ).otherwise(0)).alias("n_habs_only"),
            F.sum(F.when(F.col("recon_result") == "Out of scope", 1).otherwise(0)).alias("n_out_of_scope"),
            F.sum(F.when(
                F.col("source_filename").isNotNull() & (F.col("recon_result_code") == "MATCH_FINDUR"), 1
            ).otherwise(0)).alias("n_findur"),
            F.sum(F.when(_swift_warn_c & _foreign_ccy_r, 1).otherwise(0)).alias("n_foreign_ccy"),
            F.sum(F.when(_swift_warn_c & ~_foreign_ccy_r & ~_has_clob & ~_has_db, 1).otherwise(0)).alias("n_not_in_habs"),
            F.sum(F.when(_swift_warn_c & ~_foreign_ccy_r & _has_clob & ~_has_db & _db_loading_r, 1).otherwise(0)).alias("n_db_loading"),
            F.sum(F.when(_swift_warn_c & ~_foreign_ccy_r & _has_clob & ~_has_db & _missing_db_r, 1).otherwise(0)).alias("n_clob_only"),
            F.sum(F.when(_swift_warn_c & ~_foreign_ccy_r & ~_has_clob & _has_db, 1).otherwise(0)).alias("n_db_only"),
            F.sum(F.when(F.col("clob_transaction_cnt") > 0, 1).otherwise(0)).alias("n_clob"),
            F.sum(F.when(
                F.col("clob_transaction_cnt") > 0, F.col("clob_amount")
            ).otherwise(0)).alias("clob_total"),
            F.sum(F.when(F.col("db_transaction_cnt") > 0, 1).otherwise(0)).alias("n_db"),
            F.sum(F.when(
                F.col("db_transaction_cnt") > 0, F.col("db_amount")
            ).otherwise(0)).alias("db_total"),
        ).collect()[0]
        n_swift_rows = int(agg["n_swift"] or 0)
        n_matched = int(agg["n_matched"] or 0)
        n_unmatched = int(agg["n_unmatched"] or 0)
        swift_total_amount = agg["swift_total"] or Decimal(0)
        n_habs_only = int(agg["n_habs_only"] or 0)
        n_out_of_scope = int(agg["n_out_of_scope"] or 0)
        n_findur = int(agg["n_findur"] or 0)
        # Per-currency totals (email and Excel Summary use the same numbers).
        swift_by_ccy = _totals_by_currency(
            all_df, F.col("source_filename").isNotNull(), "swift_currency_skey", "swift_amount")
        clob_by_ccy = _totals_by_currency(
            all_df, F.col("clob_transaction_cnt") > 0, "clob_currency_skey", "clob_amount")
        db_by_ccy = _totals_by_currency(
            all_df, F.col("db_transaction_cnt") > 0, "db_currency_skey", "db_amount")
        n_habs_clob = int(agg["n_clob"] or 0)
        clob_total_amount = agg["clob_total"] or Decimal(0)
        n_habs_db = int(agg["n_db"] or 0)
        db_total_amount = agg["db_total"] or Decimal(0)
        total = n_swift_rows + n_habs_only + n_out_of_scope
        success = n_matched
        warnings = n_unmatched
    else:
        # Reconciliation did not run for this file.
        total, warnings, success = "N/A", "N/A", "N/A"
        n_swift_rows, swift_total_amount = "N/A", "N/A"
        n_matched, n_unmatched = "N/A", "N/A"
        n_habs_clob, clob_total_amount = "N/A", "N/A"
        n_habs_db, db_total_amount = "N/A", "N/A"
        n_habs_only = "N/A"
        n_out_of_scope = "N/A"
        n_findur = 0
        swift_by_ccy, clob_by_ccy, db_by_ccy = None, None, None

    # Status based only on SWIFT file rows matching HABS.
    # HABS-only rows are informational and do not affect the status.
    if failed_tasks:
        file_type = "PIPELINE_FAILURE"
    elif isinstance(n_unmatched, int) and n_unmatched > 0:
        file_type = "WARNINGS"
    elif isinstance(n_swift_rows, int) and n_swift_rows == 0:
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
        "swift_file_rows": n_swift_rows,
        "swift_file_amount": swift_total_amount,
        "matched_count": n_matched,
        "unmatched_count": n_unmatched,
        "habs_clob_rows": n_habs_clob,
        "habs_clob_amount": clob_total_amount,
        "habs_db_rows": n_habs_db,
        "habs_db_amount": db_total_amount,
        "habs_only_count": n_habs_only,
        "out_of_scope_count": n_out_of_scope,
        "findur_matched_count": n_findur,
        "swift_by_ccy": swift_by_ccy,
        "clob_by_ccy": clob_by_ccy,
        "db_by_ccy": db_by_ccy,
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
    "land_to_raw": "FAILED/NOT RUN",
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

# DBTITLE 1,Build Excel report attachment
# Excel reconciliation report attached to the success/warnings email.
# Built from curated_db.tbl_dvr_recon_report (written by 07_generate_reports);
# replaces the .xlsx files that used to be saved in <raw volume>/reports.
import io
import zipfile
from decimal import Decimal
from xml.sax.saxutils import escape as _xml_escape

REPORT_TABLE = f"{CATALOG}.curated_db.tbl_dvr_recon_report"
REPORT_COLUMNS = [
    "report_date", "inbound_outbound_ind", "transaction_reference",
    "swift_gen_message_type", "swift_transaction_cnt", "swift_amount",
    "clob_transaction_cnt", "clob_amount", "db_transaction_cnt", "db_amount",
    "recon_result", "warning_reason", "source_filename",
]
FINDUR_REPORT_COLUMNS = [
    "findur_deal_num", "findur_document_num", "findur_transaction_cnt", "findur_amount",
    "findur_currency_skey", "findur_value_date", "findur_match_type",
]
_MAX_ATTACHMENT_BYTES = 2_900_000  # Graph direct attachments must be < 3 MiB


def _col_name(index):
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _xlsx_cell(ref, value, bold=False):
    style = ' s="1"' if bold else ""
    if value is None:
        return f'<c r="{ref}"{style}/>'
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, (int, float, Decimal)):
        return f'<c r="{ref}"{style}><v>{value}</v></c>'
    text = _xml_escape(str(value))
    return f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'


def _xlsx_bytes(sheets):
    """Build a basic .xlsx with the standard library (openpyxl is not on the
    job cluster). sheets: list of (sheet_name, header, rows)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            f'{overrides}</Types>')
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        sheet_xml = "".join(
            f'<sheet name="{_xml_escape(name[:31])}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _, _) in enumerate(sheets, start=1)
        )
        z.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{sheet_xml}</sheets></workbook>')
        rels = "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        n = len(sheets) + 1
        z.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{rels}<Relationship Id="rId{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
        z.writestr("xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '</styleSheet>')
        for i, (_, header, rows) in enumerate(sheets, start=1):
            lines = []
            for r_idx, row in enumerate([header] + list(rows), start=1):
                cells = "".join(
                    _xlsx_cell(f"{_col_name(c_idx)}{r_idx}", v, bold=(r_idx == 1))
                    for c_idx, v in enumerate(row)
                )
                lines.append(f'<row r="{r_idx}">{cells}</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                f'<sheetData>{"".join(lines)}</sheetData></worksheet>')
    return buf.getvalue()


def _report_attachment(filename):
    """This run's report rows for one file as an .xlsx attachment, or None.
    Same columns as the former reports/ .xlsx files."""
    if not filename or not spark.catalog.tableExists(REPORT_TABLE):
        return None
    info = next((f for f in valid_files if isinstance(f, dict) and f.get("filename") == filename), {})
    try:
        run_id = dbutils.jobs.taskValues.get(
            taskKey="reconcile", key="job_run_id", debugValue=""
        ) or ""
    except Exception:
        run_id = ""
    df = spark.table(REPORT_TABLE)
    if run_id.isdigit():
        df = df.where(F.col("audit_run_id") == F.lit(int(run_id)))
    else:
        df = df.where(F.col("report_run_date") == F.lit(today))
    in_file = F.col("source_filename") == F.lit(filename)
    if info.get("file_date") and info.get("file_type"):
        # HABS-only rows (no SWIFT file) for the same business date and direction.
        in_file = in_file | (
            F.col("source_filename").isNull()
            & (F.col("report_date") == F.to_date(F.lit(info["file_date"])))
            & (F.col("inbound_outbound_ind") == F.lit(info["file_type"]))
        )
    sheet_cols = REPORT_COLUMNS + [c for c in FINDUR_REPORT_COLUMNS if c in df.columns]
    rows = (
        df.where(in_file).select(*sheet_cols)
        .orderBy("recon_result", "swift_gen_message_type", "transaction_reference")
        .collect()
    )
    if not rows:
        return None

    def _cell(r, c):
        v = r[c]
        if v is None:
            return None
        if c in ("report_date", "findur_value_date"):
            return str(v)
        if c == "findur_currency_skey":
            return _ccy_code(v)
        return v

    detail = [[_cell(r, c) for c in sheet_cols] for r in rows]
    sheet_header = ["findur_currency" if c == "findur_currency_skey" else c for c in sheet_cols]
    n_findur = sum(1 for r in rows if "findur_match_type" in sheet_cols and r["findur_match_type"])
    n_success = sum(1 for r in rows if r["recon_result"] == "Success")
    n_warning = sum(1 for r in rows if r["recon_result"] == "Warning")
    n_out_of_scope = sum(1 for r in rows if r["recon_result"] == "Out of scope")
    direction = info.get("file_type") or (rows[0]["inbound_outbound_ind"] or "")
    business_date = info.get("file_date") or str(rows[0]["report_date"] or "")
    # Detailed breakdown so the summary explains every number.
    n_swift_rows = sum(1 for r in rows if r["source_filename"] is not None)
    n_has_clob = sum(
        1 for r in rows
        if r["clob_transaction_cnt"] is not None and r["clob_transaction_cnt"] > 0
    )
    n_has_db = sum(
        1 for r in rows
        if r["db_transaction_cnt"] is not None and r["db_transaction_cnt"] > 0
    )
    swift_total_amt = sum(
        (r["swift_amount"] or Decimal(0)) for r in rows
        if r["source_filename"] is not None
    )
    clob_total_amt = sum(
        (r["clob_amount"] or Decimal(0)) for r in rows
        if r["clob_transaction_cnt"] is not None and r["clob_transaction_cnt"] > 0
    )
    db_total_amt = sum(
        (r["db_amount"] or Decimal(0)) for r in rows
        if r["db_transaction_cnt"] is not None and r["db_transaction_cnt"] > 0
    )
    # Per-currency totals computed for the email (same recon rows).
    _ccy = next((n for n in file_notifications if n.get("filename") == filename), {})

    def _ccy_lines(by_ccy, fallback_total):
        if not by_ccy:
            return [["  Total amount", fallback_total]]
        return [[f"  Total amount {code} ({n:,} row{'' if n == 1 else 's'})", amt]
                for code, n, amt in by_ccy]

    # Warning sub-categories, each counted directly from the row values.
    n_habs_only_warn = sum(
        1 for r in rows
        if r["recon_result"] == "Warning" and r["source_filename"] is None
    )
    _swift_warn = [
        r for r in rows
        if r["recon_result"] == "Warning" and r["source_filename"] is not None
    ]
    def _reason(r):
        return r["warning_reason"] or ""

    n_foreign_ccy = sum(1 for r in _swift_warn if "Foreign currency" in _reason(r))
    _non_fx = [r for r in _swift_warn if "Foreign currency" not in _reason(r)]
    _clob_no_db = [r for r in _non_fx if r["clob_transaction_cnt"] and not r["db_transaction_cnt"]]
    n_not_in_habs = sum(1 for r in _non_fx if not r["clob_transaction_cnt"] and not r["db_transaction_cnt"])
    n_db_loading = sum(1 for r in _clob_no_db if "HABS DB still loading" in _reason(r))
    n_clob_only = sum(1 for r in _clob_no_db if "Missing in HABS DB" in _reason(r))
    n_db_only = sum(1 for r in _non_fx if r["db_transaction_cnt"] and not r["clob_transaction_cnt"])
    # Everything else: the transaction is in HABS but the count or amount differs.
    n_both_differ = len(_swift_warn) - n_foreign_ccy - n_not_in_habs - n_db_loading - n_clob_only - n_db_only
    summary = [
        ["File", filename],
        ["Direction", direction],
        ["Business date", business_date],
        ["Run date", report_date_str],
        ["Job run ID", run_id or "interactive"],
        ["", ""],
        ["SWIFT file rows", n_swift_rows],
        *_ccy_lines(_ccy.get("swift_by_ccy"), swift_total_amt),
        ["HABS CLOB rows", n_has_clob],
        *_ccy_lines(_ccy.get("clob_by_ccy"), clob_total_amt),
        ["HABS DB rows", n_has_db],
        *_ccy_lines(_ccy.get("db_by_ccy"), db_total_amt),
        ["", ""],
        ["Reconciliation rows (all sources)", len(rows)],
        ["Success (3-way match or Findur)", n_success],
        *([["  Matched in Findur (foreign currency)", n_findur]] if n_findur else []),
        ["Warning (unmatched SWIFT + HABS-only)", n_warning],
        ["", ""],
        ["Unmatched SWIFT rows", len(_swift_warn)],
        ["Foreign currency, not matched in HABS or Findur", n_foreign_ccy],
        ["Not in HABS (no CLOB, no DB)", n_not_in_habs],
        ["In HABS CLOB only (missing in HABS DB)", n_clob_only],
        ["In HABS DB only (missing in HABS CLOB)", n_db_only],
    ]
    # Shown only when non-zero so the breakdown stays short but still adds up.
    if n_db_loading:
        summary.append(["In HABS CLOB, HABS DB still loading", n_db_loading])
    if n_both_differ:
        summary.append(["In HABS, but amount or count differs", n_both_differ])
    summary += [
        ["", ""],
        ["HABS-only (in HABS, not in SWIFT file)", n_habs_only_warn],
        ["Out of scope (Receiver General via Viagate, not in SWIFT DVR)", n_out_of_scope],
    ]
    content = _xlsx_bytes([
        ("Summary", ["Item", "Value"], summary),
        ("Reconciliation", sheet_header, detail),
    ])
    if len(content) >= _MAX_ATTACHMENT_BYTES:
        logger.warning("Report for %s is %d bytes; too large to attach", filename, len(content))
        return None
    name = f"DVR_Recon_Report_{direction or 'FILE'}_{business_date.replace('-', '')}.xlsx"
    return {
        "name": name,
        "content": content,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }


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


def _amount_rows(by_ccy):
    """Indented 'Total amount <CCY> (n rows)' rows for the email summary.
    None means reconciliation did not run (N/A); an empty list means 0 rows."""
    if by_ccy is None:
        return '<tr><td style="padding-left:32px">&ndash; Total amount</td><td>N/A</td></tr>'
    if not by_ccy:
        return '<tr><td style="padding-left:32px">&ndash; Total amount</td><td>0.00</td></tr>'
    return "".join(
        f'<tr><td style="padding-left:32px">&ndash; Total amount {html.escape(code)} '
        f'({n:,} row{"" if n == 1 else "s"})</td><td>{amt:,.2f}</td></tr>'
        for code, n, amt in by_ccy
    )


def _fmt_amount(val):
    """Format a numeric value with commas and 2 decimals for email display."""
    if isinstance(val, (int, float, Decimal)):
        return f"{val:,.2f}"
    return str(val)


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
        # Unmatched rows: one line only; the full list and reasons are in the Excel.
        unmatched_html = ""
        _um_total = item.get("unmatched_count")
        if isinstance(_um_total, int) and _um_total > 0:
            unmatched_html = (
                f'<p style="color:#E65100"><strong>There {"is" if _um_total == 1 else "are"} '
                f'{_um_total} unmatched row{"" if _um_total == 1 else "s"}.</strong> '
                f'Check the attached Excel report for details.</p>'
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
            "swift_file_rows": str(item.get("swift_file_rows", "N/A")),
            "swift_file_amount": _fmt_amount(item.get("swift_file_amount", "N/A")),
            "matched_count": str(item.get("matched_count", "N/A")),
            "unmatched_count": str(item.get("unmatched_count", "N/A")),
            "habs_clob_rows": str(item.get("habs_clob_rows", "N/A")),
            "habs_clob_amount": _fmt_amount(item.get("habs_clob_amount", "N/A")),
            "habs_db_rows": str(item.get("habs_db_rows", "N/A")),
            "habs_db_amount": _fmt_amount(item.get("habs_db_amount", "N/A")),
            "habs_only_count": str(item.get("habs_only_count", "N/A")),
            "out_of_scope_count": str(item.get("out_of_scope_count", "N/A")),
            "unmatched_details_html": unmatched_html,
            "findur_matched_row": (
                '<tr><td style="padding-left:32px">&ndash; of which matched in Findur (foreign currency)</td>'
                f'<td>{item["findur_matched_count"]}</td></tr>'
                if isinstance(item.get("findur_matched_count"), int) and item["findur_matched_count"] > 0 else ""
            ),
            "swift_amount_rows": _amount_rows(item.get("swift_by_ccy")),
            "habs_clob_amount_rows": _amount_rows(item.get("clob_by_ccy")),
            "habs_db_amount_rows": _amount_rows(item.get("db_by_ccy")),
        }
        # Success/warnings emails carry this file's reconciliation report as
        # .xlsx. A report problem must not stop the email itself.
        attachments = None
        if file_type in ("SUCCESS", "WARNINGS"):
            try:
                report = _report_attachment(item["filename"])
                if report:
                    attachments = [report]
                    logger.info("Attaching %s (%d bytes)", report["name"], len(report["content"]))
            except Exception as report_error:
                logger.warning("Report attachment skipped for %s: %s", item["filename"], report_error)
        em.send_email(template_ref=template_ref, variables=variables, attachments=attachments)
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

