# Databricks notebook source
# DBTITLE 1,Generate DVR report rows
# MAGIC %md
# MAGIC Writes this run's transaction-level reconciliation report rows to `curated_db.tbl_dvr_recon_report` (one row per transaction, same columns as the former .xlsx/.html reports). No report files are written to the raw volume.

# COMMAND ----------

# DBTITLE 1,Write DVR report rows to curated_db
import json
from datetime import datetime

from pyspark.sql import functions as F

# Job parameters; interactive runs default to this workspace's env.
_ENV = {"adb-1700301391505163": "dev", "adb-13344226264609": "stg", "adb-642333651898149": "prd"}.get(
    spark.conf.get("spark.databricks.workspaceUrl", "").split(".")[0], "dev")
dbutils.widgets.text("catalog", f"{_ENV}_banking_and_payments_cat", "Catalog")
dbutils.widgets.text("report_date", "", "Report date (YYYY-MM-DD)")
dbutils.widgets.text("valid_files_json", "", "Current run valid files")
CATALOG = dbutils.widgets.get("catalog")
REPORT_DATE = dbutils.widgets.get("report_date") or datetime.now().strftime("%Y-%m-%d")
valid_files_json = dbutils.widgets.get("valid_files_json")
# Fall back to the validate task's value when the job doesn't pass it explicitly.
if not valid_files_json:
    try:
        valid_files_json = dbutils.jobs.taskValues.get(
            taskKey="validate_swift_files", key="valid_files_json", debugValue=""
        ) or ""
    except Exception:
        valid_files_json = ""
valid_files = [
    item for item in (json.loads(valid_files_json) if valid_files_json else [])
    if isinstance(item, dict) and item.get("filename")
]
valid_filenames = [item["filename"] for item in valid_files]
# (business date, direction) pairs covered by this run's uploaded files.
run_scope = sorted({(item.get("file_date"), item.get("file_type")) for item in valid_files})
run_directions = sorted({direction for _, direction in run_scope if direction})
RECON_TABLE = f"{CATALOG}.curated_db.tbl_swift_habs_recon_results_fact"
# Report rows (replaces the .xlsx/.html files in <raw volume>/reports).
REPORT_TABLE = f"{CATALOG}.curated_db.tbl_dvr_recon_report"

# Validate ran in this job but passed no files: no new report rows. Without
# this, the date fallback below re-reports earlier runs. An empty value means
# an interactive run, which keeps the date fallback.
if valid_files_json and not valid_files:
    print("No valid files in this run; report not generated.")
    dbutils.jobs.taskValues.set(key="status", value="SKIPPED")
    dbutils.notebook.exit(str({
        "report_date": REPORT_DATE, "report_table": REPORT_TABLE, "rows": 0,
        "files": [], "reports": [], "skipped": "No valid files in this run",
    }))

# Select this run's reconciliation rows by the job run ID that 04_reconcile
# stamped on them (audit_run_id). This keeps runs separate even
# when two run on the same day or a run crosses midnight. Fall back to the
# audit date for interactive runs or rows written without a run ID.
try:
    JOB_RUN_ID = dbutils.jobs.taskValues.get(
        taskKey="reconcile", key="job_run_id", debugValue=""
    ) or ""
except Exception:
    JOB_RUN_ID = ""
recon_all = spark.table(RECON_TABLE)
run_rows = (
    recon_all.where(F.col("audit_run_id") == F.lit(int(JOB_RUN_ID)))
    if JOB_RUN_ID.isdigit() else None
)
if run_rows is not None and run_rows.limit(1).count() > 0:
    report_df = run_rows
    print(f"Selecting reconciliation rows for job run {JOB_RUN_ID}")
else:
    # ``report_date`` is the business date of the file; ``REPORT_DATE`` is the run date.
    report_df = recon_all.where(F.to_date("audit_create_ts") == F.lit(REPORT_DATE))
    print(f"No job run ID rows; selecting reconciliation rows created on {REPORT_DATE}")
if valid_filenames:
    # Keep this run's SWIFT rows plus HABS-only rows (no source file) for the
    # same business date and direction, so missing-in-SWIFT items still show.
    habs_only_in_scope = F.lit(False)
    for scope_date, scope_direction in run_scope:
        habs_only_in_scope = habs_only_in_scope | (
            (F.col("report_date") == F.to_date(F.lit(scope_date)))
            & (F.col("inbound_outbound_ind") == F.lit(scope_direction))
        )
    report_df = report_df.where(
        F.col("source_filename").isin(valid_filenames)
        | (F.col("source_filename").isNull() & habs_only_in_scope)
    )
report_df = report_df.dropDuplicates(
    ["source_filename", "report_date", "inbound_outbound_ind",
     "transaction_reference", "swift_gen_message_type", "recon_result"]
)
# Only report the directions uploaded in this run (an inbound-only upload must
# not create outbound report rows).
if run_directions:
    report_df = report_df.where(F.col("inbound_outbound_ind").isin(run_directions))

# Same columns as the former .xlsx/.html reports, plus run identifiers.
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
# Findur match details (release-2.2.0) are copied when both tables have them.
_report_target_cols = set(spark.table(REPORT_TABLE).columns) if spark.catalog.tableExists(REPORT_TABLE) else set()
findur_out = [c for c in FINDUR_REPORT_COLUMNS if c in report_df.columns and c in _report_target_cols]
if len(findur_out) < len(FINDUR_REPORT_COLUMNS):
    print("Findur columns not on both recon and report tables (release-2.2.0); report written without them.")
run_id_value = int(JOB_RUN_ID) if JOB_RUN_ID.isdigit() else None
report_out = report_df.select(
    F.col("report_date").cast("date").alias("report_date"),
    *[F.col(c) for c in REPORT_COLUMNS[1:]],
    *[F.col(c) for c in findur_out],
    F.to_date(F.lit(REPORT_DATE)).alias("report_run_date"),
    F.lit(run_id_value).cast("long").alias("audit_run_id"),
    F.current_timestamp().alias("audit_create_ts"),
)

# Keep one copy per file in the report table, the same rule 04_reconcile uses
# for the recon table: re-uploading a file (or repairing this run) replaces the
# earlier rows for that file and the HABS-only rows for the same business date
# and direction. Without this, queries by report_date counted a file twice.
if spark.catalog.tableExists(REPORT_TABLE):
    def _q(value):
        return "'" + str(value).replace("'", "''") + "'"

    conditions = []
    if run_id_value is not None:
        conditions.append(f"audit_run_id = {run_id_value}")
    if valid_filenames:
        conditions.append(
            "source_filename IN (" + ", ".join(_q(n) for n in valid_filenames) + ")"
        )
        scope_list = " OR ".join(
            f"(report_date = DATE {_q(d)} AND inbound_outbound_ind = {_q(t)})"
            for d, t in run_scope if d and t
        )
        if scope_list:
            conditions.append(f"(source_filename IS NULL AND ({scope_list}))")
    if conditions:
        spark.sql(f"DELETE FROM {REPORT_TABLE} WHERE " + " OR ".join(conditions))
report_out.write.mode("append").saveAsTable(REPORT_TABLE)

counts = {
    row["inbound_outbound_ind"]: row["count"]
    for row in report_out.groupBy("inbound_outbound_ind").count().collect()
}
report_directions = run_directions or sorted(d for d in counts if d)
reports_written = [{"direction": d, "rows": counts.get(d, 0)} for d in report_directions]
for item in reports_written:
    print(f"Wrote {item['rows']} {item['direction']} row(s) to {REPORT_TABLE}")

result = {
    "report_date": REPORT_DATE,
    "report_table": REPORT_TABLE,
    "rows": sum(counts.values()),
    "files": valid_filenames,
    "reports": reports_written,
}
print(result)
dbutils.jobs.taskValues.set(key="status", value="PASSED")
dbutils.notebook.exit(str(result))

