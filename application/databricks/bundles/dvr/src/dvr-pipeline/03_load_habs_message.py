# Databricks notebook source
# DBTITLE 1,Load HABS Message Data
# MAGIC %md
# MAGIC # Load HABS Message Data (03)
# MAGIC
# MAGIC Extracts SWIFT-related messages from the existing BAP raw HABS table, parses message fields from CLOB content, converts to UTC, and loads into `tbl_habs_message_fact` for DVR reconciliation. SMM ingestion is deferred from the DVR first release.

# COMMAND ----------

# DBTITLE 1,Configuration
import json
from datetime import datetime, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

# --- Runtime parameters and source/target tables ---
# Job parameters; interactive runs default to this workspace's env.
_ENV = {"adb-1700301391505163": "dev", "adb-13344226264609": "stg", "adb-642333651898149": "prd"}.get(
    spark.conf.get("spark.databricks.workspaceUrl", "").split(".")[0], "dev")
dbutils.widgets.text("catalog", f"{_ENV}_banking_and_payments_cat", "BAP catalog")
dbutils.widgets.text("habs_catalog", f"{_ENV}_ext_ora_habs", "HABS foreign catalog")
dbutils.widgets.text("habs_source_table", f"{_ENV}_banking_and_payments_cat.raw_db.habs_habs_message", "HABS source table")
CATALOG = dbutils.widgets.get("catalog")
HABS_CATALOG = dbutils.widgets.get("habs_catalog")
HABS_SOURCE = dbutils.widgets.get("habs_source_table") or f"{CATALOG}.raw_db.habs_habs_message"
HABS_FACT_TABLE = f"{CATALOG}.derived_db.tbl_habs_message_fact"
FI_DIM_TABLE = f"{CATALOG}.curated_db.tbl_financial_institution_dim"
MSG_TYPE_DIM = f"{CATALOG}.curated_db.tbl_bo_swift_msg_type_dim"

# --- Widget: report date range ---
dbutils.widgets.text("report_date", "", "Report date (YYYY-MM-DD) to load")
report_date_str = dbutils.widgets.get("report_date")

if report_date_str:
    report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
    print(f"Loading HABS data for report date: {report_date}")
else:
    report_date = None
    print("No report date specified — will load the business dates of this run's files")

# --- EST to UTC offset (5 hours per ETL spec) ---
UTC_OFFSET_HOURS = 5

print(f"Source: {HABS_SOURCE}")
print(f"Target: {HABS_FACT_TABLE}")

# COMMAND ----------

# DBTITLE 1,Extract SWIFT messages from HABS
# Read HABS messages filtered to Swift service. The BAP raw table is populated
# from the environment-specific HABS foreign catalog; no direct Oracle
# connection is required by this notebook.
# The CLOB contains raw SWIFT MT messages we need to parse
habs_raw = spark.table(HABS_SOURCE).where(
    F.col("HABS_MESSAGE_SERVICE_NAME") == "Swift"
)

# --- Business dates to load ---
# Load HABS for the SWIFT business dates of the files validated in this run.
# A window relative to today missed late uploads and anything after a weekend
# or holiday, so every row came out as a warning.
business_dates = []
if report_date:
    business_dates = [report_date]
else:
    try:
        run_files_json = dbutils.jobs.taskValues.get(
            taskKey="validate_swift_files", key="valid_files_json", debugValue=""
        ) or ""
    except Exception:
        run_files_json = ""
    run_files = json.loads(run_files_json) if run_files_json else []
    business_dates = sorted({
        datetime.strptime(f["file_date"], "%Y-%m-%d").date()
        for f in run_files if f.get("file_date")
    })

if business_dates:
    # APPLICATION_UPDATE_TIMESTAMP is local (EST); the UTC business date can fall
    # on the local day before or after, so include one day either side.
    load_dates = sorted({
        str(d + timedelta(days=offset)) for d in business_dates for offset in (-1, 0, 1)
    })
    habs_raw = habs_raw.where(
        F.to_date(F.col("APPLICATION_UPDATE_TIMESTAMP")).isin(load_dates)
    )
    print(f"Loading HABS for business date(s) {[str(d) for d in business_dates]} (local dates {load_dates})")
else:
    # Interactive run with no files and no report_date: recent data only.
    cutoff = datetime.now() - timedelta(days=7)
    habs_raw = habs_raw.where(
        F.col("APPLICATION_UPDATE_TIMESTAMP") >= F.lit(cutoff)
    )
    print("No business dates from validate task or report_date — loading the last 7 days")

print(f"HABS Swift messages to process: {habs_raw.count()}")
habs_raw.select("MESSAGE_PK", "MESSAGE_TYPE_FK", "MESSAGE_STATUS_FK",
                "APPLICATION_UPDATE_TIMESTAMP", "PARTY_REFERENCE", "VALUE_AMT").show(5, truncate=False)

# COMMAND ----------

# DBTITLE 1,Check HABS has been refreshed for the business dates
# --- HABS freshness check ---
# BAP-HABS-WORKPACKAGE1 loads raw_db.habs_habs_message once a day (21:00 ET).
# If it has not run yet for a file's business date, every SWIFT row would come
# back as "missing in HABS". Flag those dates so reconcile, the email and the
# app can say "HABS not refreshed yet" instead.
habs_not_refreshed_dates = []
latest_habs_ts = None
if business_dates:
    latest_habs_ts = (
        spark.table(HABS_SOURCE)
        .where(F.col("HABS_MESSAGE_SERVICE_NAME") == "Swift")
        .agg(F.max("APPLICATION_UPDATE_TIMESTAMP").alias("latest"))
        .first()
        .latest
    )
    latest_habs_date = latest_habs_ts.date() if latest_habs_ts else None
    habs_not_refreshed_dates = [
        str(d) for d in business_dates if latest_habs_date is None or latest_habs_date < d
    ]

print(f"Latest HABS Swift message: {latest_habs_ts}")
if habs_not_refreshed_dates:
    print(f"HABS not refreshed yet for business date(s): {habs_not_refreshed_dates}")
dbutils.jobs.taskValues.set(key="habs_not_refreshed_dates", value=json.dumps(habs_not_refreshed_dates))

# COMMAND ----------

# DBTITLE 1,CLOB parsing UDFs for MT message fields
import re

# ---------------------------------------------------------------------------
# UDFs to parse SWIFT MT message fields from HABS CLOB
# SWIFT message format: {1:basic_header}{2:app_header}{3:user_header}{4:\n:field:value\n...}{5:trailer}
# ---------------------------------------------------------------------------

def extract_mt_type_from_clob(clob: str) -> str:
    """Extract message type from Block 2 of SWIFT message.
    Block 2 format: {2:I103BCANCAW0XXXXN} -> MT103
    Or: {2:O1030815BCANCAW0AXXX...} -> MT103
    """
    if not clob:
        return None
    m = re.search(r'\{2:[IO](\d{3})', clob)
    if m:
        return f"MT{m.group(1)}"
    return None

def extract_field(clob: str, tag: str) -> str:
    """Extract a field value from Block 4 by tag number.
    e.g., tag='20' extracts from ':20:value'
    """
    if not clob:
        return None
    pattern = rf':{tag}:([^\r\n:]+)'
    m = re.search(pattern, clob)
    if m:
        return m.group(1).strip()
    return None

def extract_amount_from_32a(clob: str) -> float:
    """Extract amount from field :32A: (Value Date/Currency/Amount).
    Format: :32A:YYMMDDCCCAMOUNT, (comma = decimal)
    """
    if not clob:
        return None
    m = re.search(r':32[AB]:\d{6}[A-Z]{3}([\d,]+)', clob)
    if m:
        return float(m.group(1).replace(',', '.'))
    # Try :32B: format (no date)
    m = re.search(r':32B:[A-Z]{3}([\d,]+)', clob)
    if m:
        return float(m.group(1).replace(',', '.'))
    return None

def extract_currency_from_32a(clob: str) -> str:
    """Extract currency from field :32A:."""
    if not clob:
        return None
    m = re.search(r':32[AB]:\d{6}([A-Z]{3})', clob)
    if m:
        return m.group(1)
    m = re.search(r':32B:([A-Z]{3})', clob)
    if m:
        return m.group(1)
    return None

def extract_bic_from_field(clob: str, tag: str) -> str:
    """Extract BIC8 from a tag like :52A:, :57A:, :58A:, :59A:.
    May have /account\nBIC or just BIC.
    """
    if not clob:
        return None
    # Find the field block
    pattern = rf':{tag}:([^{{}}]+?)(?=\r?\n:|\r?\n-|$)'
    m = re.search(pattern, clob, re.DOTALL)
    if not m:
        return None
    field_content = m.group(1).strip()
    lines = [l.strip() for l in field_content.split('\n') if l.strip()]
    for line in lines:
        # Skip lines starting with / (account numbers)
        if line.startswith('/'):
            continue
        # BIC is typically 8 or 11 chars, all alphanumeric
        bic_match = re.match(r'^([A-Z0-9]{8,11})$', line)
        if bic_match:
            return bic_match.group(1)[:8]  # Return BIC8
    return None

def extract_sender_bic(clob: str) -> str:
    """Extract sender BIC from Block 2 (positions vary by I/O type)."""
    if not clob:
        return None
    # Output message: {2:O103...SENDERBICXXXX...}
    m = re.search(r'\{2:O\d{3}\d{4}([A-Z0-9]{8,12})', clob)
    if m:
        return m.group(1)[:8]
    # Input message: {2:I103RECEIVERBIC...}
    m = re.search(r'\{2:I\d{3}([A-Z0-9]{8,12})', clob)
    if m:
        return m.group(1)[:8]
    return None

# Register UDFs
extract_mt_type_udf = F.udf(extract_mt_type_from_clob, StringType())
extract_txn_ref_udf = F.udf(lambda c: extract_field(c, '20'), StringType())
extract_amount_udf = F.udf(extract_amount_from_32a, "double")
extract_currency_udf = F.udf(extract_currency_from_32a, StringType())
extract_originator_udf = F.udf(lambda c: extract_bic_from_field(c, '52A'), StringType())
extract_beneficiary_udf = F.udf(lambda c: extract_bic_from_field(c, '59A') or extract_bic_from_field(c, '58A'), StringType())
extract_sender_udf = F.udf(extract_sender_bic, StringType())

print("CLOB parsing UDFs registered.")

# COMMAND ----------

# DBTITLE 1,Transform HABS data for fact table
# Parse HABS messages and build the HABS message fact.
#
# Production HABS stores SWIFT payments as ISO 20022 (CBPR+) XML, not MT text
# (confirmed with read-only prod queries, 2026-10-23):
#   pacs.009 inbound  (MESSAGE_TYPE_FK 11966) -> MT202, To BIC = BCANCAW2
#   pacs.008 inbound  (MESSAGE_TYPE_FK 11866) -> MT103
#   pacs.009 outbound (MESSAGE_TYPE_FK 12016) -> MT202, From BIC = BCANCAW2
#   pacs.008 outbound (MESSAGE_TYPE_FK 11916) -> MT103, From BIC = BCANCAW2
# Messages are selected by MsgDefIdr (not by FK), so all four are picked up.
#   InstrId = SWIFT DVR "Transaction Reference"; VALUE_AMT = amount.
# camt.053/camt.054 (statements, Lynx Balances) and MT900/910/950/199
# confirmations repeat the same payments, so they are excluded from the recon.
BOC_BIC8 = "BCANCAW2"
MX_TO_MT = {"pacs.008": "MT103", "pacs.009": "MT202"}

# The XML sits in MESSAGE_CONTENT_XML and is often repeated in the CLOB.
xml_col = F.coalesce(
    F.col("MESSAGE_CONTENT_XML"),
    F.when(F.ltrim(F.col("MESSAGE_CONTENT_CLOB")).startswith("<"), F.col("MESSAGE_CONTENT_CLOB")),
)
habs_raw = (
    habs_raw
    .withColumn("_xml", xml_col)
    .withColumn("_msg_def", F.regexp_extract("_xml", r"<(?:\w+:)?MsgDefIdr>([^<]+)<", 1))
    .withColumn("_from_bic", F.regexp_extract("_xml", r"(?s)<(?:\w+:)?Fr>.*?<(?:\w+:)?BICFI>([^<]+)<", 1))
    .withColumn("_to_bic", F.regexp_extract("_xml", r"(?s)<(?:\w+:)?To>.*?<(?:\w+:)?BICFI>([^<]+)<", 1))
    .withColumn("_instr_id", F.trim(F.regexp_extract("_xml", r"<(?:\w+:)?InstrId>([^<]+)<", 1)))
    .withColumn("_mx_family", F.regexp_extract("_msg_def", r"^(pacs\.00[89])", 1))
    .withColumn("_is_mx_payment", F.col("_mx_family") != "")
)
mx_to_mt = F.create_map(*[F.lit(x) for kv in MX_TO_MT.items() for x in kv])

habs_parsed = habs_raw.select(
    F.lit(None).cast("long").alias("habs_message_fact_skey"),
    F.lit(None).cast("long").alias("md_workflow_execution_skey"),
    # Transaction date = AUDIT_CREATION_DATE
    F.to_date("AUDIT_CREATION_DATE").alias("trans_date_id"),
    # UTC date = APPLICATION_UPDATE_TIMESTAMP + 5 hours (EST to UTC per ETL spec)
    F.to_date(
        F.col("APPLICATION_UPDATE_TIMESTAMP") + F.expr(f"INTERVAL {UTC_OFFSET_HOURS} HOURS")
    ).alias("trans_utc_date_id"),
    F.col("APPLICATION_UPDATE_TIMESTAMP").alias("application_update_ts"),
    F.lit(None).cast("long").alias("swift_message_type_skey"),
    F.col("MESSAGE_TYPE_FK").cast("string").alias("habs_swift_message_code"),
    # MX payments: pacs.008 -> MT103, pacs.009 -> MT202 (matches the SWIFT DVR file).
    # MT messages: type from CLOB Block 2.
    F.when(F.col("_is_mx_payment"), mx_to_mt[F.col("_mx_family")])
     .otherwise(extract_mt_type_udf("MESSAGE_CONTENT_CLOB")).alias("swift_gen_message_type"),
    F.col("MESSAGE_STATUS_FK").cast("long").alias("swift_message_status_skey"),
    F.lit(None).cast("long").alias("currency_skey"),
    F.lit(None).cast("long").alias("originating_fi_skey"),
    F.lit(None).cast("long").alias("counterparty_fi_skey"),
    F.lit(None).cast("long").alias("beneficiary_fi_skey"),
    # Transaction reference: XML InstrId for MX payments, :20: for MT
    F.when(F.col("_is_mx_payment"), F.col("_instr_id"))
     .otherwise(extract_txn_ref_udf("MESSAGE_CONTENT_CLOB")).alias("transaction_reference"),
    # Amount: VALUE_AMT for MX payments; :32A: (or VALUE_AMT) for MT
    F.when(F.col("_is_mx_payment"), F.col("VALUE_AMT").cast("double"))
     .otherwise(F.coalesce(extract_amount_udf("MESSAGE_CONTENT_CLOB"), F.col("VALUE_AMT").cast("double")))
     .cast("decimal(20,2)").alias("amount"),
    F.lit(None).cast("decimal(20,2)").alias("amount_cad"),
    # Direction. MX: sent by the Bank (From BIC = BCANCAW2) = outbound, else inbound.
    # MT: Block 2 I = Input (outbound), O = Output (inbound).
    F.when(F.col("_is_mx_payment"),
           F.when(F.col("_from_bic").startswith(BOC_BIC8), F.lit(1)).otherwise(F.lit(0)))
     .when(F.col("MESSAGE_CONTENT_CLOB").rlike(r"\{2:O"), F.lit(0))
     .otherwise(F.lit(1)).alias("habs_outgoing_message_ind"),
    F.lit(0).alias("relational_table_ind"),  # CLOB source
    F.col("MESSAGE_PK").cast("long").alias("source_message_pk"),
    F.current_timestamp().alias("audit_create_ts"),
    F.current_timestamp().alias("audit_last_update_ts"),
)

# Keep payment messages only: MX pacs.008/pacs.009 with a reference and amount,
# or MT103/202/205. Statements and confirmations (camt.053/054, MT900/910/950,
# MT199) repeat the same payments and would double-count in the recon.
habs_dvr = habs_parsed.where(
    F.col("swift_gen_message_type").rlike("^MT(103|202|205)")
    & F.col("transaction_reference").isNotNull()
    & (F.col("transaction_reference") != "")
    & F.col("amount").isNotNull()
)

print(f"HABS DVR messages after filtering: {habs_dvr.count()}")
habs_dvr.groupBy("swift_gen_message_type", "habs_outgoing_message_ind").count().show()

# COMMAND ----------

# DBTITLE 1,Add HABS DB (curated payment) rows for three-way recon
# --- HABS DB side: curated payment business transactions ---
# Three-way recon compares SWIFT vs HABS message (raw_db) vs HABS DB (curated_db).
# Confirmed with read-only prod queries (2026-10-26, business date 2026-10-08):
#   curated src_reference_num = raw message SRC_REFERENCE_NUM for 783 of 786
#   SWIFT payments, one curated row per reference, business_value_amt equal.
#   rk_message_pk is -1 (unknown) and bo_payment_direction_skey mixes 25/28
#   within one direction, so neither is used; reference, MT type and direction
#   come from the linked HABS message.
dbutils.widgets.text(
    "habs_db_source_table", f"{CATALOG}.curated_db.tbl_bo_payment_bus_trans_fact",
    "HABS DB (curated payment) table",
)
HABS_DB_SOURCE = dbutils.widgets.get("habs_db_source_table") or f"{CATALOG}.curated_db.tbl_bo_payment_bus_trans_fact"

habs_db_rows = None
try:
    payments = spark.table(HABS_DB_SOURCE)
    if business_dates:
        db_from = min(business_dates) - timedelta(days=1)
        db_to = max(business_dates) + timedelta(days=2)
        payments = payments.where(
            (F.col("business_value_dt") >= F.lit(str(db_from)))
            & (F.col("business_value_dt") < F.lit(str(db_to)))
        )
    payments = (
        payments.where(F.col("src_reference_num").isNotNull())
        .groupBy("src_reference_num")
        .agg(
            F.sum("business_value_amt").cast("decimal(20,2)").alias("db_amount"),
            F.max("application_update_ts").alias("db_application_update_ts"),
        )
    )
    # Link each HABS payment message (already parsed above) to its curated row.
    message_refs = habs_raw.select(
        F.col("MESSAGE_PK").cast("long").alias("source_message_pk"),
        F.trim(F.col("SRC_REFERENCE_NUM")).alias("src_reference_num"),
    ).where(F.col("src_reference_num").isNotNull() & (F.col("src_reference_num") != "NONREF"))

    habs_db_rows = (
        habs_dvr.where(F.col("relational_table_ind") == 0)
        .join(message_refs, "source_message_pk")
        .join(payments, "src_reference_num")
        .withColumn("amount", F.col("db_amount"))
        .withColumn("application_update_ts", F.coalesce("db_application_update_ts", "application_update_ts"))
        .withColumn("relational_table_ind", F.lit(1))  # DB (relational) source
        .select(*habs_dvr.columns)
    )
    db_count = habs_db_rows.count()
    print(f"HABS DB rows linked from {HABS_DB_SOURCE}: {db_count}")
    if db_count:
        habs_dvr = habs_dvr.unionByName(habs_db_rows)
except Exception as e:
    # Missing or unreadable curated table: keep the two-way SWIFT vs message recon.
    print(f"HABS DB source unavailable ({e.__class__.__name__}); using two-way recon only.")
    habs_db_rows = None

# COMMAND ----------

# DBTITLE 1,Write to HABS fact table
from delta.tables import DeltaTable

HABS_KEYS = ["source_message_pk", "relational_table_ind", "swift_gen_message_type"]

if habs_dvr.count() > 0:
    # The load window overlaps between runs, so replace messages already in the
    # fact table instead of appending them again (duplicates inflated recon counts).
    habs_dvr = habs_dvr.dropDuplicates(HABS_KEYS)
    (
        DeltaTable.forName(spark, HABS_FACT_TABLE).alias("t")
        .merge(
            habs_dvr.select(*HABS_KEYS).alias("s"),
            " AND ".join(f"t.{k} <=> s.{k}" for k in HABS_KEYS),
        )
        .whenMatchedDelete()
        .execute()
    )
    habs_dvr.write.mode("append").saveAsTable(HABS_FACT_TABLE)
    row_count = habs_dvr.count()
    print(f"Wrote {row_count} row(s) to {HABS_FACT_TABLE}")
    display(habs_dvr.limit(5))
else:
    print("No HABS DVR messages to load.")

# COMMAND ----------

# DBTITLE 1,Notebook exit
result = json.dumps({
    "habs_messages_loaded": habs_dvr.where(F.col("relational_table_ind") == 0).count() if habs_dvr else 0,
    "habs_db_rows_loaded": habs_dvr.where(F.col("relational_table_ind") == 1).count() if habs_dvr else 0,
    "business_dates": [str(d) for d in business_dates] or "last_7_days",
    "habs_not_refreshed_dates": habs_not_refreshed_dates,
    "latest_habs_message_ts": str(latest_habs_ts) if latest_habs_ts else None,
})
print(f"Notebook result: {result}")
dbutils.jobs.taskValues.set(key="status", value="PASSED")
dbutils.notebook.exit(result)
