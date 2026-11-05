# Databricks notebook source
# DBTITLE 1,Generate retained DVR reports
# MAGIC %md
# MAGIC Writes transaction-level CSV and HTML reconciliation reports to the governed landing volume. PDF conversion remains a deployment decision because the approved rendering service is not defined in the source specifications.

# COMMAND ----------

# DBTITLE 1,Generate retained DVR reports
import csv
import html
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from pyspark.sql import functions as F

# Job parameters; interactive runs default to this workspace's env.
_ENV = {"adb-1700301391505163": "dev", "adb-13344226264609": "stg", "adb-642333651898149": "prd"}.get(
    spark.conf.get("spark.databricks.workspaceUrl", "").split(".")[0], "dev")
dbutils.widgets.text("catalog", f"{_ENV}_banking_and_payments_cat", "Catalog")
dbutils.widgets.text("reports_root", f"/Volumes/{_ENV}_raw_cat/restricted_db/vol_internal_swift/reports", "Reports root")
dbutils.widgets.text("report_date", "", "Report date (YYYY-MM-DD)")
dbutils.widgets.text("valid_files_json", "", "Current run valid files")
CATALOG = dbutils.widgets.get("catalog")
REPORTS_ROOT = dbutils.widgets.get("reports_root").rstrip("/")
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
RECON_TABLE = f"{CATALOG}.derived_db.tbl_swift_habs_recon_results_fact"

# Validate ran in this job but passed no files: no new reports. Without this,
# the date fallback below rewrites reports from earlier runs. An empty value
# means an interactive run, which keeps the date fallback.
if valid_files_json and not valid_files:
    print("No valid files in this run; reports not generated.")
    dbutils.jobs.taskValues.set(key="status", value="SKIPPED")
    dbutils.notebook.exit(str({
        "report_date": REPORT_DATE, "report_root": REPORTS_ROOT, "rows": 0,
        "files": [], "reports": [], "skipped": "No valid files in this run",
    }))

# Select this run's reconciliation rows by the job run ID that 04_reconcile
# stamped on them (md_workflow_execution_skey). This keeps runs separate even
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
    recon_all.where(F.col("md_workflow_execution_skey") == F.lit(int(JOB_RUN_ID)))
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
).orderBy("inbound_outbound_ind", "transaction_reference", "swift_gen_message_type")
rows = [row.asDict(recursive=True) for row in report_df.collect()]
os.makedirs(REPORTS_ROOT, exist_ok=True)


def write_xlsx(path, columns, data_rows):
    """Write a dependency-free XLSX workbook containing one worksheet."""
    def cell(value, row_number, column_number):
        column = ""
        number = column_number
        while number:
            number, remainder = divmod(number - 1, 26)
            column = chr(65 + remainder) + column
        text = "" if value is None else str(value)
        return (
            f'<c r="{column}{row_number}" t="inlineStr">'
            f"<is><t>{xml_escape(text)}</t></is></c>"
        )

    sheet_rows = []
    header = "".join(cell(column, 1, index) for index, column in enumerate(columns, 1))
    sheet_rows.append(f'<row r="1">{header}</row>')
    for row_number, data in enumerate(data_rows, 2):
        values = [data.get(column, "") for column in columns]
        sheet_rows.append(
            f'<row r="{row_number}">'
            + "".join(cell(value, row_number, index) for index, value in enumerate(values, 1))
            + "</row>"
        )

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Reconciliation" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook_relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    # Unity Catalog Volumes can reject zipfile's seek/close operations when an
    # XLSX is created directly on the mounted volume. Build locally first,
    # close the ZIP completely, then copy the finished file to the volume.
    temporary_path = tempfile.mktemp(suffix=".xlsx")
    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as workbook:
            workbook.writestr("[Content_Types].xml", content_types)
            workbook.writestr("_rels/.rels", relationships)
            workbook.writestr("xl/workbook.xml", workbook_xml)
            workbook.writestr("xl/_rels/workbook.xml.rels", workbook_relationships)
            workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        shutil.copyfile(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

# Only produce reports for the directions uploaded in this run (an inbound-only
# upload must not create an outbound report).
report_directions = run_directions or sorted({row.get("inbound_outbound_ind") for row in rows if row.get("inbound_outbound_ind")})
reports_written = []
for direction in report_directions:
    direction_rows = [row for row in rows if row.get("inbound_outbound_ind") == direction]
    stem = f"Swift_HABS_DVR_{direction}_{REPORT_DATE}"
    xlsx_path = os.path.join(REPORTS_ROOT, f"{stem}.xlsx")
    html_path = os.path.join(REPORTS_ROOT, f"{stem}.html")

    columns = [
        "report_date", "inbound_outbound_ind", "transaction_reference",
        "swift_gen_message_type", "swift_transaction_cnt", "swift_amount",
        "clob_transaction_cnt", "clob_amount", "db_transaction_cnt", "db_amount",
        "recon_result", "warning_reason",
    ]
    write_xlsx(xlsx_path, columns, direction_rows)

    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '') or ''))}</td>" for column in columns) + "</tr>"
        for row in direction_rows
    )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(stem)}</title>
<style>body{{font-family:Arial,sans-serif}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:4px;font-size:11px}}th{{background:#e8f0fe}}</style>
</head><body><h1>{html.escape(stem)}</h1><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></body></html>"""
    with open(html_path, "w", encoding="utf-8") as output:
        output.write(document)
    print(f"Wrote {len(direction_rows)} {direction} row(s): {xlsx_path}, {html_path}")
    reports_written.append({"direction": direction, "rows": len(direction_rows)})

result = {
    "report_date": REPORT_DATE,
    "report_root": REPORTS_ROOT,
    "rows": len(rows),
    "files": valid_filenames,
    "reports": reports_written,
    "formats": ["xlsx", "html"],
}
print(result)
dbutils.jobs.taskValues.set(key="status", value="PASSED")
dbutils.notebook.exit(str(result))
