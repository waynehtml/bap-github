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
HABS_FACT_TABLE = f"{CATALOG}.curated_db.tbl_habs_message_fact"
FI_DIM_TABLE = f"{CATALOG}.curated_db.tbl_financial_institution_dim"
GLOBAL_LEGAL_ENTITY_VIEW = f"{CATALOG}.view_db.vwu_global_legal_entity_dim"
MSG_TYPE_DIM = f"{CATALOG}.curated_db.tbl_swift_message_type_dim"
MSG_STATUS_DIM = f"{CATALOG}.curated_db.tbl_swift_message_status_dim"
MSG_TYPE_REF = f"{CATALOG}.curated_db.tbl_swift_message_type_ref"
# Shared currency dimension (same columns as FMBODW.CURRENCY_DIM), owned by Financial Markets.
# Read through FMD's own view (owner tbl_owner_fmd, per Ally 2026-11-12); same
# currency_skey/currency_name as curated_db.tbl_currency_dim. All columns are STRING,
# so the lookup below casts the skey and trims/uppercases the name.
# Needs USE SCHEMA + SELECT on fmbo_unmodelled_views_db for the services SPN.
dbutils.widgets.text("currency_dim_table", f"{_ENV}_financial_markets_cat.fmbo_unmodelled_views_db.vwu_finddw_currency_dim", "Currency dimension")
CURRENCY_DIM_TABLE = dbutils.widgets.get("currency_dim_table")

# --- Widget: report date range ---
dbutils.widgets.text("report_date", "", "Report date (YYYY-MM-DD) to load")
report_date_str = dbutils.widgets.get("report_date")

if report_date_str:
    report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
    print(f"Loading HABS data for report date: {report_date}")
else:
    report_date = None
    print("No report date specified — will load the business dates of this run's files")

# --- Time zone for HABS timestamps ---
# HABS APPLICATION_UPDATE_TIMESTAMP is in Eastern Time (America/Toronto).
# The original ETL used a fixed +5 hours (EST), but October is EDT (UTC-4).
# We interpret the timestamp in America/Toronto and convert to UTC.
HABS_TZ = "America/Toronto"

# --- Job run ID (audit_run_id), shared with 02/04/07 ---
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

print(f"Source: {HABS_SOURCE}")
print(f"Target: {HABS_FACT_TABLE}")
print(f"Job run ID: {JOB_RUN_ID}")

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

# MESSAGE_STATUS_FK is the HABS business code. Maintain the dedicated DVR
# dimension before resolving its surrogate key in the HABS fact.
status_source = (
    habs_raw.where(F.col("MESSAGE_STATUS_FK").isNotNull())
    .select(F.col("MESSAGE_STATUS_FK").cast("long").alias("swift_message_status_code"))
    .distinct()
)
status_source.createOrReplaceTempView("dvr_habs_message_status_source")
spark.sql(f"""
    MERGE INTO {MSG_STATUS_DIM} AS target
    USING dvr_habs_message_status_source AS source
    ON target.swift_message_status_code = source.swift_message_status_code
    WHEN NOT MATCHED THEN INSERT (
      swift_message_status_code,
      swift_message_status_edesc,
      swift_message_status_fdesc
    ) VALUES (
      source.swift_message_status_code,
      CONCAT('HABS message status ', CAST(source.swift_message_status_code AS STRING)),
      NULL
    )
""")

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
extract_counterparty_udf = F.udf(lambda c: extract_bic_from_field(c, '57A'), StringType())
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
    F.lit(JOB_RUN_ID).cast("long").alias("audit_run_id"),
    # Transaction date = AUDIT_CREATION_DATE
    F.to_date("AUDIT_CREATION_DATE").alias("trans_date_id"),
    # UTC date: interpret the ET timestamp, convert to UTC, then extract the date.
    F.to_date(
        F.to_utc_timestamp(F.col("APPLICATION_UPDATE_TIMESTAMP"), HABS_TZ)
    ).alias("trans_utc_date_id"),
    F.col("APPLICATION_UPDATE_TIMESTAMP").alias("application_update_ts"),
    F.lit(None).cast("long").alias("swift_message_type_skey"),
    F.col("MESSAGE_TYPE_FK").cast("string").alias("habs_swift_message_code"),
    # MX payments: pacs.008 -> MT103, pacs.009 -> MT202 (matches the SWIFT DVR file).
    # MT messages: type from CLOB Block 2.
    F.when(F.col("_is_mx_payment"), mx_to_mt[F.col("_mx_family")])
     .otherwise(extract_mt_type_udf("MESSAGE_CONTENT_CLOB")).alias("swift_gen_message_type"),
    # pacs family (pacs.008 / pacs.009) for the message type key; null for MT messages.
    F.when(F.col("_is_mx_payment"), F.col("_mx_family")).alias("_mx_key_name"),
    F.col("MESSAGE_STATUS_FK").cast("long").alias("_swift_message_status_code"),
    F.lit(None).cast("long").alias("currency_skey"),
    # Currency: IntrBkSttlmAmt Ccy for MX payments; :32A: currency for MT.
    F.when(F.col("_is_mx_payment"),
           F.regexp_extract("_xml", r'<(?:\w+:)?IntrBkSttlmAmt[^>]*Ccy="([A-Z]{3})"', 1))
     .otherwise(extract_currency_udf("MESSAGE_CONTENT_CLOB")).alias("_currency_code"),
    F.lit(None).cast("long").alias("originating_fi_skey"),
    F.lit(None).cast("decimal(21,0)").alias("originating_client_gle_skey"),
    F.lit(None).cast("long").alias("counterparty_fi_skey"),
    F.lit(None).cast("decimal(21,0)").alias("counterparty_client_gle_skey"),
    F.lit(None).cast("long").alias("beneficiary_fi_skey"),
    F.lit(None).cast("decimal(21,0)").alias("beneficiary_client_gle_skey"),
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
    # BIC from the XML AppHdr is 11 chars (e.g. PWGSXXW2XXX); the FI dim stores
    # 8-char BIC8, so truncate before the lookup.  MT UDFs already return 8 chars.
    F.when(F.col("_is_mx_payment"), F.col("_from_bic").substr(1, 8)).otherwise(extract_sender_udf("MESSAGE_CONTENT_CLOB")).alias("_originating_bic8"),
    F.when(F.col("_is_mx_payment"), F.col("_to_bic").substr(1, 8)).otherwise(extract_counterparty_udf("MESSAGE_CONTENT_CLOB")).alias("_counterparty_bic8"),
    F.when(F.col("_is_mx_payment"), F.lit(None).cast("string")).otherwise(extract_beneficiary_udf("MESSAGE_CONTENT_CLOB")).alias("_beneficiary_bic8"),
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

from pyspark.sql import Window

_fi_window = Window.partitionBy("bic8").orderBy(F.col("financial_institution_skey").desc())
fi_dim = (
    spark.table(FI_DIM_TABLE)
    .where((F.col("md_current_ind") == 1) & F.col("bic8").isNotNull())
    .select("bic8", "client_id", "financial_institution_skey")
    .withColumn("_rn", F.row_number().over(_fi_window))
    .where(F.col("_rn") == 1)
    .drop("_rn")
)
_gle_window = Window.partitionBy("client_id").orderBy(F.col("global_legal_entity_skey").desc())
gle_dim = (
    spark.table(GLOBAL_LEGAL_ENTITY_VIEW)
    .where(
        F.col("client_id").isNotNull()
        & F.col("global_legal_entity_skey").isNotNull()
        & (F.col("global_legal_entity_skey") > 0)
    )
    .select("client_id", "global_legal_entity_skey")
    .withColumn("_rn", F.row_number().over(_gle_window))
    .where(F.col("_rn") == 1)
    .drop("_rn")
)
# FMBODW.SWIFT_MESSAGE_TYPE_DIM: SWIFT_MESSAGE_TYPE_SKEY + SWIFT_GEN_MESSAGE_TYPE.
msg_type_dim = spark.table(MSG_TYPE_DIM).select(
    F.col("swift_gen_message_type").alias("_lookup_swift_gen_message_type"),
    F.col("swift_message_type_skey").cast("long").alias("_lookup_swift_message_type_skey"),
)
# FMBODW keys pacs messages by their ISO 20022 name (pacs.008 = 21, pacs.009 = 22,
# pacs.009COV = 23; confirmed in PROD FMBODW.SWIFT_MESSAGE_FACT, 2026-11-09).
# The REF table maps HABS MESSAGE_TYPE_FK (e.g. 12066 pacs.009COVi) to that name;
# otherwise use the pacs family from the XML. swift_gen_message_type stays MT for the match.
msg_type_ref = (
    spark.table(MSG_TYPE_REF)
    .where(F.col("swift_gen_message_type").startswith("pacs"))
    .select(
        F.col("swift_message_type").cast("string").alias("_ref_code"),
        F.col("swift_gen_message_type").alias("_ref_gen_type"),
    )
)
# Currency code -> CURRENCY_SKEY (USD has skey 0; only a missing match becomes -1).
currency_dim = spark.table(CURRENCY_DIM_TABLE).select(
    F.upper(F.trim(F.col("currency_name"))).alias("_lookup_currency_name"),
    F.col("currency_skey").cast("long").alias("_lookup_currency_skey"),
)
# Key types in tbl_habs_message_fact: *_fi_skey BIGINT (FI dim key is DECIMAL(12,0))
# and *_client_gle_skey DECIMAL(21,0) (GLE view key is BIGINT). Cast explicitly:
# the job runtime (DBR 16.4) rejects implicit type changes on append
# (DELTA_FAILED_TO_MERGE_FIELDS).
FI_SKEY_TYPE = "bigint"
GLE_SKEY_TYPE = "decimal(21,0)"
msg_status_dim = spark.table(MSG_STATUS_DIM).select(
    "swift_message_status_code",
    F.col("swift_message_status_skey").alias("_lookup_swift_message_status_skey"),
)

habs_dvr = (
    habs_dvr
    .join(msg_type_ref, F.col("habs_swift_message_code") == F.col("_ref_code"), "left")
    .withColumn(
        "_type_key_name",
        F.when(F.col("_mx_key_name").isNotNull(), F.coalesce(F.col("_ref_gen_type"), F.col("_mx_key_name")))
         .otherwise(F.col("swift_gen_message_type")),
    )
    .join(msg_type_dim, F.col("_type_key_name") == F.col("_lookup_swift_gen_message_type"), "left")
    .withColumn("swift_message_type_skey", F.coalesce(F.col("_lookup_swift_message_type_skey"), F.lit(-1)))
    .drop("_lookup_swift_gen_message_type", "_lookup_swift_message_type_skey",
          "_ref_code", "_ref_gen_type", "_type_key_name", "_mx_key_name")
    .join(currency_dim, F.upper(F.trim(F.col("_currency_code"))) == F.col("_lookup_currency_name"), "left")
    .withColumn("currency_skey", F.coalesce(F.col("_lookup_currency_skey"), F.lit(-1)))
    .drop("_lookup_currency_name", "_lookup_currency_skey", "_currency_code")
    .join(
        msg_status_dim,
        F.col("_swift_message_status_code") == F.col("swift_message_status_code"),
        "left",
    )
    .withColumn("swift_message_status_skey", F.coalesce(F.col("_lookup_swift_message_status_skey"), F.lit(-1)))
    .drop("swift_message_status_code", "_lookup_swift_message_status_skey", "_swift_message_status_code")
    .join(fi_dim.alias("orig"), F.col("_originating_bic8") == F.col("orig.bic8"), "left")
    .join(gle_dim.alias("orig_gle"), F.col("orig.client_id") == F.col("orig_gle.client_id"), "left")
    .withColumn("originating_fi_skey", F.coalesce(F.col("orig.financial_institution_skey"), F.lit(-1)).cast(FI_SKEY_TYPE))
    .withColumn("originating_client_gle_skey", F.coalesce(F.col("orig_gle.global_legal_entity_skey"), F.lit(-1)).cast(GLE_SKEY_TYPE))
    # Drop the joined dim columns as Column objects: a string like "orig.bic8" is
    # treated as a literal column name, matches nothing, and leaves duplicate
    # bic8/client_id/... columns (DELTA_DUPLICATE_COLUMNS_FOUND on write).
    .drop(*[F.col(c) for c in ("orig.bic8", "orig.client_id", "orig.financial_institution_skey",
                               "orig_gle.client_id", "orig_gle.global_legal_entity_skey")])
    .join(fi_dim.alias("cpty"), F.col("_counterparty_bic8") == F.col("cpty.bic8"), "left")
    .join(gle_dim.alias("cpty_gle"), F.col("cpty.client_id") == F.col("cpty_gle.client_id"), "left")
    .withColumn("counterparty_fi_skey", F.coalesce(F.col("cpty.financial_institution_skey"), F.lit(-1)).cast(FI_SKEY_TYPE))
    .withColumn("counterparty_client_gle_skey", F.coalesce(F.col("cpty_gle.global_legal_entity_skey"), F.lit(-1)).cast(GLE_SKEY_TYPE))
    .drop(*[F.col(c) for c in ("cpty.bic8", "cpty.client_id", "cpty.financial_institution_skey",
                               "cpty_gle.client_id", "cpty_gle.global_legal_entity_skey")])
    .join(fi_dim.alias("bene"), F.col("_beneficiary_bic8") == F.col("bene.bic8"), "left")
    .join(gle_dim.alias("bene_gle"), F.col("bene.client_id") == F.col("bene_gle.client_id"), "left")
    .withColumn("beneficiary_fi_skey", F.coalesce(F.col("bene.financial_institution_skey"), F.lit(-1)).cast(FI_SKEY_TYPE))
    .withColumn("beneficiary_client_gle_skey", F.coalesce(F.col("bene_gle.global_legal_entity_skey"), F.lit(-1)).cast(GLE_SKEY_TYPE))
    .drop(*[F.col(c) for c in ("bene.bic8", "bene.client_id", "bene.financial_institution_skey",
                               "bene_gle.client_id", "bene_gle.global_legal_entity_skey")])
    # Sender BIC8, kept so 04_reconcile can mark internal senders (Receiver
    # General via Viagate, PWGSXXW2) as out of scope. Needs release-2.1.0.
    .withColumn("habs_sender_bic", F.upper(F.trim(F.col("_originating_bic8"))))
    .drop("_originating_bic8", "_counterparty_bic8", "_beneficiary_bic8")
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
    # --- Scope DB read by reference, not by value-date window ---
    # The old ±1 day window on business_value_dt missed future-dated payments
    # (e.g. value date 29 Oct for business date 13 Oct).  Instead, join to
    # the CLOB messages already loaded: every CLOB row has a SRC_REFERENCE_NUM
    # that links to the curated payment table.  This is a semi-join, so the
    # scan stays bounded to the references in this run.
    message_refs = habs_raw.select(
        F.col("MESSAGE_PK").cast("long").alias("source_message_pk"),
        F.trim(F.col("SRC_REFERENCE_NUM")).alias("src_reference_num"),
    ).where(F.col("src_reference_num").isNotNull() & (F.col("src_reference_num") != "NONREF"))

    # Distinct references to scope the DB read (broadcast-friendly).
    ref_list = message_refs.select("src_reference_num").distinct()

    payments = (
        spark.table(HABS_DB_SOURCE)
        .where(F.col("src_reference_num").isNotNull())
        .withColumn("src_reference_num", F.trim(F.col("src_reference_num")))
        .join(F.broadcast(ref_list), "src_reference_num")
        .groupBy("src_reference_num")
        .agg(
            F.sum("business_value_amt").cast("decimal(20,2)").alias("db_amount"),
            F.max("application_update_ts").alias("db_application_update_ts"),
        )
    )

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

# habs_sender_bic is added by data_release release-2.1.0. If that release
# has not run yet in this environment, load without it instead of failing.
if "habs_sender_bic" not in spark.table(HABS_FACT_TABLE).columns:
    print("WARNING: habs_sender_bic not in the HABS fact table (run BAP-DATA-RELEASE-DEPLOYMENT "
          "release-2.1.0); internal-sender rows will not be marked out of scope.")
    habs_dvr = habs_dvr.drop("habs_sender_bic")

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

