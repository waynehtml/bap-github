# Databricks notebook source
# DBTITLE 1,SWIFT DVR File Validation
# MAGIC %md
# MAGIC # SWIFT DVR File Validation (01)
# MAGIC
# MAGIC Reads uploaded SWIFT DVR Excel files from the inbox volume, validates filename format, worksheet name, date consistency, and required fields. Routes valid files to archive and invalid files to rejected, with error logs.

# COMMAND ----------

# DBTITLE 1,Configuration
import os
import re
import json
import shutil
from datetime import datetime, date
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, DateType, TimestampType

# --- Environment (job parameters; interactive runs default to this workspace's env) ---
_ENV = {"adb-1700301391505163": "dev", "adb-13344226264609": "stg", "adb-642333651898149": "prd"}.get(
    spark.conf.get("spark.databricks.workspaceUrl", "").split(".")[0], "dev")
dbutils.widgets.text("catalog", f"{_ENV}_banking_and_payments_cat", "BAP catalog")
dbutils.widgets.text("swift_volume_root", f"/Volumes/{_ENV}_raw_cat/restricted_db/vol_internal_swift", "SWIFT volume root")
CATALOG = dbutils.widgets.get("catalog")

# --- Volume paths ---
BASE_VOLUME = dbutils.widgets.get("swift_volume_root").rstrip("/")
INBOX_PATH = f"{BASE_VOLUME}/inbox"
ARCHIVE_PATH = f"{BASE_VOLUME}/archive"
REJECTED_PATH = f"{BASE_VOLUME}/rejected"
ERROR_LOG_PATH = f"{BASE_VOLUME}/error_logs"

# --- Target table ---
PROCESSING_LOG_TABLE = f"{CATALOG}.derived_db.tbl_dvr_file_processing_log"

# --- Filename regex pattern ---
# Accepts both original spec format and real SWIFT.com export format:
#   Activity Reports_inbound_Entity_YYYYMMDD.xlsx
#   Activity Reports_inbound_Entity_20261008_(20261009_074039)(Activity Report - Transactions).csv
FILENAME_PATTERN = re.compile(
    r"^Activity Reports_(inbound|outbound)_Entity_(\d{8}).*\.(xlsx|xls|csv)$"
)

# --- Required worksheet name (for Excel files) ---
# Production files use a regular hyphen; the spec used an em dash.
# Accept both to avoid false rejections.
# CSV files skip worksheet validation entirely.
REQUIRED_WORKSHEETS = {"Activity Report - Transactions", "Activity Report \u2013 Transactions"}

# --- Required columns that cannot be blank ---
# Accept both spec names and actual production file column names
REQUIRED_COLUMNS_VARIANTS = {
    "input_day": ["Input Day (UTC)", "Input Day UTC"],
    "message_type": ["Message type", "Message Definition"],
    "txn_ref": ["Transaction Reference"],
    "amount": ["Amount received", "Amount sent"],
}

# --- Ensure output folders exist ---
for path in [ARCHIVE_PATH, REJECTED_PATH, ERROR_LOG_PATH]:
    os.makedirs(path, exist_ok=True)

print(f"Catalog:    {CATALOG}")
print(f"Inbox:      {INBOX_PATH}")
print(f"Archive:    {ARCHIVE_PATH}")
print(f"Rejected:   {REJECTED_PATH}")
print(f"Error logs: {ERROR_LOG_PATH}")

# COMMAND ----------

# DBTITLE 1,Validation functions (stdlib — xlsx and csv)
import csv as _csv
import zipfile
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Stdlib-only .xlsx parser (no openpyxl needed)
# .xlsx is a ZIP of XML files.  We read:
#   xl/workbook.xml          -> sheet names
#   xl/sharedStrings.xml     -> string table
#   xl/worksheets/sheet*.xml -> cell data
# ---------------------------------------------------------------------------

XLSX_NS = {
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _col_letter_to_index(col: str) -> int:
    """Convert Excel column letters (A, B, ..., Z, AA, AB, ...) to 0-based index."""
    idx = 0
    for ch in col.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _parse_cell_ref(ref: str) -> tuple:
    """Parse 'AB12' into (col_index_0based, row_number_1based)."""
    col = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            break
    row = int(ref[len(col):])
    return _col_letter_to_index(col), row


def read_xlsx(filepath: str) -> dict:
    """
    Read an .xlsx file using only stdlib.
    Returns {"sheet_names": [...], "sheets": {name: [[row], ...]}}
    """
    result = {"sheet_names": [], "sheets": {}}
    try:
        zf = zipfile.ZipFile(filepath, "r")
    except Exception as e:
        return {"error": str(e)}

    # 1. Shared strings table
    shared_strings = []
    if "xl/sharedStrings.xml" in zf.namelist():
        ss_tree = ET.parse(zf.open("xl/sharedStrings.xml"))
        for si in ss_tree.findall(".//s:si", XLSX_NS):
            # A shared string may have <t> directly or <r><t> runs
            parts = []
            t_elem = si.find("s:t", XLSX_NS)
            if t_elem is not None and t_elem.text:
                parts.append(t_elem.text)
            else:
                for r in si.findall(".//s:r/s:t", XLSX_NS):
                    if r.text:
                        parts.append(r.text)
            shared_strings.append("".join(parts))

    # 2. Workbook: map sheet names -> rIds
    wb_tree = ET.parse(zf.open("xl/workbook.xml"))
    sheet_map = {}  # rId -> name
    for sheet_el in wb_tree.findall(".//s:sheets/s:sheet", XLSX_NS):
        name = sheet_el.get("name")
        rid = sheet_el.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        sheet_map[rid] = name
        result["sheet_names"].append(name)

    # 3. Workbook relationships: rId -> file path
    rid_to_path = {}
    if "xl/_rels/workbook.xml.rels" in zf.namelist():
        rels_tree = ET.parse(zf.open("xl/_rels/workbook.xml.rels"))
        for rel in rels_tree.findall(".//rel:Relationship", XLSX_NS):
            rid_to_path[rel.get("Id")] = "xl/" + rel.get("Target")

    # 4. Parse each worksheet
    for rid, sheet_name in sheet_map.items():
        ws_path = rid_to_path.get(rid)
        if not ws_path or ws_path not in zf.namelist():
            continue

        ws_tree = ET.parse(zf.open(ws_path))
        rows_dict = {}  # row_num -> {col_idx: value}
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
                    # Check for inline string
                    is_el = cell_el.find(".//s:is/s:t", XLSX_NS)
                    value = is_el.text if is_el is not None else None
                elif cell_type == "s":  # shared string
                    idx = int(raw_val)
                    value = shared_strings[idx] if idx < len(shared_strings) else raw_val
                elif cell_type == "b":  # boolean
                    value = raw_val == "1"
                else:
                    # number or date — keep as string, caller will parse
                    value = raw_val

                if row_num not in rows_dict:
                    rows_dict[row_num] = {}
                rows_dict[row_num][col_idx] = value

        # Convert to list-of-lists
        if rows_dict:
            all_rows = []
            for rn in sorted(rows_dict.keys()):
                row_data = [rows_dict[rn].get(c) for c in range(max_col + 1)]
                all_rows.append((rn, row_data))  # (excel_row_num, [values])
            result["sheets"][sheet_name] = all_rows
        else:
            result["sheets"][sheet_name] = []

    zf.close()
    return result


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_filename(filename: str) -> tuple:
    """Validate filename matches expected pattern. Returns (is_valid, file_type, file_date, errors)."""
    errors = []
    match = FILENAME_PATTERN.match(filename)
    if not match:
        errors.append({
            "Error_Code": "DVRFNERR001",
            "Description": "Filename format error",
            "Excel_Row": "N/A",
            "Additional_Details": f"Expected pattern: Activity Reports_{{inbound|outbound}}_Entity_YYYYMMDD[...].xlsx/.csv, got: {filename}"
        })
        return False, None, None, errors

    file_type = match.group(1).upper()  # INBOUND or OUTBOUND
    date_str = match.group(2)

    try:
        file_date = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        errors.append({
            "Error_Code": "DVRFNERR001",
            "Description": "Filename date error",
            "Excel_Row": "N/A",
            "Additional_Details": f"Invalid date in filename: {date_str}"
        })
        return False, file_type, None, errors

    return True, file_type, file_date, errors


def read_csv_as_xlsx(filepath: str) -> dict:
    """Read a CSV file and return it in the same structure as read_xlsx.
    Uses a synthetic worksheet name so downstream code works identically.
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


def validate_worksheet(filepath: str) -> tuple:
    """Open the file (xlsx or csv) and validate contents. Returns (parsed_data, errors)."""
    errors = []
    # Choose parser based on file extension
    if filepath.lower().endswith(".csv"):
        xlsx = read_csv_as_xlsx(filepath)
    else:
        xlsx = read_xlsx(filepath)

    if "error" in xlsx:
        errors.append({
            "Error_Code": "DVRVALERR001",
            "Description": "Cannot open Excel file",
            "Excel_Row": "N/A",
            "Additional_Details": xlsx["error"]
        })
        return None, errors

    # Find any matching worksheet name (accept both hyphen and em dash)
    matched_ws = None
    for ws_name in xlsx["sheet_names"]:
        if ws_name in REQUIRED_WORKSHEETS:
            matched_ws = ws_name
            break
    if matched_ws is None:
        errors.append({
            "Error_Code": "DVRVALERR001",
            "Description": "Worksheet name error",
            "Excel_Row": "N/A",
            "Additional_Details": f"Expected worksheet matching {REQUIRED_WORKSHEETS}, found: {xlsx['sheet_names']}"
        })
        return None, errors

    # Store the matched name so downstream code uses the right key
    xlsx["_matched_worksheet"] = matched_ws
    return xlsx, errors


def parse_dvr_date(value) -> date:
    """Parse various date formats from DVR Excel cells into a Python date."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    s = str(value).strip().strip("'")
    # Try known DVR date formats
    for fmt in ["%d %b %Y", "%d-%b-%y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Excel serial date number (days since 1899-12-30)
    try:
        serial = int(float(s))
        if 1 < serial < 200000:  # sanity check
            from datetime import timedelta
            return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    except (ValueError, OverflowError):
        pass
    return None


def validate_file_content(xlsx_data: dict, file_type: str, file_date: date, filename: str) -> list:
    """Validate dates and required fields inside the Excel file. Returns list of errors."""
    errors = []
    matched_ws = xlsx_data.get("_matched_worksheet") or next((n for n in xlsx_data["sheet_names"] if n in REQUIRED_WORKSHEETS), None)
    rows = xlsx_data["sheets"].get(matched_ws, []) if matched_ws else []

    if not rows:
        errors.append({
            "Error_Code": "DVRVALERR001",
            "Description": "Worksheet is empty",
            "Excel_Row": "N/A",
            "Additional_Details": f"No data rows found in '{REQUIRED_WORKSHEET}'"
        })
        return errors

    # Find header row by scanning first 5 rows for known column names
    header_row_idx = None
    headers = {}
    for excel_row_num, row_values in rows[:5]:
        row_strs = [str(v).strip() for v in (row_values or []) if v is not None]
        if "Message type" in row_strs or "Message Definition" in row_strs or "Transaction Reference" in row_strs:
            header_row_idx = excel_row_num
            headers = {str(v).strip(): col_idx for col_idx, v in enumerate(row_values) if v is not None}
            break

    if header_row_idx is None:
        errors.append({
            "Error_Code": "DVRVALERR001",
            "Description": "Cannot find header row in worksheet",
            "Excel_Row": "N/A",
            "Additional_Details": "Scanned rows 1-5, could not find expected column headers"
        })
        return errors

    # Resolve required columns: find at least one variant for each required group
    resolved_required = {}  # group_name -> actual_column_name
    missing_groups = []
    for group, variants in REQUIRED_COLUMNS_VARIANTS.items():
        found = None
        for v in variants:
            if v in headers:
                found = v
                break
        if found:
            resolved_required[group] = found
        else:
            missing_groups.append(f"{group} (tried: {variants})")

    if missing_groups:
        errors.append({
            "Error_Code": "DVRVALERR001",
            "Description": "Missing required columns",
            "Excel_Row": str(header_row_idx),
            "Additional_Details": f"Missing columns: {missing_groups}. Found: {list(headers.keys())}"
        })
        return errors

    # Determine which date column to validate against file_date
    # Inbound: "Daily Period"/"Daily period" must match filename date
    # Outbound: "Input Day (UTC)"/"Input Day UTC" must match filename date
    if file_type == "INBOUND":
        date_col_name = next((k for k in headers if k.lower().startswith("daily")), None)
    else:
        date_col_name = resolved_required.get("input_day")
    date_col_idx = headers.get(date_col_name) if date_col_name else None

    # Validate each data row (skip header)
    found_header = False
    for excel_row_num, row_values in rows:
        if excel_row_num == header_row_idx:
            found_header = True
            continue
        if not found_header:
            continue

        # Skip empty rows
        if all(v is None for v in row_values):
            continue

        # Check required fields are not blank
        for group, col_name in resolved_required.items():
            col_idx = headers.get(col_name)
            if col_idx is not None and (col_idx >= len(row_values) or row_values[col_idx] is None or str(row_values[col_idx]).strip() == ""):
                txn_ref = row_values[headers.get("Transaction Reference", 0)] if headers.get("Transaction Reference") is not None else "Unknown"
                errors.append({
                    "Error_Code": "DVRVALERR003",
                    "Description": f"Required field blank: {col_name}",
                    "Excel_Row": str(excel_row_num),
                    "Additional_Details": f"For Transaction ID #: {txn_ref}"
                })

        # Validate date matches filename date
        if date_col_idx is not None and date_col_idx < len(row_values):
            cell_date = parse_dvr_date(row_values[date_col_idx])
            if cell_date is not None and cell_date != file_date:
                txn_ref = row_values[headers.get("Transaction Reference", 0)] if headers.get("Transaction Reference") is not None else "Unknown"
                errors.append({
                    "Error_Code": "DVRVALERR002",
                    "Description": f"Validation Error in {date_col_name}",
                    "Excel_Row": str(excel_row_num),
                    "Additional_Details": f"For Transaction ID #: {txn_ref}. Expected date {file_date}, found {cell_date}"
                })

    return errors

print("Validation functions loaded (stdlib only — no external dependencies).")

# COMMAND ----------

# DBTITLE 1,Discover files in inbox
# List all supported files in the inbox (.xlsx, .xls, .csv)
try:
    inbox_files = [f for f in os.listdir(INBOX_PATH) if f.endswith((".xlsx", ".xls", ".csv"))]
except FileNotFoundError:
    os.makedirs(INBOX_PATH, exist_ok=True)
    inbox_files = []

print(f"Found {len(inbox_files)} file(s) in inbox:")
for f in inbox_files:
    print(f"  - {f}")

if not inbox_files:
    print("\nNo files to process. Exiting gracefully.")

# COMMAND ----------

# DBTITLE 1,Main validation loop
from datetime import datetime as dt

valid_files = []
invalid_files = []
all_log_records = []

for filename in inbox_files:
    filepath = os.path.join(INBOX_PATH, filename)
    file_errors = []
    processing_start = dt.now()

    print(f"\n{'='*60}")
    print(f"Processing: {filename}")

    # --- Step 1: Validate filename ---
    fn_valid, file_type, file_date, fn_errors = validate_filename(filename)
    file_errors.extend(fn_errors)

    if not fn_valid:
        print(f"  FILENAME ERROR: {fn_errors[0]['Additional_Details']}")
    else:
        print(f"  File type: {file_type}, Date: {file_date}")

        # --- Step 2: Validate worksheet ---
        xlsx_data, ws_errors = validate_worksheet(filepath)
        file_errors.extend(ws_errors)

        if xlsx_data is not None:
            # --- Step 3: Validate content (dates + required fields) ---
            content_errors = validate_file_content(xlsx_data, file_type, file_date, filename)
            file_errors.extend(content_errors)

    processing_end = dt.now()

    # --- Route file based on validation result ---
    if file_errors:
        # Move to rejected
        dest = os.path.join(REJECTED_PATH, filename)
        shutil.move(filepath, dest)
        invalid_files.append({
            "filename": filename,
            "errors": file_errors,
        })
        status = "INVALID"

        # Write error log CSV
        error_log_name = f"{file_type or 'UNKNOWN'}_{file_date or 'NODATE'}_Validation_Error.csv"
        error_log_path = os.path.join(ERROR_LOG_PATH, error_log_name)
        with open(error_log_path, "w") as ef:
            ef.write("Error_Code,Description,Excel_Row,Additional_Details\n")
            for err in file_errors:
                ef.write(f"{err['Error_Code']},{err['Description']},{err['Excel_Row']},\"{err['Additional_Details']}\"\n")

        print(f"  REJECTED ({len(file_errors)} error(s)) → {dest}")
        print(f"  Error log → {error_log_path}")
    else:
        # Move to archive
        dest = os.path.join(ARCHIVE_PATH, filename)
        shutil.move(filepath, dest)
        valid_files.append({
            "filename": filename,
            "file_type": file_type,
            "file_date": str(file_date),
            "archive_path": dest
        })
        status = "VALID"
        print(f"  VALID → {dest}")

    # --- Build audit log record ---
    all_log_records.append({
        "filename": filename,
        "file_type": file_type or "UNKNOWN",
        "file_date": file_date,
        "file_path": filepath,
        "processing_status": status,
        "error_code": file_errors[0]["Error_Code"] if file_errors else None,
        "error_description": "; ".join([e["Description"] for e in file_errors]) if file_errors else None,
        "uploaded_by": None,  # populated by upload app metadata if available
        "processing_start_ts": processing_start,
        "processing_end_ts": processing_end,
        "archive_path": dest
    })

print(f"\n{'='*60}")
print(f"Summary: {len(valid_files)} valid, {len(invalid_files)} invalid out of {len(inbox_files)} files")

# COMMAND ----------

# DBTITLE 1,Write audit log to processing log table
if all_log_records:
    log_schema = StructType([
        StructField("log_skey", LongType(), True),
        StructField("filename", StringType(), False),
        StructField("file_type", StringType(), True),
        StructField("file_date", DateType(), True),
        StructField("file_path", StringType(), True),
        StructField("processing_status", StringType(), True),
        StructField("error_code", StringType(), True),
        StructField("error_description", StringType(), True),
        StructField("uploaded_by", StringType(), True),
        StructField("processing_start_ts", TimestampType(), True),
        StructField("processing_end_ts", TimestampType(), True),
        StructField("archive_path", StringType(), True),
        StructField("audit_create_ts", TimestampType(), True),
    ])

    log_rows = []
    for rec in all_log_records:
        log_rows.append((
            None,  # log_skey (auto-generated or null)
            rec["filename"],
            rec["file_type"],
            rec["file_date"],
            rec["file_path"],
            rec["processing_status"],
            rec["error_code"],
            rec["error_description"],
            rec["uploaded_by"],
            rec["processing_start_ts"],
            rec["processing_end_ts"],
            rec["archive_path"],
            dt.now(),
        ))

    log_df = spark.createDataFrame(log_rows, log_schema)
    log_df.write.mode("append").saveAsTable(PROCESSING_LOG_TABLE)
    print(f"Wrote {len(log_rows)} record(s) to {PROCESSING_LOG_TABLE}")
else:
    print("No files processed — nothing to log.")

# COMMAND ----------

# DBTITLE 1,Exit with valid file list for downstream tasks
# Pass valid files to the next task in the job via dbutils.notebook.exit()
result = json.dumps({
    "valid_files": valid_files,
    "invalid_files": invalid_files,
    "invalid_count": len(invalid_files),
    "total_processed": len(inbox_files),
    "report_date": str(dt.now().date()),
})

print(f"Notebook result:\n{result}")
# Make the current run's file list available to downstream tasks. Without
# this task value, notify falls back to every processing-log row from today,
# which re-notifies files processed by earlier runs.
dbutils.jobs.taskValues.set(key="result", value=result)
dbutils.jobs.taskValues.set(
    key="valid_files_json",
    value=json.dumps(valid_files),
)
dbutils.jobs.taskValues.set(key="report_date", value=str(dt.now().date()))
# Read by the job's has_files condition: 0 means the inbox was empty and the
# rest of the pipeline does not run.
dbutils.jobs.taskValues.set(key="file_count", value=len(inbox_files))
dbutils.jobs.taskValues.set(key="status", value="PASSED")
dbutils.notebook.exit(result)
