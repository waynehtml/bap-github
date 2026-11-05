# Databricks notebook source
# DBTITLE 1,SWIFT vs HABS Reconciliation
# MAGIC %md
# MAGIC # SWIFT vs HABS Reconciliation (04)
# MAGIC
# MAGIC Three-way comparison of SWIFT DVR data, HABS CLOB data, and HABS Relational data. Matches by Transaction Reference + Date + Message Type. Writes results to `tbl_swift_habs_recon_results_fact`.

# COMMAND ----------

# DBTITLE 1,Configuration and read source tables
import json
from pyspark.sql import functions as F
from datetime import datetime

# --- Runtime parameters and tables ---
# Job parameter; interactive runs default to this workspace's env.
_ENV = {"adb-1700301391505163": "dev", "adb-13344226264609": "stg", "adb-642333651898149": "prd"}.get(
    spark.conf.get("spark.databricks.workspaceUrl", "").split(".")[0], "dev")
dbutils.widgets.text("catalog", f"{_ENV}_banking_and_payments_cat", "Catalog")
CATALOG = dbutils.widgets.get("catalog")
SWIFT_FACT = f"{CATALOG}.derived_db.tbl_swift_message_fact"
HABS_FACT = f"{CATALOG}.derived_db.tbl_habs_message_fact"
RECON_TABLE = f"{CATALOG}.derived_db.tbl_swift_habs_recon_results_fact"

# --- Widget: report date ---
dbutils.widgets.text("report_date", "", "Report date (YYYY-MM-DD)")
report_date_str = dbutils.widgets.get("report_date")

if report_date_str:
    report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
else:
    report_date = None

# Read SWIFT fact
swift_df = spark.table(SWIFT_FACT)
if report_date:
    swift_df = swift_df.where(F.col("source_file_date") == str(report_date))

# Read HABS fact - split into CLOB and Relational
habs_df = spark.table(HABS_FACT)
if report_date:
    habs_df = habs_df.where(F.col("trans_utc_date_id") == str(report_date))

# --- Scope to the files validated in this run ---
# Without this, every SWIFT file ever loaded (and every HABS day) is
# re-reconciled, so a single inbound upload also produced outbound rows.
try:
    run_files_json = dbutils.jobs.taskValues.get(
        taskKey="validate_swift_files", key="valid_files_json", debugValue=""
    ) or ""
except Exception:
    run_files_json = ""
run_files = json.loads(run_files_json) if run_files_json else []

# Validate ran in this job but passed no files (empty inbox, or every file
# rejected): there is nothing new to reconcile. Without this, the unscoped
# branch below re-reconciles every file ever loaded. An empty value means an
# interactive run, which still reconciles without file scope.
if run_files_json and not run_files:
    print("No valid files in this run; reconciliation skipped.")
    skipped = json.dumps({
        "report_date": str(report_date) if report_date else "all",
        "total_reconciled": 0, "warnings": 0, "success": 0,
        "habs_not_refreshed_dates": [], "skipped": "No valid files in this run",
    })
    dbutils.jobs.taskValues.set(key="result", value=skipped)
    dbutils.jobs.taskValues.set(key="status", value="SKIPPED")
    dbutils.notebook.exit(skipped)

if run_files:
    run_filenames = [f["filename"] for f in run_files]
    run_scope = spark.createDataFrame(
        sorted({(f["file_date"], f["file_type"]) for f in run_files}),
        "scope_date string, scope_direction string",
    ).withColumn("scope_date", F.to_date("scope_date"))
    swift_df = swift_df.where(F.col("source_filename").isin(run_filenames))
    habs_direction = F.when(F.col("habs_outgoing_message_ind") == 1, "OUTBOUND").otherwise("INBOUND")
    habs_df = habs_df.join(
        run_scope,
        (F.col("trans_utc_date_id") == F.col("scope_date")) & (habs_direction == F.col("scope_direction")),
        "left_semi",
    )
    print(f"Scoped to this run's files: {run_filenames}")
else:
    print("No valid_files_json from validate task; reconciling without file scope.")

habs_clob = habs_df.where(F.col("relational_table_ind") == 0)
habs_rel = habs_df.where(F.col("relational_table_ind") == 1)

print(f"SWIFT records: {swift_df.count()}")
print(f"HABS CLOB records: {habs_clob.count()}")
print(f"HABS Relational records: {habs_rel.count()}")

# COMMAND ----------

# DBTITLE 1,Aggregate SWIFT data by match keys
# Per ETL spec: group HABS by Transaction Reference + Transaction Date + Message Type
# to match SWIFT DVR which already comes grouped (Transactions Received > 1)

# SWIFT aggregated by match keys
swift_agg = swift_df.groupBy(
    F.col("source_filename"),
    F.col("trans_date_id").alias("report_date"),
    F.col("inbound_outbound_ind"),
    F.col("transaction_reference"),
    F.col("swift_gen_message_type"),
).agg(
    F.sum("transactions_received_cnt").cast("int").alias("swift_transaction_cnt"),
    # Original transaction-currency amount, the same unit as the HABS :32A: amount.
    # The CAD-converted column is rounded by SWIFT and differed by 0.01 on exact matches.
    F.sum("amount_received").alias("swift_amount"),
)

# HABS CLOB aggregated
habs_clob_agg = habs_clob.groupBy(
    F.col("trans_utc_date_id").alias("report_date"),
    F.when(F.col("habs_outgoing_message_ind") == 1, "OUTBOUND").otherwise("INBOUND").alias("inbound_outbound_ind"),
    F.col("transaction_reference"),
    F.col("swift_gen_message_type"),
).agg(
    F.count("*").cast("int").alias("clob_transaction_cnt"),
    F.sum("amount").alias("clob_amount"),
    F.max("application_update_ts").alias("clob_application_update_ts"),
)

# HABS Relational aggregated
habs_rel_agg = habs_rel.groupBy(
    F.col("trans_utc_date_id").alias("report_date"),
    F.when(F.col("habs_outgoing_message_ind") == 1, "OUTBOUND").otherwise("INBOUND").alias("inbound_outbound_ind"),
    F.col("transaction_reference"),
    F.col("swift_gen_message_type"),
).agg(
    F.count("*").cast("int").alias("db_transaction_cnt"),
    F.sum("amount").alias("db_amount"),
    F.max("application_update_ts").alias("db_application_update_ts"),
)

print(f"SWIFT aggregated groups: {swift_agg.count()}")
print(f"HABS CLOB aggregated groups: {habs_clob_agg.count()}")
print(f"HABS Relational aggregated groups: {habs_rel_agg.count()}")

# COMMAND ----------

# DBTITLE 1,Three-way join and reconciliation logic
# Three-way FULL OUTER JOIN on match keys
join_keys = ["report_date", "inbound_outbound_ind", "transaction_reference", "swift_gen_message_type"]

recon = swift_agg.alias("s").join(
    habs_clob_agg.alias("c"),
    on=join_keys,
    how="full_outer"
).join(
    habs_rel_agg.alias("d"),
    on=join_keys,
    how="full_outer"
).select(
    F.lit(None).cast("long").alias("recon_result_skey"),
    F.lit(None).cast("long").alias("md_workflow_execution_skey"),
    F.coalesce("s.report_date", "c.report_date", "d.report_date").alias("report_date"),
    F.col("s.source_filename").alias("source_filename"),
    F.coalesce("s.inbound_outbound_ind", "c.inbound_outbound_ind", "d.inbound_outbound_ind").alias("inbound_outbound_ind"),
    F.coalesce("s.transaction_reference", "c.transaction_reference", "d.transaction_reference").alias("transaction_reference"),
    F.coalesce("s.swift_gen_message_type", "c.swift_gen_message_type", "d.swift_gen_message_type").alias("swift_gen_message_type"),
    F.lit(None).cast("long").alias("swift_message_type_skey"),
    # SWIFT data
    F.coalesce("s.swift_transaction_cnt", F.lit(0)).alias("swift_transaction_cnt"),
    F.coalesce("s.swift_amount", F.lit(0)).alias("swift_amount"),
    F.lit(None).cast("long").alias("swift_currency_skey"),
    # HABS CLOB data
    F.coalesce("c.swift_gen_message_type", F.lit("Unknown")).alias("clob_message_type"),
    F.coalesce("c.clob_transaction_cnt", F.lit(0)).alias("clob_transaction_cnt"),
    F.coalesce("c.clob_amount", F.lit(0)).alias("clob_amount"),
    F.lit(None).cast("long").alias("clob_currency_skey"),
    F.col("c.clob_application_update_ts"),
    # HABS Relational data
    F.coalesce("d.swift_gen_message_type", F.lit("Unknown")).alias("db_message_type"),
    F.coalesce("d.db_transaction_cnt", F.lit(0)).alias("db_transaction_cnt"),
    F.coalesce("d.db_amount", F.lit(0)).alias("db_amount"),
    F.lit(None).cast("long").alias("db_currency_skey"),
    F.col("d.db_application_update_ts"),
)

# The relational (DB) side is only checked when HABS DB rows were loaded for
# this scope. 03_load_habs_message currently loads CLOB messages only, so
# requiring a DB match made Success impossible.
has_db_source = habs_rel.limit(1).count() > 0
print(f"HABS DB rows in scope: {has_db_source} — "
      + ("three-way SWIFT/CLOB/DB match" if has_db_source else "two-way SWIFT/CLOB match"))

clob_count_ok = F.col("swift_transaction_cnt") == F.col("clob_transaction_cnt")
clob_amount_ok = F.abs(F.col("swift_amount") - F.col("clob_amount")) < 0.01
db_count_ok = (F.col("swift_transaction_cnt") == F.col("db_transaction_cnt")) if has_db_source else F.lit(True)
db_amount_ok = (F.abs(F.col("swift_amount") - F.col("db_amount")) < 0.01) if has_db_source else F.lit(True)

# Determine reconciliation result: Warning if counts or amounts don't match
recon = recon.withColumn(
    "recon_result",
    F.when(clob_count_ok & clob_amount_ok & db_count_ok & db_amount_ok, F.lit("Success"))
     .otherwise(F.lit("Warning"))
).withColumn(
    "warning_reason",
    F.when(F.col("recon_result") == "Warning",
        F.concat_ws("; ",
            F.when(~clob_count_ok, F.lit("SWIFT/CLOB count mismatch")),
            F.when(~db_count_ok, F.lit("SWIFT/DB count mismatch")),
            F.when(~clob_amount_ok, F.lit("SWIFT/CLOB amount mismatch")),
            F.when(~db_amount_ok, F.lit("SWIFT/DB amount mismatch")),
        )
    )
).withColumn("audit_create_ts", F.current_timestamp()) \
 .withColumn("audit_last_update_ts", F.current_timestamp()) \
 .withColumn(
     "recon_result_code",
     F.when(F.col("recon_result") == "Success", F.lit("MATCH")).otherwise(F.lit("WARNING"))
 )

# HABS not refreshed yet (03_load_habs_message): SWIFT rows with no HABS
# message on those business dates are not real mismatches, so say why.
try:
    habs_not_refreshed_dates = json.loads(dbutils.jobs.taskValues.get(
        taskKey="load_habs_message", key="habs_not_refreshed_dates", debugValue="[]"
    ) or "[]")
except Exception:
    habs_not_refreshed_dates = []
HABS_NOT_REFRESHED = (
    "HABS not refreshed yet for this business date (BAP-HABS-WORKPACKAGE1 has not loaded it); "
    "upload the file again after it completes"
)
if habs_not_refreshed_dates:
    print(f"HABS not refreshed for {habs_not_refreshed_dates}; marking affected warnings")
    recon = recon.withColumn(
        "warning_reason",
        F.when(
            (F.col("recon_result") == "Warning")
            & F.col("report_date").cast("string").isin(habs_not_refreshed_dates)
            & (F.col("clob_transaction_cnt") == 0),
            F.lit(HABS_NOT_REFRESHED),
        ).otherwise(F.col("warning_reason")),
    )
recon = recon.withColumn("recon_result_detail", F.col("warning_reason"))

warning_count = recon.where(F.col("recon_result") == "Warning").count()
success_count = recon.where(F.col("recon_result") == "Success").count()
print(f"Reconciliation: {success_count} Success, {warning_count} Warning(s)")

# COMMAND ----------

# DBTITLE 1,Write reconciliation results
# --- Tag rows with this pipeline run's job run ID ---
# Reports (07) and notifications (05) select this run's rows by ID instead of
# by audit date, so runs crossing midnight or two runs on one day stay separate.
def _job_run_id():
    """Job run ID shared by every task of this run, or None when run interactively."""
    try:
        tags = json.loads(
            dbutils.notebook.entry_point.getDbutils().notebook().getContext().toJson()
        ).get("tags", {})
        value = tags.get("multitaskParentRunId") or ""
        return int(value) if value else None
    except Exception:
        return None

JOB_RUN_ID = _job_run_id()
print(f"Job run ID: {JOB_RUN_ID}")
recon = recon.withColumn("md_workflow_execution_skey", F.lit(JOB_RUN_ID).cast("long"))

if recon.count() > 0:
    if run_files:
        # Re-uploading a file replaces its earlier reconciliation instead of
        # stacking another copy: remove this file's rows and the HABS-only rows
        # (no source_filename) for the same business date and direction.
        def _q(value):
            return "'" + str(value).replace("'", "''") + "'"

        file_list = ", ".join(_q(name) for name in run_filenames)
        scope_list = " OR ".join(
            f"(report_date = DATE {_q(d)} AND inbound_outbound_ind = {_q(t)})"
            for d, t in sorted({(f["file_date"], f["file_type"]) for f in run_files})
        )
        spark.sql(
            f"DELETE FROM {RECON_TABLE} WHERE source_filename IN ({file_list}) "
            f"OR (source_filename IS NULL AND ({scope_list}))"
        )
    recon.write.mode("append").saveAsTable(RECON_TABLE)
    print(f"Wrote {recon.count()} row(s) to {RECON_TABLE}")
    display(recon.limit(10))
else:
    print("No reconciliation results to write (no SWIFT or HABS data for this period).")

# COMMAND ----------

# DBTITLE 1,Notebook exit with summary
result = json.dumps({
    "report_date": report_date_str or "all",
    "total_reconciled": recon.count() if recon else 0,
    "warnings": warning_count,
    "success": success_count,
    "habs_not_refreshed_dates": habs_not_refreshed_dates,
})
dbutils.jobs.taskValues.set(key="recon_result", value=result)
# Downstream tasks use this to select exactly this run's reconciliation rows.
dbutils.jobs.taskValues.set(key="job_run_id", value=str(JOB_RUN_ID or ""))
dbutils.jobs.taskValues.set(key="status", value="PASSED")
print(f"Notebook result: {result}")
dbutils.notebook.exit(result)
