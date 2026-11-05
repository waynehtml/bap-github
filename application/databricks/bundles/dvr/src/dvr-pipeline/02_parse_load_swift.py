# Databricks notebook source
# DBTITLE 1,Parse and Load SWIFT DVR Data
# MAGIC %md
# MAGIC # Parse and Load SWIFT DVR Data (02)
# MAGIC
# MAGIC Parses validated SWIFT DVR Excel files from the archive folder and loads transaction data into `tbl_swift_message_fact`. Receives the list of valid files from notebook 01 via `dbutils.widgets`.

# COMMAND ----------

# DBTITLE 1,Configuration and imports
import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType,
    DateType, TimestampType, DecimalType
)

# --- Environment (job parameters; interactive runs default to this workspace's env) ---
_ENV = {"adb-1700301391505163": "dev", "adb-13344226264609": "stg", "adb-642333651898149": "prd"}.get(
    spark.conf.get("spark.databricks.workspaceUrl", "").split(".")[0], "dev")
dbutils.widgets.text("catalog", f"{_ENV}_banking_and_payments_cat", "BAP catalog")
dbutils.widgets.text("swift_volume_root", f"/Volumes/{_ENV}_raw_cat/restricted_db/vol_internal_swift", "SWIFT volume root")
CATALOG = dbutils.widgets.get("catalog")

# --- Volume paths ---
BASE_VOLUME = dbutils.widgets.get("swift_volume_root").rstrip("/")
ARCHIVE_PATH = f"{BASE_VOLUME}/archive"

# --- Target table ---
SWIFT_FACT_TABLE = f"{CATALOG}.derived_db.tbl_swift_message_fact"
FI_DIM_TABLE = f"{CATALOG}.curated_db.tbl_financial_institution_dim"
print(f"Catalog: {CATALOG} | Archive: {ARCHIVE_PATH}")

# --- Widget: receive valid files from notebook 01 or process all in archive ---
dbutils.widgets.text("valid_files_json", "", "Valid files JSON from notebook 01")
valid_files_json = dbutils.widgets.get("valid_files_json")

# In a job run, always load only the files the validate task accepted in this
# run. Scanning the whole archive here reloaded every earlier upload.
INTERACTIVE = "__INTERACTIVE__"
if not valid_files_json:
    try:
        valid_files_json = dbutils.jobs.taskValues.get(
            taskKey="validate_swift_files", key="valid_files_json", debugValue=INTERACTIVE
        ) or "[]"
    except Exception:
        valid_files_json = INTERACTIVE

if valid_files_json != INTERACTIVE:
    valid_files = json.loads(valid_files_json)
    print(f"Received {len(valid_files)} file(s) from validate_swift_files")
else:
    # Interactive debugging only: process every file currently in archive
    try:
        archive_files = [f for f in os.listdir(ARCHIVE_PATH) if f.endswith((".xlsx", ".xls", ".csv"))]
    except FileNotFoundError:
        archive_files = []
    FILENAME_PATTERN = re.compile(r"^Activity Reports_(inbound|outbound)_Entity_(\d{8}).*\.(xlsx|xls|csv)$")
    valid_files = []
    for f in archive_files:
        m = FILENAME_PATTERN.match(f)
        if m:
            valid_files.append({
                "filename": f,
                "file_type": m.group(1).upper(),
                "file_date": f"{m.group(2)[:4]}-{m.group(2)[4:6]}-{m.group(2)[6:8]}",
                "archive_path": os.path.join(ARCHIVE_PATH, f)
            })
    print(f"No upstream input — found {len(valid_files)} file(s) in archive")

print(f"Files to process: {[f['filename'] for f in valid_files]}")

# COMMAND ----------

# DBTITLE 1,Stdlib xlsx/csv parser (shared with notebook 01)
# ---------------------------------------------------------------------------
# Reuse the same stdlib xlsx/csv parser from notebook 01
# ---------------------------------------------------------------------------
import csv as _csv
XLSX_NS = {
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

def _col_letter_to_index(col: str) -> int:
    idx = 0
    for ch in col.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1

def _parse_cell_ref(ref: str) -> tuple:
    col = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            break
    return _col_letter_to_index(col), int(ref[len(col):])

def read_xlsx(filepath: str) -> dict:
    result = {"sheet_names": [], "sheets": {}}
    try:
        zf = zipfile.ZipFile(filepath, "r")
    except Exception as e:
        return {"error": str(e)}
    shared_strings = []
    if "xl/sharedStrings.xml" in zf.namelist():
        ss_tree = ET.parse(zf.open("xl/sharedStrings.xml"))
        for si in ss_tree.findall(".//s:si", XLSX_NS):
            parts = []
            t_elem = si.find("s:t", XLSX_NS)
            if t_elem is not None and t_elem.text:
                parts.append(t_elem.text)
            else:
                for r in si.findall(".//s:r/s:t", XLSX_NS):
                    if r.text:
                        parts.append(r.text)
            shared_strings.append("".join(parts))
    wb_tree = ET.parse(zf.open("xl/workbook.xml"))
    sheet_map = {}
    for sheet_el in wb_tree.findall(".//s:sheets/s:sheet", XLSX_NS):
        name = sheet_el.get("name")
        rid = sheet_el.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        sheet_map[rid] = name
        result["sheet_names"].append(name)
    rid_to_path = {}
    if "xl/_rels/workbook.xml.rels" in zf.namelist():
        rels_tree = ET.parse(zf.open("xl/_rels/workbook.xml.rels"))
        for rel in rels_tree.findall(".//rel:Relationship", XLSX_NS):
            rid_to_path[rel.get("Id")] = "xl/" + rel.get("Target")
    for rid, sheet_name in sheet_map.items():
        ws_path = rid_to_path.get(rid)
        if not ws_path or ws_path not in zf.namelist():
            continue
        ws_tree = ET.parse(zf.open(ws_path))
        rows_dict = {}
        max_col = 0
        for row_el in ws_tree.findall(".//s:sheetData/s:row", XLSX_NS):
            row_num = int(row_el.get("r"))
            for cell_el in row_el.findall("s:c", XLSX_NS):
                ref = cell_el.get("r")
                col_idx, _ = _parse_cell_ref(ref)
                max_col = max(max_col, col_idx)
                cell_type = cell_el.get("t", "")
                v_el = cell_el.find("s:v", XLSX_NS)
                raw_val = v_el.text if v_el is not None else None
                if raw_val is None:
                    is_el = cell_el.find(".//s:is/s:t", XLSX_NS)
                    value = is_el.text if is_el is not None else None
                elif cell_type == "s":
                    idx = int(raw_val)
                    value = shared_strings[idx] if idx < len(shared_strings) else raw_val
                elif cell_type == "b":
                    value = raw_val == "1"
                else:
                    value = raw_val
                if row_num not in rows_dict:
                    rows_dict[row_num] = {}
                rows_dict[row_num][col_idx] = value
        if rows_dict:
            all_rows = []
            for rn in sorted(rows_dict.keys()):
                row_data = [rows_dict[rn].get(c) for c in range(max_col + 1)]
                all_rows.append((rn, row_data))
            result["sheets"][sheet_name] = all_rows
        else:
            result["sheets"][sheet_name] = []
    zf.close()
    return result

def parse_dvr_date(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    s = str(value).strip().strip("'")
    for fmt in ["%d %b %Y", "%d-%b-%y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        serial = int(float(s))
        if 1 < serial < 200000:
            return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    except (ValueError, OverflowError):
        pass
    return None

def parse_amount(value):
    """Parse amount strings like '$31,569,106,561.78' or plain numbers."""
    if value is None:
        return None
    s = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

def read_csv_as_xlsx(filepath: str) -> dict:
    """Read a CSV file and return it in the same structure as read_xlsx.
    Tries UTF-8 first, then falls back to Latin-1 (common for SWIFT exports)."""
    ws_name = "Activity Report - Transactions"
    result = {"sheet_names": [ws_name], "sheets": {}}
    try:
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(filepath, "r", encoding=enc) as fh:
                    reader = _csv.reader(fh)
                    rows = []
                    for row_num, row in enumerate(reader, start=1):
                        rows.append((row_num, row))
                result["sheets"][ws_name] = rows
                break
            except UnicodeDecodeError:
                continue
        else:
            return {"error": "Cannot decode CSV with utf-8 or latin-1"}
    except Exception as e:
        return {"error": str(e)}
    return result


def read_file(filepath: str) -> dict:
    """Read xlsx or csv file into unified structure."""
    if filepath.lower().endswith(".csv"):
        return read_csv_as_xlsx(filepath)
    return read_xlsx(filepath)

print("xlsx/csv parser and helpers loaded.")

# COMMAND ----------

# DBTITLE 1,Parse DVR files and build transaction rows
from decimal import Decimal

REQUIRED_WORKSHEETS = {"Activity Report - Transactions", "Activity Report \u2013 Transactions"}

# Column mapping: DVR Excel column name -> target field
# Supports both spec names and actual production file column names
DVR_COLUMNS = {
    # Date columns
    "Daily period": "trans_date_id",
    "Daily Period": "trans_date_id",
    "Input Day (UTC)": "trans_utc_date_id",
    "Input Day UTC": "trans_utc_date_id",
    # Message type
    "Message type": "swift_gen_message_type",
    "Message Definition": "swift_gen_message_type",
    # Currency
    "Currency": "currency_code",
    # Originator / Debtor FI
    "Originating Country": "originating_country",
    "Debtor FI Country": "originating_country",
    "Originating BIC8": "originating_bic8",
    "Originating (BIC8)": "originating_bic8",
    "Debtor FI BIC8": "originating_bic8",
    # Counterparty
    "Counterparty (BIC8)": "counterparty_bic8",
    "Counterparty BIC8": "counterparty_bic8",
    "Counterparty Country": "counterparty_country",
    # My entity
    "My Entities (BIC8)": "my_entity_bic8",
    "My BIC8": "my_entity_bic8",
    "My Entities (BIC11)": "my_entity_bic11",
    "My BIC11": "my_entity_bic11",
    # Beneficiary / Creditor FI
    "Beneficiary BIC8": "beneficiary_bic8",
    "Creditor FI BIC8": "beneficiary_bic8",
    "Beneficiary Country": "beneficiary_country",
    "Creditor FI Country": "beneficiary_country",
    # Transaction
    "Transaction Reference": "transaction_reference",
    "UETR": "uetr",
    "Transaction received": "transactions_received_cnt",
    "Transactions received": "transactions_received_cnt",
    "Transactions sent": "transactions_received_cnt",
    "Amount received": "amount_received",
    "Amount sent": "amount_received",
    "Amount received (converted in CAD)": "amount_received_cad",
    "Amount sent (converted in CAD)": "amount_received_cad",
}

# ---------------------------------------------------------------------------
# ISO 20022 → legacy MT code mapping
# SWIFT.com CSV exports use ISO 20022 message names; HABS uses MT codes.
# ---------------------------------------------------------------------------
# Per Chris McNaught (2026-10-14): Swift DVR only uses pacs.008 and pacs.009.
ISO20022_TO_MT = {
    "pacs.008": "MT103",     # Customer Credit Transfer
    "pacs.009": "MT202",     # Financial Institution Credit Transfer
}


def normalize_message_type(raw: str) -> str:
    """Normalize message type to legacy MT code for HABS reconciliation."""
    s = raw.strip()
    if not s:
        return ""
    if s.upper().startswith("MT") or s.upper().startswith("NT"):
        mt = s.upper().replace("NT", "MT")
        if mt == "MT202C":
            return "MT202COV"
        if mt == "MT205C":
            return "MT205COV"
        return mt
    iso_key = s.lower().split(".")[0] + "." + s.lower().split(".")[1][:3] if "." in s else s.lower()
    if iso_key in ISO20022_TO_MT:
        return ISO20022_TO_MT[iso_key]
    return s


all_transactions = []
file_counter = 0

for file_info in valid_files:
    filename = file_info["filename"]
    file_type = file_info["file_type"]
    file_date_str = file_info["file_date"]
    archive_path = file_info["archive_path"]
    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()

    print(f"\nParsing: {filename} ({file_type}, {file_date})")

    # --- Dedup: remove any previously loaded rows for this file ---
    try:
        del_count = spark.sql(f"""
            DELETE FROM {SWIFT_FACT_TABLE}
            WHERE source_filename = '{filename}'
        """).collect()[0][0]
        if del_count:
            print(f"  Dedup: removed {del_count} existing row(s) for this file")
    except Exception as e:
        print(f"  Dedup check skipped: {e}")

    xlsx = read_file(archive_path)
    if "error" in xlsx:
        print(f"  ERROR opening file: {xlsx['error']}")
        continue

    ws_name = next((n for n in xlsx["sheet_names"] if n in REQUIRED_WORKSHEETS), None)
    if ws_name is None:
        # Fall back to first sheet
        ws_name = xlsx["sheet_names"][0] if xlsx["sheet_names"] else None
    if not ws_name or ws_name not in xlsx["sheets"]:
        print(f"  ERROR: no worksheet found")
        continue

    rows = xlsx["sheets"][ws_name]

    # Find header row
    headers = {}
    header_row_idx = None
    for excel_row_num, row_values in rows[:5]:
        for col_idx, v in enumerate(row_values):
            if v and str(v).strip() in DVR_COLUMNS:
                headers[str(v).strip()] = col_idx
        if headers:
            header_row_idx = excel_row_num
            # Map all columns in this header row
            headers = {str(v).strip(): col_idx for col_idx, v in enumerate(row_values) if v is not None}
            break

    if not headers:
        print(f"  ERROR: cannot find header row")
        continue

    print(f"  Found {len(headers)} columns at row {header_row_idx}")

    # Helper to get value by DVR column name
    def get_val(row_vals, col_name):
        idx = headers.get(col_name)
        if idx is not None and idx < len(row_vals):
            return row_vals[idx]
        return None

    # Parse data rows
    found_header = False
    row_count = 0
    for excel_row_num, row_values in rows:
        if excel_row_num == header_row_idx:
            found_header = True
            continue
        if not found_header:
            continue
        if all(v is None for v in row_values):
            continue

        # Normalize message type — handles MT codes and ISO 20022 (pacs.008 → MT103)
        raw_mt = str(
            get_val(row_values, "Message type")
            or get_val(row_values, "Message Definition")
            or ""
        ).strip()
        mt = normalize_message_type(raw_mt)

        trans_date = parse_dvr_date(get_val(row_values, "Daily period") or get_val(row_values, "Daily Period"))
        utc_date = parse_dvr_date(get_val(row_values, "Input Day (UTC)") or get_val(row_values, "Input Day UTC"))
        amount = parse_amount(
            get_val(row_values, "Amount received")
            or get_val(row_values, "Amount sent")
        )
        amount_cad = parse_amount(
            get_val(row_values, "Amount received (converted in CAD)")
            or get_val(row_values, "Amount sent (converted in CAD)")
        )
        txn_cnt = (
            get_val(row_values, "Transaction received")
            or get_val(row_values, "Transactions received")
            or get_val(row_values, "Transactions sent")
        )

        txn = {
            "swift_message_fact_skey": None,
            "md_workflow_execution_skey": None,
            "trans_date_id": trans_date or file_date,
            "trans_utc_date_id": utc_date,
            "swift_message_type_skey": None,  # looked up later
            "swift_gen_message_type": mt,
            "currency_skey": None,
            "currency_code": str(get_val(row_values, "Currency") or "").strip(),
            "originating_country": str(get_val(row_values, "Originating Country") or get_val(row_values, "Debtor FI Country") or "").strip(),
            "originating_fi_skey": None,
            "originating_bic8": str(get_val(row_values, "Originating BIC8") or get_val(row_values, "Originating (BIC8)") or get_val(row_values, "Debtor FI BIC8") or "").strip(),
            "originating_bic_name": None,
            "counterparty_fi_skey": None,
            "counterparty_bic8": str(get_val(row_values, "Counterparty (BIC8)") or get_val(row_values, "Counterparty BIC8") or "").strip(),
            "counterparty_country": str(get_val(row_values, "Counterparty Country") or "").strip(),
            "counterparty_bic_name": None,
            "beneficiary_fi_skey": None,
            "beneficiary_bic8": str(get_val(row_values, "Beneficiary BIC8") or get_val(row_values, "Creditor FI BIC8") or "").strip(),
            "beneficiary_country": str(get_val(row_values, "Beneficiary Country") or get_val(row_values, "Creditor FI Country") or "").strip(),
            "beneficiary_bic_name": None,
            "transaction_reference": str(get_val(row_values, "Transaction Reference") or "").strip(),
            "transactions_received_cnt": int(txn_cnt) if txn_cnt else 1,
            "amount_received": amount,
            "amount_received_cad": amount_cad,
            "inbound_outbound_ind": file_type,
            "source_filename": filename,
            "source_file_date": file_date,
            "audit_create_ts": datetime.now(),
            "audit_last_update_ts": datetime.now(),
        }
        all_transactions.append(txn)
        row_count += 1

    file_counter += 1
    print(f"  Parsed {row_count} transaction(s)")

print(f"\nTotal: {len(all_transactions)} transactions from {file_counter} file(s)")

# COMMAND ----------

# DBTITLE 1,Create DataFrame and write to SWIFT fact table
if all_transactions:
    fact_schema = StructType([
        StructField("swift_message_fact_skey", LongType(), True),
        StructField("md_workflow_execution_skey", LongType(), True),
        StructField("trans_date_id", DateType(), True),
        StructField("trans_utc_date_id", DateType(), True),
        StructField("swift_message_type_skey", LongType(), True),
        StructField("swift_gen_message_type", StringType(), True),
        StructField("currency_skey", LongType(), True),
        StructField("currency_code", StringType(), True),
        StructField("originating_country", StringType(), True),
        StructField("originating_fi_skey", LongType(), True),
        StructField("originating_bic8", StringType(), True),
        StructField("originating_bic_name", StringType(), True),
        StructField("counterparty_fi_skey", LongType(), True),
        StructField("counterparty_bic8", StringType(), True),
        StructField("counterparty_bic_name", StringType(), True),
        StructField("beneficiary_fi_skey", LongType(), True),
        StructField("beneficiary_bic8", StringType(), True),
        StructField("beneficiary_bic_name", StringType(), True),
        StructField("transaction_reference", StringType(), True),
        StructField("transactions_received_cnt", IntegerType(), True),
        StructField("amount_received", DecimalType(20, 2), True),
        StructField("amount_received_cad", DecimalType(20, 2), True),
        StructField("inbound_outbound_ind", StringType(), True),
        StructField("source_filename", StringType(), True),
        StructField("source_file_date", DateType(), True),
        StructField("audit_create_ts", TimestampType(), True),
        StructField("audit_last_update_ts", TimestampType(), True),
    ])

    rows = []
    for t in all_transactions:
        rows.append((
            t["swift_message_fact_skey"],
            t["md_workflow_execution_skey"],
            t["trans_date_id"],
            t["trans_utc_date_id"],
            t["swift_message_type_skey"],
            t["swift_gen_message_type"],
            t["currency_skey"],
            t["currency_code"],
            t["originating_country"],
            t["originating_fi_skey"],
            t["originating_bic8"],
            t["originating_bic_name"],
            t["counterparty_fi_skey"],
            t["counterparty_bic8"],
            t["counterparty_bic_name"],
            t["beneficiary_fi_skey"],
            t["beneficiary_bic8"],
            t["beneficiary_bic_name"],
            t["transaction_reference"],
            t["transactions_received_cnt"],
            Decimal(str(t["amount_received"])) if t["amount_received"] is not None else None,
            Decimal(str(t["amount_received_cad"])) if t["amount_received_cad"] is not None else None,
            t["inbound_outbound_ind"],
            t["source_filename"],
            t["source_file_date"],
            t["audit_create_ts"],
            t["audit_last_update_ts"],
        ))

    swift_df = spark.createDataFrame(rows, fact_schema)

    # Lookup FI dimension keys by BIC8.
    # The FI dim has several current rows for some BIC8s (e.g. BCANCAW2 x4,
    # CUCXCATT x6), which multiplied SWIFT rows ~3x on the joins below.
    # Keep exactly one current row per BIC8 (highest skey) so each source
    # transaction produces exactly one fact row.
    from pyspark.sql import Window
    _fi_window = Window.partitionBy("bic8").orderBy(F.col("financial_institution_skey").desc())
    fi_dim = (
        spark.table(FI_DIM_TABLE)
        .where((F.col("md_current_ind") == 1) & F.col("bic8").isNotNull())
        .select("bic8", "financial_institution_skey", "financial_institution_enm")
        .withColumn("_rn", F.row_number().over(_fi_window))
        .where(F.col("_rn") == 1)
        .drop("_rn")
    )

    # Join for originating, counterparty, beneficiary
    swift_df = swift_df \
        .join(fi_dim.alias("orig"), swift_df.originating_bic8 == F.col("orig.bic8"), "left") \
        .withColumn("originating_fi_skey", F.coalesce(F.col("orig.financial_institution_skey"), F.lit(-1))) \
        .withColumn("originating_bic_name", F.col("orig.financial_institution_enm")) \
        .drop("orig.bic8", "orig.financial_institution_skey", "orig.financial_institution_enm")

    swift_df = swift_df \
        .join(fi_dim.alias("cpty"), swift_df.counterparty_bic8 == F.col("cpty.bic8"), "left") \
        .withColumn("counterparty_fi_skey", F.coalesce(F.col("cpty.financial_institution_skey"), F.lit(-1))) \
        .withColumn("counterparty_bic_name", F.col("cpty.financial_institution_enm")) \
        .drop("cpty.bic8", "cpty.financial_institution_skey", "cpty.financial_institution_enm")

    swift_df = swift_df \
        .join(fi_dim.alias("bene"), swift_df.beneficiary_bic8 == F.col("bene.bic8"), "left") \
        .withColumn("beneficiary_fi_skey", F.coalesce(F.col("bene.financial_institution_skey"), F.lit(-1))) \
        .withColumn("beneficiary_bic_name", F.col("bene.financial_institution_enm")) \
        .drop("bene.bic8", "bene.financial_institution_skey", "bene.financial_institution_enm")

    # Select final columns matching target table
    final_cols = [f.name for f in fact_schema.fields]
    swift_df = swift_df.select(*final_cols)

    # Guard: the fact must have exactly one row per parsed source transaction.
    _fact_rows = swift_df.count()
    if _fact_rows != len(all_transactions):
        raise ValueError(
            f"Row count mismatch: parsed {len(all_transactions)} transactions but "
            f"built {_fact_rows} fact rows (check FI dimension join duplicates)."
        )

    swift_df.write.mode("append").saveAsTable(SWIFT_FACT_TABLE)
    print(f"\nWrote {len(all_transactions)} row(s) to {SWIFT_FACT_TABLE}")
    display(swift_df.limit(5))
else:
    print("No transactions to load.")

# COMMAND ----------

# DBTITLE 1,Notebook exit
result = json.dumps({
    "transactions_loaded": len(all_transactions),
    "files_processed": file_counter,
    "file_dates": list(set(f["file_date"] for f in valid_files))
})
print(f"Notebook result: {result}")
dbutils.jobs.taskValues.set(key="status", value="PASSED")
dbutils.notebook.exit(result)
