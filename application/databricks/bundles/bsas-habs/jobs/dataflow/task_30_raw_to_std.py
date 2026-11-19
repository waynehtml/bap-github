# Databricks notebook source
# /// script
# [tool.databricks.environment]
# base_environment = "workspace-base-environments/oeds-standard-v6c"
# environment_version = "6"
# ///
# MAGIC %run ../../common

# COMMAND ----------

from functools import reduce
from pyspark.sql import functions as F
from datetime import date, datetime, timezone
import logging

# DataKit library imports
from oeds.core.df_utils import normalize_column_names, normalize_nulls, select_columns
from oeds.core.df_validator import Rules, validate_df
from oeds.core.file_reader import load_file_failfast
from oeds.core.uc_utils import delta_batch_update
from pyspark.sql import DataFrame
from pyspark.sql.types import StructType
from pyspark.errors import AnalysisException

# COMMAND ----------

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")
job_run_id = job_ctx["job_run_id"]

# COMMAND ----------

# DBTITLE 1,Function: load SAA XML file
def load_bsas_xml_file(in_path_to_file: str) -> DataFrame:
    """Load an XML file into a Spark DataFrame.
    The file is expected to be in the format of a single root element with
    multiple child elements, each representing a record. The function returns
    a DataFrame with one record per row.

    If the file is not valid XML or has no <Message> element (e.g. content "test"),
    Spark raises UNABLE_TO_INFER_SCHEMA; an empty DataFrame is returned instead."""
    try:
        df_file = (
        spark.read.format("xml")
        .option("rowTag", "G_RECORD")
        .option("encoding", "ISO-8859-1")
        .option("ignoreSurroundingSpaces", "false")  # keep CLOB content exactly as in file
        .load(in_path_to_file)
        )
        df_file.schema  # force schema inference here (Spark Connect is lazy)
    except AnalysisException as e:
        if "UNABLE_TO_INFER_SCHEMA" not in str(e):
            raise
        logger.warning(f"Invalid XML file (no <Message> records), returning empty DataFrame: {in_path_to_file}")
        df_file = spark.createDataFrame([], StructType([]))
    return df_file

# COMMAND ----------

# DBTITLE 1,Function: insert tbl_batch_id_control
def insert_batch_id_control(in_tbl_batch_id_control: str, in_audit_load_id: int) -> int:
    """Insert a row into tbl_batch_id_control and return its next_batch_id.

    next_batch_id is a plain INT column, so the new value is computed as
    max(next_batch_id) + 1 (1 when no batch id exists yet) before inserting.
    """
    next_batch_id = spark.sql(
        f"SELECT max(next_batch_id) as next_batch_id FROM {in_tbl_batch_id_control}"
    ).first()[0]
    
    if next_batch_id == 0 or next_batch_id is None:
        ## Start With 10000 to let buffer for import from SQL
        next_batch_id = 10000
    else:
        next_batch_id = int(next_batch_id) + 1
    
    logger.info(
        f"{in_tbl_batch_id_control}: max batch id {next_batch_id}, "
        f"next batch id {next_batch_id}"
    )

    audit_ts = datetime.now(timezone.utc)
    spark.sql(
        f"""
        INSERT INTO {in_tbl_batch_id_control}
            (next_batch_id,     audit_creation_user,    audit_creation_date,    audit_last_update_user, audit_last_update_date, audit_load_id)
        VALUES 
            (:next_batch_id,    'bsas',                 :audit_ts,              'bsas',                 :audit_ts,              CAST(:audit_load_id AS BIGINT))
        """,
        args={"next_batch_id": next_batch_id, "audit_ts": audit_ts, "audit_load_id": int(in_audit_load_id)},
    )
    return int(next_batch_id)

# COMMAND ----------

# DBTITLE 1,Function: insert tbl_file_process
def insert_file_process(
    in_file_name: str,
    in_batch_id: int,
    in_srce_sys_id: str,
    in_art_type_id: str,
    in_file_art_written_count: int,
    in_tbl_file_process: str,
    in_process_status_id: str = "1",  # tbl_process_status: 1 = Success, 2 = Fail
    in_process_error_msg: str = "",
    in_audit_load_id: int = 0,  # Python int == SQL BIGINT
) -> None:
    """Insert one row per processed file into tbl_file_process."""
    spark.sql(
        f"""
        INSERT INTO {in_tbl_file_process}
            (file_name, process_error_msg, file_art_written_count, batch_id,
             process_status_id, srce_sys_id, art_type_id,
             audit_creation_user, audit_creation_date,
             audit_last_update_user, audit_last_update_date, audit_load_id)
        VALUES
            (:file_name, :process_error_msg, :file_art_written_count, :batch_id,
             :process_status_id, :srce_sys_id, :art_type_id,
             'load_FileProcess', current_timestamp(),
             'load_FileProcess', current_timestamp(), CAST(:audit_load_id AS BIGINT))
        """,
        args={
            "file_name": in_file_name,
            "process_error_msg": (in_process_error_msg or "")[:4000],
            "file_art_written_count": int(in_file_art_written_count or 0),
            "batch_id": int(in_batch_id),
            "process_status_id": str(in_process_status_id),
            "srce_sys_id": in_srce_sys_id,
            "art_type_id": in_art_type_id,
            "audit_load_id": int(in_audit_load_id),
        },
    )
    logger.info(
        f"tbl_file_process: {in_file_name} batch_id={in_batch_id} "
        f"status={in_process_status_id} rows={in_file_art_written_count}"
    )

# COMMAND ----------

def _xml_escape(c):
    """Escape XML special characters in a string column."""
    c = F.regexp_replace(c, "&", "&amp;")
    c = F.regexp_replace(c, "<", "&lt;")
    return F.regexp_replace(c, ">", "&gt;")


def _xml_tag(name: str, c):
    """Build <name>value</name>, or <name/> when the value is null/empty."""
    s = c.cast("string")
    return F.when(s.isNull() | (s == ""), F.lit(f"<{name}/>")).otherwise(
        F.concat(F.lit(f"<{name}>"), _xml_escape(s), F.lit(f"</{name}>"))
    )

# COMMAND ----------

# DBTITLE 1,Function: load tbl_archived_artifact (SAA / SWIFT)
def load_archived_artifact_habs(
    in_df_file,
    in_srce_sys_id: str,
    in_art_type_id: str,
    in_batch_id: int,
    in_tbl_archived_artifact: str,
    in_purge_months: int = 84,
    in_audit_load_id: int = 0,  # Python int == SQL BIGINT
):
    """Append one HABS file (one row per G_RECORD) to tbl_archived_artifact.

    Mapping (matches existing HABS311R rows):
      keyw1_srce_tran_id / keyw4_boc_doc_title = MESSAGE_PK
      keyw2_srce_tran_effect_date / srce_sys_creation_date = AUDIT_CREATION_DATE
      keyw5_boc_doc_creator = AUDIT_CREATION_USER
      art_archive_bytes = <G_RECORD> XML of the record (ISO-8859-1)
      purge_forward_date = srce_sys_creation_date + 84 months, purge_hold_flag = 'N'
    Returns the number of rows written.
    """
    record_xml = F.concat(
        F.lit("<G_RECORD>"),
        _xml_tag("MESSAGE_PK", F.col("MESSAGE_PK")),
        _xml_tag("BUSINESS_TRANS_PK", F.col("BUSINESS_TRANS_PK")),
        _xml_tag("MESSAGE_CONTENT_CLOB", F.col("MESSAGE_CONTENT_CLOB")),
        _xml_tag("AUDIT_CREATION_USER", F.col("AUDIT_CREATION_USER")),
        _xml_tag("AUDIT_CREATION_DATE", F.col("AUDIT_CREATION_DATE")),
        F.lit("</G_RECORD>"),
    )
    src_date = F.col("AUDIT_CREATION_DATE").cast("timestamp")
    now_ts = F.current_timestamp()

    df_art = in_df_file.select(
        F.lit(in_srce_sys_id).alias("srce_sys_id"),
        F.lit(in_art_type_id).alias("art_type_id"),
        F.lit(in_batch_id).cast("int").alias("batch_id_process_file"),
        F.col("MESSAGE_PK").cast("string").alias("keyw1_srce_tran_id"),
        src_date.alias("keyw2_srce_tran_effect_date"),
        F.lit(None).cast("string").alias("keyw3_srce_prime_party_id"),
        F.col("MESSAGE_PK").cast("string").alias("keyw4_boc_doc_title"),
        F.col("AUDIT_CREATION_USER").cast("string").alias("keyw5_boc_doc_creator"),
        F.lit(None).cast("string").alias("keyw6_srce_account_id"),
        F.lit(None).cast("string").alias("keyw7_value"),
        F.lit(None).cast("string").alias("keyw8_value"),
        F.lit(None).cast("string").alias("keyw9_value"),
        F.lit(None).cast("string").alias("keyw10_value"),
        F.encode(record_xml, "ISO-8859-1").alias("art_archive_bytes"),
        src_date.alias("srce_sys_creation_date"),
        F.add_months(src_date, in_purge_months).cast("timestamp").alias("purge_forward_date"),
        F.lit("N").alias("purge_hold_flag"),
        F.lit("load_Artifact").alias("audit_creation_user"),
        now_ts.alias("audit_creation_date"),
        F.lit("load_artifact").alias("audit_last_update_user"),
        now_ts.alias("audit_last_update_date"),
        F.lit(in_audit_load_id).cast("bigint").alias("audit_load_id"),
    )

    if df_art.where(F.col("keyw1_srce_tran_id").isNull()).limit(1).count() > 0:
        raise ValueError(f"MESSAGE_PK is null for some records (batch_id={in_batch_id})")

    row_count = df_art.count()
    df_art.write.mode("append").saveAsTable(in_tbl_archived_artifact)
    logger.info(
        f"Loaded {row_count} row(s) into {in_tbl_archived_artifact} "
        f"(art_type_id={in_art_type_id}, batch_id={in_batch_id})"
    )

# COMMAND ----------

# audit_load_id must be numeric: job run id in jobs, 0 when run interactively (default is a UUID)
audit_load_id = int(job_run_id) if str(job_run_id).strip().isdigit() else 0
logger.info(f"audit_load_id: {audit_load_id}")

## Set Catalog and table names 
catalog = f"{job_ctx['env']}_banking_and_payments_cat"
tbl_batch_id_control = f"{catalog}.bsas_db.tbl_batch_id_control"
tbl_file_process = f"{catalog}.bsas_db.tbl_file_process"
tbl_archived_artifat = f"{catalog}.bsas_db.tbl_archived_artifact"

file_date = dbutils.jobs.taskValues.get(
    taskKey="main", key="file_date", debugValue=date.today().isoformat()
)
logger.info(f"file_date: {file_date}")

raw_root = job_ctx.get("raw_root")
raw_path = f"{raw_root}/{file_date}"

# List HABS XML files in the raw folder
xml_files = sorted(
    [f for f in dbutils.fs.ls(raw_path) if f.name.upper().endswith(".XML")],
    key=lambda f: f.name,
)
if not xml_files:
    raise FileNotFoundError(f"No XML files found in {raw_path}")
print(f"Found {len(xml_files)} XML file(s) in {raw_path}")

# 1- Insert tbl_batch_id_control
# Get one ID per execution
next_batch_id = insert_batch_id_control(in_tbl_batch_id_control=tbl_batch_id_control, in_audit_load_id=audit_load_id)

## Loop on files o Raw folder
## For each file a new batch_id will be generated
for f in xml_files:
    
    ## Set parameters table load
    srce_sys_id = 'HABS'
    art_type_id = f.name.split("_")[0]

    df_file = load_bsas_xml_file(f.path)

    if(df_file.isEmpty()):       
        ## Insert one rcord in tbl_file_process for the empty file
        insert_file_process(
            in_file_name = f.name,
            in_batch_id = next_batch_id,
            in_srce_sys_id = srce_sys_id,
            in_art_type_id = art_type_id,
            in_file_art_written_count = 0,
            in_tbl_file_process = tbl_file_process,
            in_audit_load_id = audit_load_id)
    else:
        ## Process files
        try:
            ## 2 Insert Table tbl_archived_artifact
            ## Load SWIFT File
            load_archived_artifact_habs(
                in_df_file=df_file,
                in_srce_sys_id=srce_sys_id,
                in_art_type_id=art_type_id,
                in_batch_id=next_batch_id,
                in_tbl_archived_artifact=tbl_archived_artifat,
                in_audit_load_id = audit_load_id)
        
        except Exception as e:
            # 3- Insert tbl_file_process if error
            # Record the failed file (status 2 = Fail).
            insert_file_process(
                in_file_name=f.name,
                in_batch_id=next_batch_id,
                in_srce_sys_id=srce_sys_id,
                in_art_type_id=art_type_id,
                in_file_art_written_count=0,
                in_tbl_file_process=tbl_file_process,
                in_process_status_id="2",
                in_process_error_msg=str(e),
                in_audit_load_id = audit_load_id)            

        else:
            ## 3- Insert tbl_file_process if success (only when the load did not fail)
            ## Table tbl_file_process (status 1 = Success)
            insert_file_process(
                in_file_name=f.name,
                in_batch_id=next_batch_id,
                in_srce_sys_id=srce_sys_id,
                in_art_type_id=art_type_id,
                in_file_art_written_count=df_file.count(),
                in_tbl_file_process=tbl_file_process,
                in_audit_load_id = audit_load_id)