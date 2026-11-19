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
SWIFT_FACT = f"{CATALOG}.curated_db.tbl_swift_message_fact"
HABS_FACT = f"{CATALOG}.curated_db.tbl_habs_message_fact"
RECON_TABLE = f"{CATALOG}.curated_db.tbl_swift_habs_recon_results_fact"

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
if "habs_sender_bic" not in habs_df.columns:
    print("WARNING: habs_sender_bic missing (run BAP-DATA-RELEASE-DEPLOYMENT release-2.1.0); "
          "internal-sender rows cannot be marked out of scope.")
    habs_df = habs_df.withColumn("habs_sender_bic", F.lit(None).cast("string"))
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
    F.max("swift_message_type_skey").alias("swift_message_type_skey"),
    F.max("originating_client_gle_skey").alias("originating_client_gle_skey"),
    F.max("counterparty_client_gle_skey").alias("counterparty_client_gle_skey"),
    F.max("beneficiary_client_gle_skey").alias("beneficiary_client_gle_skey"),
    F.max("currency_skey").alias("currency_skey"),
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
    F.max("swift_message_type_skey").alias("swift_message_type_skey"),
    F.max("originating_client_gle_skey").alias("originating_client_gle_skey"),
    F.max("counterparty_client_gle_skey").alias("counterparty_client_gle_skey"),
    F.max("beneficiary_client_gle_skey").alias("beneficiary_client_gle_skey"),
    F.max("currency_skey").alias("currency_skey"),
    F.count("*").cast("int").alias("clob_transaction_cnt"),
    F.max("habs_sender_bic").alias("habs_sender_bic"),
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
    F.max("swift_message_type_skey").alias("swift_message_type_skey"),
    F.max("originating_client_gle_skey").alias("originating_client_gle_skey"),
    F.max("counterparty_client_gle_skey").alias("counterparty_client_gle_skey"),
    F.max("beneficiary_client_gle_skey").alias("beneficiary_client_gle_skey"),
    F.max("currency_skey").alias("currency_skey"),
    F.count("*").cast("int").alias("db_transaction_cnt"),
    F.max("habs_sender_bic").alias("habs_sender_bic"),
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
    F.lit(None).cast("long").alias("audit_run_id"),
    F.coalesce("s.report_date", "c.report_date", "d.report_date").alias("report_date"),
    F.col("s.source_filename").alias("source_filename"),
    F.coalesce("s.inbound_outbound_ind", "c.inbound_outbound_ind", "d.inbound_outbound_ind").alias("inbound_outbound_ind"),
    F.coalesce("s.transaction_reference", "c.transaction_reference", "d.transaction_reference").alias("transaction_reference"),
    F.coalesce("s.swift_gen_message_type", "c.swift_gen_message_type", "d.swift_gen_message_type").alias("swift_gen_message_type"),
    F.coalesce(
        F.col("s.swift_message_type_skey"),
        F.col("c.swift_message_type_skey"),
        F.col("d.swift_message_type_skey"),
        F.lit(-1),
    ).alias("swift_message_type_skey"),
    F.coalesce(
        F.col("s.originating_client_gle_skey"),
        F.col("c.originating_client_gle_skey"),
        F.col("d.originating_client_gle_skey"),
        F.lit(-1),
    ).alias("originating_client_gle_skey"),
    F.coalesce(
        F.col("s.counterparty_client_gle_skey"),
        F.col("c.counterparty_client_gle_skey"),
        F.col("d.counterparty_client_gle_skey"),
        F.lit(-1),
    ).alias("counterparty_client_gle_skey"),
    F.coalesce(
        F.col("s.beneficiary_client_gle_skey"),
        F.col("c.beneficiary_client_gle_skey"),
        F.col("d.beneficiary_client_gle_skey"),
        F.lit(-1),
    ).alias("beneficiary_client_gle_skey"),
    # SWIFT data
    F.coalesce("s.swift_transaction_cnt", F.lit(0)).alias("swift_transaction_cnt"),
    F.coalesce("s.swift_amount", F.lit(0)).alias("swift_amount"),
    F.col("s.currency_skey").cast("long").alias("swift_currency_skey"),
    # HABS CLOB data
    F.coalesce("c.swift_gen_message_type", F.lit("Unknown")).alias("clob_message_type"),
    F.coalesce("c.clob_transaction_cnt", F.lit(0)).alias("clob_transaction_cnt"),
    F.coalesce("c.clob_amount", F.lit(0)).alias("clob_amount"),
    F.col("c.currency_skey").cast("long").alias("clob_currency_skey"),
    F.col("c.clob_application_update_ts"),
    # HABS Relational data
    F.coalesce("d.swift_gen_message_type", F.lit("Unknown")).alias("db_message_type"),
    F.coalesce("d.db_transaction_cnt", F.lit(0)).alias("db_transaction_cnt"),
    F.coalesce("d.db_amount", F.lit(0)).alias("db_amount"),
    F.col("d.currency_skey").cast("long").alias("db_currency_skey"),
    F.col("d.db_application_update_ts"),
    F.coalesce(F.col("c.habs_sender_bic"), F.col("d.habs_sender_bic")).alias("_habs_sender_bic"),
)

# --- Is HABS DB loaded for each business date and direction? ---
# HABS DB (relational) rows can arrive days after HABS CLOB. Decide per
# business date and direction, not once for the whole run:
#   NONE     no DB rows yet          -> match SWIFT against CLOB only
#   PARTIAL  fewer DB than CLOB rows -> rows missing only in DB are
#                                       "still loading", not real breaks
#   COMPLETE DB has at least as many rows as CLOB -> full three-way match
_scope_keys = ["report_date", "inbound_outbound_ind"]
_habs_dir = F.when(F.col("habs_outgoing_message_ind") == 1, "OUTBOUND").otherwise("INBOUND")
db_scope = (
    habs_clob.groupBy(
        F.col("trans_utc_date_id").alias("report_date"), _habs_dir.alias("inbound_outbound_ind")
    ).agg(F.count("*").alias("scope_clob_cnt"))
    .join(
        habs_rel.groupBy(
            F.col("trans_utc_date_id").alias("report_date"), _habs_dir.alias("inbound_outbound_ind")
        ).agg(F.count("*").alias("scope_db_cnt")),
        _scope_keys, "full_outer",
    )
    .fillna(0, ["scope_clob_cnt", "scope_db_cnt"])
    .withColumn(
        "db_load_status",
        F.when(F.col("scope_db_cnt") == 0, F.lit("NONE"))
         .when(F.col("scope_db_cnt") < F.col("scope_clob_cnt"), F.lit("PARTIAL"))
         .otherwise(F.lit("COMPLETE")),
    )
)
for _r in db_scope.orderBy(*_scope_keys).collect():
    print(f"HABS DB {_r.report_date} {_r.inbound_outbound_ind}: {_r.db_load_status} "
          f"({_r.scope_db_cnt} DB / {_r.scope_clob_cnt} CLOB rows)")
recon = recon.join(db_scope, _scope_keys, "left").fillna(
    {"db_load_status": "NONE", "scope_clob_cnt": 0, "scope_db_cnt": 0}
)

in_swift = F.col("swift_transaction_cnt") > 0
in_clob = F.col("clob_transaction_cnt") > 0
in_db = F.col("db_transaction_cnt") > 0
db_required = F.col("db_load_status") != "NONE"
db_loading = F.col("db_load_status") == "PARTIAL"

clob_count_ok = F.col("swift_transaction_cnt") == F.col("clob_transaction_cnt")
clob_amount_ok = F.abs(F.col("swift_amount") - F.col("clob_amount")) < 0.01
db_count_ok = F.col("swift_transaction_cnt") == F.col("db_transaction_cnt")
db_amount_ok = F.abs(F.col("swift_amount") - F.col("db_amount")) < 0.01

is_match = (
    in_swift & in_clob & clob_count_ok & clob_amount_ok
    & (~db_required | (in_db & db_count_ok & db_amount_ok))
)

# Reasons say what is missing first; count/amount differences are only
# reported when both sides of that comparison have the transaction.
# --- Foreign-currency detection ---
# HABS records only CAD payments (currency_skey 6 in all environments).
# Non-CAD SWIFT rows that are missing from both CLOB and DB get a specific
# reason so they are not confused with real breaks.
CAD_SKEY = 6
is_foreign_ccy = (
    in_swift & ~in_clob & ~in_db
    & F.col("swift_currency_skey").isNotNull()
    & (F.col("swift_currency_skey") != CAD_SKEY)
)

# --- "Still loading" age cutoff ---
# HABS DB rows arrive within 1-2 days.  After 2 calendar days the gap is
# real, not a timing issue, so the reason switches to "Missing in HABS DB".
DB_LOADING_CUTOFF_DAYS = 2
db_loading_fresh = db_loading & (
    F.datediff(F.current_date(), F.col("report_date")) <= DB_LOADING_CUTOFF_DAYS
)

HABS_DB_LOADING = "HABS DB still loading for this date"
warning_reason = F.concat_ws(
    "; ",
    F.when(is_foreign_ccy,
        F.concat(F.lit("Foreign currency, not recorded in HABS"))
    ),
    F.when(~is_foreign_ccy & ~in_swift, F.lit("Missing in SWIFT")),
    F.when(~is_foreign_ccy & ~in_clob, F.lit("Missing in HABS CLOB")),
    F.when(
        ~is_foreign_ccy & db_required & ~in_db & db_loading_fresh,
        F.concat(
            F.lit(HABS_DB_LOADING + " ("), F.col("scope_db_cnt").cast("string"), F.lit(" of "),
            F.col("scope_clob_cnt").cast("string"), F.lit(" rows loaded); upload again later"),
        ),
    ),
    F.when(~is_foreign_ccy & db_required & ~in_db & ~db_loading_fresh, F.lit("Missing in HABS DB")),
    F.when(~is_foreign_ccy & in_swift & in_clob & ~clob_count_ok, F.lit("SWIFT/CLOB count differs")),
    F.when(~is_foreign_ccy & in_swift & in_clob & ~clob_amount_ok, F.lit("SWIFT/CLOB amount differs")),
    F.when(~is_foreign_ccy & db_required & in_swift & in_db & ~db_count_ok, F.lit("SWIFT/DB count differs")),
    F.when(~is_foreign_ccy & db_required & in_swift & in_db & ~db_amount_ok, F.lit("SWIFT/DB amount differs")),
)

# --- Out of scope: internal senders (ARM decision, option B) ---
# Receiver General instructions arrive through Viagate (sender BIC8 PWGSXXW2).
# They are formatted like SWIFT messages so HABS can process them, but never go
# over the SWIFT network, so they are never in the SWIFT DVR file. Keep them in
# the report with their own result; they are not warnings.
INTERNAL_SENDER_BICS = ["PWGSXXW2"]
OUT_OF_SCOPE = "Out of scope"
OUT_OF_SCOPE_REASON = "Internal sender (Receiver General via Viagate), not in SWIFT DVR"
is_out_of_scope = ~in_swift & F.col("_habs_sender_bic").isin(INTERNAL_SENDER_BICS)

recon = recon.withColumn(
    "recon_result",
    F.when(is_out_of_scope, F.lit(OUT_OF_SCOPE))
     .when(is_match, F.lit("Success"))
     .otherwise(F.lit("Warning")),
).withColumn(
    "warning_reason",
    F.when(F.col("recon_result") == OUT_OF_SCOPE, F.lit(OUT_OF_SCOPE_REASON))
     .when(F.col("recon_result") == "Warning", warning_reason),
).withColumn("audit_create_ts", F.current_timestamp()) \
 .withColumn("audit_last_update_ts", F.current_timestamp()) \
 .withColumn(
     "recon_result_code",
     F.when(F.col("recon_result") == "Success", F.lit("MATCH"))
      .when(F.col("recon_result") == OUT_OF_SCOPE, F.lit("OUT_OF_SCOPE"))
      .otherwise(F.lit("WARNING"))
 ).drop("db_load_status", "scope_clob_cnt", "scope_db_cnt", "_habs_sender_bic")

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
out_of_scope_count = recon.where(F.col("recon_result") == OUT_OF_SCOPE).count()
print(f"Reconciliation: {success_count} Success, {warning_count} Warning(s), "
      f"{out_of_scope_count} Out of scope")

# COMMAND ----------

# DBTITLE 1,Match foreign-currency rows to Findur cash settlements
# --- Findur (ARM, Chris McNaught, Nov 2026) ---
# Foreign-currency (non-CAD) SWIFT payments are booked in Findur, not HABS.
# Findur is the system of record for them, so a non-CAD SWIFT row that is not
# in HABS is matched to a Findur cash settlement instead of being a warning.
#
# Findur sources:
#   - Settlement documents (ARM rule 2, BAPDP-88): Findur STLDOC_HEADER /
#     STLDOC_DETAILS, read live through the FMBODW Oracle federated catalog
#     (<env>_ext_ora_fmbodw_cat.finddw_stg.stldoc_*_sv). Cash settlement
#     (EVENT_TYPE 14), Released (DOC_STATUS 6) and sent (DOCUMENT_SENT_FLAG 1),
#     netted per document (SUM(SETTLE_AMOUNT) over every deal in it).
#     Needs classic compute (serverless cannot reach Oracle); this job runs
#     on a classic job cluster.
#   - Cash settlement events (findprod_ab_tran_event / _event_settle /
#     ab_tran in <env>_financial_markets_cat.standardized_db): EVENT_TYPE 14,
#     current, not cancelled/deleted deals, netted per deal, currency and
#     value date. Used for inbound, for the outbound value date, and as the
#     outbound fallback when the documents cannot be read.
#
# Matching (ARM rules 3 and 4):
#   - OUTBOUND: primary key is the Findur/SWIFT reference: the SWIFT
#     reference is deal + document number + document version
#     (11811923730723 = deal 1181192, document 373072, version 3). The
#     document must be Released and sent, in the SWIFT currency, with a
#     netted payment equal to the SWIFT amount. Exactly one valid document is
#     a match; otherwise the row stays a warning with the reason.
#     Fallback (documents unreadable): reference starts with the deal number,
#     validated on currency, netted amount and value date 0-7 days after the
#     SWIFT send date (cash events).
#   - INBOUND: there is no shared reference (FRBNY... is not in Findur;
#     DOC_EXTERNAL_REF is empty), so match on currency + value date + amount
#     against the cash events, only when exactly one Findur record matches and
#     it is not claimed by another SWIFT row. Zero or multiple matches stay
#     warnings. Settlement documents are not used for inbound: most receipts
#     (coupons, maturities) have no Released+sent document (Oct 2026: 1 of 7).
#
# The step is skipped (rows keep "Foreign currency, not recorded in HABS")
# when: the findur_matching widget is false, the Findur cash event tables
# cannot be read (no access), or the findur_* columns are missing
# (release-2.2.0 not run).
from datetime import timedelta
from pyspark.sql import Window
from pyspark.sql.types import DecimalType

dbutils.widgets.dropdown("findur_matching", "true", ["true", "false"], "Match foreign currency to Findur")
FINDUR_ENABLED = dbutils.widgets.get("findur_matching") == "true"
_FINDUR_ENV = CATALOG.split("_")[0] if CATALOG.split("_")[0] in ("dev", "stg", "prd") else _ENV
dbutils.widgets.text("findur_schema", f"{_FINDUR_ENV}_financial_markets_cat.standardized_db", "Findur schema")
FINDUR_SCHEMA = dbutils.widgets.get("findur_schema")
dbutils.widgets.text("findur_document_schema", f"{_FINDUR_ENV}_ext_ora_fmbodw_cat.finddw_stg", "Findur settlement document schema")
FINDUR_DOCUMENT_SCHEMA = dbutils.widgets.get("findur_document_schema")

FINDUR_CASH_SETTLEMENT = 14            # findprod_event_type: Cash Settlement
FINDUR_EXCLUDED_STATUSES = [5, 14, 17]  # findprod_trans_status: Cancelled, Deleted, Cancelled New
FINDUR_OUTBOUND_VALUE_DAYS = 7          # outbound value date: 0-7 days after the SWIFT send date
FINDUR_MIN_DEAL_DIGITS = 6              # shortest deal number accepted as a reference prefix
FINDUR_DOC_RELEASED = 6                 # STLDOC_HEADER.DOC_STATUS: Released
FINDUR_DOC_SENT = 1                     # STLDOC_HEADER.DOCUMENT_SENT_FLAG: sent
FINDUR_DOC_LOOKBACK_DAYS = 7            # document trade date: 0-7 days before the SWIFT send date

FINDUR_COLUMNS = {
    "findur_deal_num": "string",
    "findur_document_num": "string",
    "findur_transaction_cnt": "int",
    "findur_amount": DecimalType(30, 2),
    "findur_currency_skey": "bigint",
    "findur_value_date": "date",
    "findur_match_type": "string",
}
FX_REASON_PREFIX = "Foreign currency"
MATCH_FINDUR_DOC = "Matched in Findur (settlement document)"
MATCH_FINDUR_REF = "Matched in Findur (reference)"
MATCH_FINDUR_AMT = "Matched in Findur (amount/date)"
FX_KEYS = ["source_filename", "report_date", "inbound_outbound_ind",
           "transaction_reference", "swift_gen_message_type"]

def _add_null_findur_columns(df):
    for c, t in FINDUR_COLUMNS.items():
        if c not in df.columns:
            df = df.withColumn(c, F.lit(None).cast(t))
    return df

_recon_target_cols = set(spark.table(RECON_TABLE).columns) if spark.catalog.tableExists(RECON_TABLE) else set()
_findur_cols_ready = all(c in _recon_target_cols for c in FINDUR_COLUMNS)
if not _findur_cols_ready:
    print("WARNING: findur_* columns missing on the recon table (run BAP-DATA-RELEASE-DEPLOYMENT "
          "release-2.2.0); Findur matching skipped.")

# Candidate rows: non-CAD SWIFT warnings with nothing in HABS.
is_fx_candidate = (
    (F.col("recon_result") == "Warning")
    & F.col("source_filename").isNotNull()
    & F.col("swift_currency_skey").isNotNull()
    & (F.col("swift_currency_skey") != CAD_SKEY)
    & (F.coalesce(F.col("clob_transaction_cnt"), F.lit(0)) == 0)
    & (F.coalesce(F.col("db_transaction_cnt"), F.lit(0)) == 0)
)


def findur_cash_settlements(schema, date_from, date_to, currencies):
    """Netted Findur cash settlements per deal, currency and value date."""
    ev = (
        spark.table(f"{schema}.findprod_ab_tran_event")
        .where(
            (F.col("EVENT_TYPE") == FINDUR_CASH_SETTLEMENT)
            & (F.to_date("EVENT_DATE").between(F.lit(date_from), F.lit(date_to)))
            & F.col("CURRENCY").cast("bigint").isin(currencies)
        )
        .select("EVENT_NUM", "TRAN_NUM", "CURRENCY", "EVENT_DATE", "PARA_POSITION")
    )
    tran = (
        spark.table(f"{schema}.findprod_ab_tran")
        .where((F.col("CURRENT_FLAG") == 1) & ~F.col("TRAN_STATUS").cast("int").isin(FINDUR_EXCLUDED_STATUSES))
        .select("TRAN_NUM", "DEAL_TRACKING_NUM")
    )
    settle = spark.table(f"{schema}.findprod_ab_tran_event_settle").select("EVENT_NUM", "SETTLE_AMOUNT")
    return (
        ev.join(tran, "TRAN_NUM").join(settle, "EVENT_NUM", "left")
        .withColumn("_amt", F.coalesce(F.col("SETTLE_AMOUNT"), F.col("PARA_POSITION")).cast(DecimalType(30, 2)))
        .groupBy(
            F.col("DEAL_TRACKING_NUM").cast("bigint").cast("string").alias("f_deal"),
            F.col("CURRENCY").cast("bigint").alias("f_ccy"),
            F.to_date("EVENT_DATE").alias("f_value_date"),
        )
        .agg(F.sum("_amt").alias("f_amount"), F.count("*").cast("int").alias("f_cnt"))
    )


def findur_settlement_documents(schema, date_from, date_to, currencies):
    """Findur cash settlement documents (STLDOC) per deal within a document.

    One row per document + deal + currency, with the document netted over all
    of its deals (d_doc_net), its status and sent flag. Read in two steps so
    the netting includes every row of a document, even rows traded outside
    the date window (a document can net deals from different days).
    """
    det_all = spark.table(f"{schema}.stldoc_details_sv").where(F.col("EVENT_TYPE") == FINDUR_CASH_SETTLEMENT)
    in_window = det_all.where(
        F.col("TRADE_DATE").between(F.lit(date_from).cast("timestamp"), F.lit(date_to).cast("timestamp"))
        & F.col("SETTLE_CCY").isin(currencies)
    )
    doc_nums = [int(r[0]) for r in in_window.select("DOCUMENT_NUM").distinct().collect() if r[0] is not None]
    schema_out = ("d_doc string, d_tran string, d_ccy bigint, d_trade_date date, d_doc_net decimal(30,2), "
                  "d_cnt int, d_status int, d_sent int")
    if not doc_nums:
        return spark.createDataFrame([], schema_out)
    det = det_all.where(F.col("DOCUMENT_NUM").isin(doc_nums)).select(
        F.col("DOCUMENT_NUM").cast("bigint").cast("string").alias("d_doc"),
        F.col("TRAN_NUM").cast("bigint").cast("string").alias("d_tran"),
        F.col("SETTLE_CCY").cast("bigint").alias("d_ccy"),
        F.to_date("TRADE_DATE").alias("d_trade_date"),
        F.col("SETTLE_AMOUNT").cast(DecimalType(30, 2)).alias("_amt"),
    )
    hdr = spark.table(f"{schema}.stldoc_header_sv").where(F.col("DOCUMENT_NUM").isin(doc_nums)).select(
        F.col("DOCUMENT_NUM").cast("bigint").cast("string").alias("d_doc"),
        F.col("DOC_STATUS").cast("int").alias("d_status"),
        F.col("DOCUMENT_SENT_FLAG").cast("int").alias("d_sent"),
    )
    per_doc = det.groupBy("d_doc", "d_ccy").agg(
        F.sum("_amt").cast(DecimalType(30, 2)).alias("d_doc_net"), F.count("*").cast("int").alias("d_cnt"))
    per_tran = det.groupBy("d_doc", "d_tran", "d_ccy").agg(F.min("d_trade_date").alias("d_trade_date"))
    return per_tran.join(per_doc, ["d_doc", "d_ccy"]).join(hdr, "d_doc", "left").select(
        "d_doc", "d_tran", "d_ccy", "d_trade_date", "d_doc_net", "d_cnt", "d_status", "d_sent")


def match_outbound_documents(out_rows, docs, cash):
    """OUTBOUND: SWIFT reference = deal + document number (+ version)."""
    swift_amt = F.col("swift_amount").cast(DecimalType(30, 2))
    cand = F.broadcast(out_rows).join(
        docs,
        (F.length("d_tran") >= FINDUR_MIN_DEAL_DIGITS)
        & F.col("transaction_reference").startswith(F.concat(F.col("d_tran"), F.col("d_doc"))),
    )
    released = (F.col("d_status") == FINDUR_DOC_RELEASED) & (F.col("d_sent") == FINDUR_DOC_SENT)
    cand = cand.withColumn(
        "_valid",
        released
        & (F.col("d_ccy") == F.col("swift_currency_skey"))
        & (F.col("d_doc_net") < 0)
        & (F.abs(F.col("d_doc_net")) == swift_amt)
        & F.datediff(F.col("report_date"), F.col("d_trade_date")).between(0, FINDUR_DOC_LOOKBACK_DAYS),
    ).withColumn("_released", released)
    w = Window.partitionBy(*FX_KEYS)
    cand = (
        cand.withColumn("_n_valid", F.sum(F.col("_valid").cast("int")).over(w))
        .withColumn("_docs", F.array_join(F.array_sort(F.collect_set("d_doc").over(w)), ", "))
    )
    # Value date for the report: the deal's netted cash settlement event 0-7 days after sending.
    vd = cash.where(F.col("f_amount") < 0).select(
        F.col("f_deal").alias("d_tran"), F.col("f_ccy").alias("d_ccy"), "f_value_date")
    hit = cand.where(F.col("_valid") & (F.col("_n_valid") == 1))
    hit = (
        hit.join(vd, ["d_tran", "d_ccy"], "left")
        .withColumn("f_value_date", F.when(
            F.datediff(F.col("f_value_date"), F.col("report_date")).between(0, FINDUR_OUTBOUND_VALUE_DAYS),
            F.col("f_value_date")))
        .groupBy(*FX_KEYS, "d_tran", "d_doc", "d_cnt", "d_doc_net", "d_ccy")
        .agg(F.min("f_value_date").alias("f_value_date"))
    )
    matched = hit.select(
        *FX_KEYS, F.col("d_tran").alias("f_deal"), F.col("d_doc").alias("f_doc"), F.col("d_cnt").alias("f_cnt"),
        F.col("d_doc_net").alias("f_amount"), F.col("d_ccy").alias("f_ccy"), "f_value_date",
        F.lit("DOCUMENT").alias("f_type"), F.lit(None).cast("string").alias("_findur_reason"),
    )
    first = Window.partitionBy(*FX_KEYS).orderBy(F.col("_released").desc(), "d_doc")
    failed = (
        cand.where(F.col("_n_valid") != 1)
        .withColumn("_rn", F.row_number().over(first)).where(F.col("_rn") == 1)
        .select(
            *FX_KEYS,
            F.when(F.col("_n_valid") > 1,
                   F.concat(F.lit(f"{FX_REASON_PREFIX}, multiple Released Findur documents for reference (document "),
                            F.col("_docs"), F.lit("); not matched")))
             .when(~F.coalesce(F.col("_released"), F.lit(False)),
                   F.concat(F.lit(f"{FX_REASON_PREFIX}, Findur document "), F.col("d_doc"), F.lit(" (deal "),
                            F.col("d_tran"), F.lit(") is not Released and sent (status "),
                            F.coalesce(F.col("d_status").cast("string"), F.lit("unknown")), F.lit(", sent flag "),
                            F.coalesce(F.col("d_sent").cast("string"), F.lit("unknown")), F.lit(")")))
             .otherwise(
                   F.concat(F.lit(f"{FX_REASON_PREFIX}, Findur document "), F.col("d_doc"), F.lit(" (deal "),
                            F.col("d_tran"), F.lit(") found but currency, amount or date differs (Findur net "),
                            F.col("d_doc_net").cast("string"), F.lit(")")))
             .alias("_findur_reason"),
        )
    )
    return matched, failed


def match_findur(fx, cash, docs=None):
    """One result row per FX candidate: findur_* columns (when matched) and _findur_reason.

    docs: settlement documents (findur_settlement_documents) or None when they
    cannot be read; outbound then falls back to the cash-event reference match.
    """
    swift_amt = F.col("swift_amount").cast(DecimalType(30, 2))
    out_rows = fx.where(F.col("inbound_outbound_ind") == "OUTBOUND")
    in_rows = fx.where(F.col("inbound_outbound_ind") == "INBOUND")

    # OUTBOUND (fallback, no documents): reference starts with the deal number; then validate.
    ref = F.broadcast(out_rows).join(
        cash,
        (F.length("f_deal") >= FINDUR_MIN_DEAL_DIGITS)
        & F.col("transaction_reference").startswith(F.col("f_deal")),
    )
    ref = ref.withColumn(
        "_valid",
        (F.col("f_ccy") == F.col("swift_currency_skey"))
        & (F.col("f_amount") < 0)
        & (F.abs(F.col("f_amount")) == swift_amt)
        & (F.datediff(F.col("f_value_date"), F.col("report_date")).between(0, FINDUR_OUTBOUND_VALUE_DAYS)),
    )
    w = Window.partitionBy(*FX_KEYS)
    ref = (
        ref.withColumn("_n_valid", F.sum(F.col("_valid").cast("int")).over(w))
        .withColumn("_n_cand", F.count("*").over(w))
        .withColumn("_deals", F.array_join(F.array_sort(F.collect_set("f_deal").over(w)), ", "))
    )
    ref_matched = ref.where(F.col("_valid") & (F.col("_n_valid") == 1)).select(
        *FX_KEYS, "f_deal", F.lit(None).cast("string").alias("f_doc"), "f_cnt", "f_amount", "f_ccy", "f_value_date",
        F.lit("REFERENCE").alias("f_type"), F.lit(None).cast("string").alias("_findur_reason"),
    )
    ref_failed = ref.where(F.col("_n_valid") != 1).groupBy(*FX_KEYS).agg(
        F.first("_n_valid").alias("_n_valid"), F.first("_deals").alias("_deals")
    ).select(
        *FX_KEYS,
        F.when(F.col("_n_valid") > 1,
               F.concat(F.lit(f"{FX_REASON_PREFIX}, multiple Findur records for reference (deal "),
                        F.col("_deals"), F.lit("); not matched")))
         .otherwise(F.concat(F.lit(f"{FX_REASON_PREFIX}, Findur deal "), F.col("_deals"),
                             F.lit(" found but currency, value date or amount differs")))
         .alias("_findur_reason"),
    )

    if docs is not None:
        ref_matched, ref_failed = match_outbound_documents(out_rows, docs, cash)

    # INBOUND: currency + value date + amount, exactly one match.
    amt = F.broadcast(in_rows).join(
        cash,
        (F.col("f_ccy") == F.col("swift_currency_skey"))
        & (F.col("f_value_date") == F.col("report_date"))
        & (F.col("f_amount") > 0)
        & (F.col("f_amount") == swift_amt),
    )
    w_swift = Window.partitionBy(*FX_KEYS)
    w_findur = Window.partitionBy("f_deal", "f_ccy", "f_value_date")
    amt = (
        amt.withColumn("_n_match", F.count("*").over(w_swift))
        .withColumn("_n_claims", F.count("*").over(w_findur))
        .withColumn("_deals", F.array_join(F.array_sort(F.collect_set("f_deal").over(w_swift)), ", "))
    )
    amt_matched = amt.where((F.col("_n_match") == 1) & (F.col("_n_claims") == 1)).select(
        *FX_KEYS, "f_deal", F.lit(None).cast("string").alias("f_doc"), "f_cnt", "f_amount", "f_ccy", "f_value_date",
        F.lit("AMOUNT_DATE").alias("f_type"), F.lit(None).cast("string").alias("_findur_reason"),
    )
    amt_failed = amt.where((F.col("_n_match") > 1) | (F.col("_n_claims") > 1)).groupBy(*FX_KEYS).agg(
        F.first("_deals").alias("_deals")
    ).select(
        *FX_KEYS,
        F.concat(F.lit(f"{FX_REASON_PREFIX}, multiple Findur records with the same currency, date and amount (deal "),
                 F.col("_deals"), F.lit("); not matched")).alias("_findur_reason"),
    )

    matched = ref_matched.unionByName(amt_matched).select(
        *FX_KEYS,
        F.col("f_deal").alias("findur_deal_num"),
        F.col("f_doc").alias("findur_document_num"),
        F.col("f_cnt").alias("findur_transaction_cnt"),
        F.col("f_amount").alias("findur_amount"),
        F.col("f_ccy").alias("findur_currency_skey"),
        F.col("f_value_date").alias("findur_value_date"),
        F.col("f_type").alias("findur_match_type"),
        "_findur_reason",
    )
    failed = _add_null_findur_columns(ref_failed.unionByName(amt_failed)).select(
        *FX_KEYS, *FINDUR_COLUMNS, "_findur_reason")
    found = matched.unionByName(failed)
    # Rows with no Findur record at all.
    none = fx.select(*FX_KEYS).join(found.select(*FX_KEYS), FX_KEYS, "left_anti").withColumn(
        "_findur_reason",
        F.when((F.col("inbound_outbound_ind") == "OUTBOUND") & F.lit(docs is not None),
               F.lit(f"{FX_REASON_PREFIX}, no Findur settlement document for this reference"))
         .when(F.col("inbound_outbound_ind") == "OUTBOUND",
               F.lit(f"{FX_REASON_PREFIX}, no Findur cash settlement for this reference"))
         .otherwise(F.lit(f"{FX_REASON_PREFIX}, no Findur cash settlement with the same currency, date and amount")),
    )
    return found.unionByName(_add_null_findur_columns(none).select(*FX_KEYS, *FINDUR_COLUMNS, "_findur_reason"))


def apply_findur(recon_df, results):
    """Set result, reason and findur_* columns on recon rows from Findur results."""
    r = results.select(*FX_KEYS, *[F.col(c).alias(f"_r_{c}") for c in FINDUR_COLUMNS], "_findur_reason")
    out = _add_null_findur_columns(recon_df).join(r, FX_KEYS, "left")
    matched = F.col("_r_findur_match_type").isNotNull()
    has_result = matched | F.col("_findur_reason").isNotNull()
    for c, t in FINDUR_COLUMNS.items():
        # Cast to the table type (sum() widens decimals; the append would fail otherwise).
        out = out.withColumn(c, F.when(matched, F.col(f"_r_{c}")).otherwise(F.col(c)).cast(t))
    out = (
        out.withColumn("recon_result", F.when(matched, F.lit("Success")).otherwise(F.col("recon_result")))
        .withColumn("recon_result_code", F.when(matched, F.lit("MATCH_FINDUR")).otherwise(F.col("recon_result_code")))
        .withColumn("warning_reason",
                    F.when(matched, F.lit(None).cast("string"))
                     .when(has_result, F.col("_findur_reason"))
                     .otherwise(F.col("warning_reason")))
        .withColumn("recon_result_detail",
                    F.when(F.col("_r_findur_match_type") == "DOCUMENT", F.lit(MATCH_FINDUR_DOC))
                     .when(F.col("_r_findur_match_type") == "REFERENCE", F.lit(MATCH_FINDUR_REF))
                     .when(F.col("_r_findur_match_type") == "AMOUNT_DATE", F.lit(MATCH_FINDUR_AMT))
                     .otherwise(F.col("warning_reason")))
    )
    return out.drop(*[f"_r_{c}" for c in FINDUR_COLUMNS], "_findur_reason")


findur_status = "skipped"
findur_doc_status = "not used"
if FINDUR_ENABLED and _findur_cols_ready:
    fx_rows = recon.where(is_fx_candidate).select(
        *FX_KEYS, "swift_currency_skey", "swift_amount", "swift_transaction_cnt"
    )
    fx_info = fx_rows.agg(
        F.count("*").alias("n"), F.min("report_date").alias("d0"), F.max("report_date").alias("d1"),
        F.collect_set("swift_currency_skey").alias("ccys"),
    ).first()
    if fx_info["n"]:
        try:
            cash = findur_cash_settlements(
                FINDUR_SCHEMA, fx_info["d0"],
                fx_info["d1"] + timedelta(days=FINDUR_OUTBOUND_VALUE_DAYS),
                [int(c) for c in fx_info["ccys"]],
            )
            # Settlement documents (outbound). Failure here is not fatal: outbound
            # falls back to the cash-event reference match.
            docs = None
            findur_doc_status = "not needed (no outbound rows)"
            if fx_rows.where(F.col("inbound_outbound_ind") == "OUTBOUND").limit(1).count():
                try:
                    _d = findur_settlement_documents(
                        FINDUR_DOCUMENT_SCHEMA,
                        fx_info["d0"] - timedelta(days=FINDUR_DOC_LOOKBACK_DAYS), fx_info["d1"],
                        [int(c) for c in fx_info["ccys"]],
                    )
                    docs = spark.createDataFrame(_d.collect(), _d.schema)
                    findur_doc_status = f"read {docs.count()} document row(s) from {FINDUR_DOCUMENT_SCHEMA}"
                except Exception as e:
                    findur_doc_status = ("unavailable, outbound used cash events (" +
                                         str(e).splitlines()[0][:200] + ")")
                    print(f"WARNING: Findur settlement documents could not be read from "
                          f"{FINDUR_DOCUMENT_SCHEMA}; outbound falls back to cash events. {findur_doc_status}")
            print(f"Findur settlement documents: {findur_doc_status}")
            # Collect here (a few rows) so a missing grant fails inside this try
            # instead of later when the recon table is written.
            _res = match_findur(fx_rows, cash, docs)
            findur_results = spark.createDataFrame(_res.collect(), _res.schema)
            recon = apply_findur(recon, findur_results)
            findur_status = "applied"
        except Exception as e:
            msg = str(e).splitlines()[0][:300]
            print(f"WARNING: Findur matching skipped, could not read {FINDUR_SCHEMA} ({msg}). "
                  "Foreign-currency rows stay as warnings.")
            findur_status = "unavailable"
    else:
        findur_status = "no foreign-currency rows"
if _findur_cols_ready:
    recon = _add_null_findur_columns(recon)

findur_matched_count = (
    recon.where(F.col("recon_result_code") == "MATCH_FINDUR").count() if findur_status == "applied" else 0
)
warning_count = recon.where(F.col("recon_result") == "Warning").count()
success_count = recon.where(F.col("recon_result") == "Success").count()
print(f"Findur: {findur_status}; {findur_matched_count} foreign-currency row(s) matched in Findur")
print(f"Reconciliation after Findur: {success_count} Success, {warning_count} Warning(s), "
      f"{out_of_scope_count} Out of scope")

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
recon = recon.withColumn("audit_run_id", F.lit(JOB_RUN_ID).cast("long"))

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
    "out_of_scope": out_of_scope_count,
    "findur_matched": findur_matched_count,
    "findur_status": findur_status,
    "findur_document_status": findur_doc_status,
    "habs_not_refreshed_dates": habs_not_refreshed_dates,
})
dbutils.jobs.taskValues.set(key="recon_result", value=result)
# Downstream tasks use this to select exactly this run's reconciliation rows.
dbutils.jobs.taskValues.set(key="job_run_id", value=str(JOB_RUN_ID or ""))
dbutils.jobs.taskValues.set(key="status", value="PASSED")
print(f"Notebook result: {result}")
dbutils.notebook.exit(result)

