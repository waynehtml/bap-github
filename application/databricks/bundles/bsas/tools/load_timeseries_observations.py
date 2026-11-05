# Databricks notebook source
# MAGIC %md
# MAGIC ## Load time-series observations
# MAGIC Load one bounded CSV file into a configured time-series table.
# MAGIC
# MAGIC Run the SERVICE job with the following parameters:
# MAGIC - task: `tools/load_timeseries_observations`
# MAGIC - args: `{"file_path":"/Volumes/catalog/schema/volume/observations.csv",`
# MAGIC   `"tbl_ref":"tbl_ts"}`
# MAGIC
# MAGIC Optional `args` parameters:
# MAGIC - `time_series_name_col`: Source series-name column. Defaults to
# MAGIC   `time_series_name`.
# MAGIC - `date_col`: Source observation-date column. Defaults to `date`.
# MAGIC - `observation_col`: Source value or missing-label column. Defaults to
# MAGIC   `observation`.
# MAGIC - `date_format`: Python `datetime.strptime` format. Defaults to `%Y-%m-%d`.
# MAGIC
# MAGIC Default CSV shape:
# MAGIC ```csv
# MAGIC time_series_name,date,observation
# MAGIC template.ts1#boc,2026-08-24,4.25
# MAGIC template.ts2#boc,2026-08-24,ND
# MAGIC ```
# MAGIC Observation labels `ND`, `NA`, and `NC` are matched case-insensitively.

# COMMAND ----------

# DBTITLE 1,Development parameters
# For development only.
dbutils.widgets.text("debug", "True")
dbutils.widgets.text(
    "args",
    '{"file_path":"/Volumes/catalog/schema/volume/observations.csv",'
    '"tbl_ref":"tbl_ts"}',
)

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Imports and runtime context
import json
import logging
from datetime import datetime
from typing import Any

from oeds.core.file_reader import load_file_failfast
from oeds.domain.utils.schema.schema_utils import SchemaManager
from oeds.domain.utils.timeseries import TimeSeriesUtils

logger = logging.getLogger(__name__)
job_ctx = get_job_context()

# Keep the external CSV contract in one place so argument defaults, validation,
# and documentation use the same canonical column names and date format.
_DEFAULT_TIME_SERIES_NAME_COL = "time_series_name"
_DEFAULT_DATE_COL = "date"
_DEFAULT_OBSERVATION_COL = "observation"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d"

# These are the only nonnumeric observation tokens supported by the time-series
# data contract. Input matching is case-insensitive, but stored labels are upper
# case so downstream consumers receive one consistent representation.
_MISSING_VALUE_LABELS = {"ND", "NA", "NC"}

# COMMAND ----------


def _required_string_arg(args: dict[str, Any], name: str) -> str:
    """Return a normalized required string argument.

    A missing property and a property with a non-string value are kept as
    different failures so callers can distinguish an incomplete request from a
    request containing the wrong JSON type.
    """
    value = args.get(name)
    if not isinstance(value, str):
        raise TypeError(f"args.{name} must be a string")

    # Normalize surrounding whitespace once. Downstream file and registry
    # lookups should never depend on accidental spaces in SERVICE parameters.
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"args.{name} is required")

    return normalized_value


def _optional_string_arg(
    args: dict[str, Any],
    name: str,
    default: str,
) -> str:
    """Return a normalized optional string argument or its documented default.

    The default applies only when the property is omitted. An explicitly blank
    value is rejected because silently replacing it can hide a misspelled or
    incorrectly populated SERVICE argument.
    """
    if name not in args:
        return default

    value = args[name]
    if not isinstance(value, str):
        raise TypeError(f"args.{name} must be a string")

    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"args.{name} must not be blank")

    return normalized_value


def _parse_observation(
    raw_observation: Any,
    *,
    record_number: int,
) -> tuple[float | None, str | None]:
    """Parse one CSV observation into the time-series write representation.

    Returns a numeric value with no label, or ``None`` with a normalized missing
    label. The record number is included only in validation errors and is never
    used as part of the persisted observation.
    """
    # Spark CSV values may be strings or None. Converting here gives blank cells,
    # whitespace-only cells, numeric text, and missing-value labels one explicit
    # normalization path.
    observation_text = (
        str(raw_observation).strip() if raw_observation is not None else ""
    )
    if not observation_text:
        raise ValueError(f"CSV record {record_number} observation is required")

    # Check labels before numeric conversion. A supported label represents a
    # missing numeric value and is stored separately as observation_str by
    # TimeSeriesUtils.write_observations.
    normalized_label = observation_text.upper()
    if normalized_label in _MISSING_VALUE_LABELS:
        return None, normalized_label

    # Every remaining value must satisfy Python's floating-point parser. Keeping
    # conversion here ensures all numeric observations passed to the utility are
    # floats, regardless of how Spark represented the original CSV field.
    try:
        return float(observation_text), None
    except ValueError as exc:
        supported_labels = ", ".join(sorted(_MISSING_VALUE_LABELS))
        raise ValueError(
            f"CSV record {record_number} observation must be numeric or one of: "
            f"{supported_labels}"
        ) from exc


# COMMAND ----------

# DBTITLE 1,Parse and validate tool arguments
# SERVICE supplies args as JSON text. Reject arrays, scalars, and null before
# reading named properties so every later lookup operates on a mapping.
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

file_path = _required_string_arg(args, "file_path")
tbl_ref = _required_string_arg(args, "tbl_ref")
time_series_name_col = _optional_string_arg(
    args,
    "time_series_name_col",
    _DEFAULT_TIME_SERIES_NAME_COL,
)
date_col = _optional_string_arg(args, "date_col", _DEFAULT_DATE_COL)
observation_col = _optional_string_arg(
    args,
    "observation_col",
    _DEFAULT_OBSERVATION_COL,
)
date_format = _optional_string_arg(args, "date_format", _DEFAULT_DATE_FORMAT)

# The three semantic fields must come from three different source columns. If
# two arguments name the same column, Spark could alias one source value into
# multiple meanings and produce records that look valid but are incorrect.
selected_columns = (time_series_name_col, date_col, observation_col)
if len(set(selected_columns)) != len(selected_columns):
    raise ValueError(
        "time_series_name_col, date_col, and observation_col must be distinct"
    )

# Validate the format itself before resolving the table or reading the file. A
# round trip catches unsupported strptime directives even on platforms whose
# strftime implementation leaves an unknown directive unchanged.
try:
    date_format_sample = datetime.now().astimezone().strftime(date_format)
    datetime.strptime(date_format_sample, date_format)
except ValueError as exc:
    raise ValueError(f"args.date_format is invalid: {date_format}") from exc

# tbl_ref is intentionally a schema-registry reference rather than an arbitrary
# table name. find() supplies the fully qualified destination and raises for an
# unknown reference; this tool performs no additional destination-schema audit.
schema_registry = SchemaManager.get_instance().find(tbl_ref)
full_table_name = schema_registry.full_name
logger.info(
    "Loading time-series observations from '%s' into table ref '%s' resolved "
    "as '%s'",
    file_path,
    tbl_ref,
    full_table_name,
)

# COMMAND ----------

# DBTITLE 1,Read and validate the CSV file
# Disable schema inference so Spark preserves source values as strings. This is
# important for missing labels and prevents Spark from deciding a mixed numeric
# and label column has an unintended inferred type.
csv_df = load_file_failfast(
    file_path,
    "csv",
    options={
        "header": "true",
        "inferSchema": "false",
    },
)

# Validate the exact configured header names before selecting columns. Extra CSV
# columns are harmless and intentionally ignored, but every configured semantic
# column must exist exactly as named.
missing_columns = [
    column_name
    for column_name in selected_columns
    if column_name not in csv_df.columns
]
if missing_columns:
    raise ValueError(
        "CSV file is missing configured column(s): "
        f"{', '.join(missing_columns)}"
    )

# Select only the three required fields and give them canonical internal names.
# collect() is deliberate: this tool accepts a bounded CSV and must validate the
# complete batch before TimeSeriesUtils is allowed to create an audit record.
source_rows = csv_df.select(
    csv_df[time_series_name_col].alias("time_series_name"),
    csv_df[date_col].alias("date"),
    csv_df[observation_col].alias("observation"),
).collect()
if not source_rows:
    raise ValueError("CSV file must contain at least one observation record")

logger.info("Read %s time-series observation record(s)", len(source_rows))

# COMMAND ----------

# DBTITLE 1,Convert CSV rows to observation records
# Build ordinary dictionaries matching the public TimeSeriesObservation shape.
# Nothing is written in this loop, so any invalid row rejects the entire batch
# before an audit record or destination-table append can occur.
observations: list[dict[str, Any]] = []
for record_number, source_row in enumerate(source_rows, start=1):
    # Series identity is required for every row. Normalize whitespace here so
    # the same identity is used for validation, storage, and transaction logs.
    time_series_name = (
        str(source_row["time_series_name"]).strip()
        if source_row["time_series_name"] is not None
        else ""
    )
    if not time_series_name:
        raise ValueError(
            f"CSV record {record_number} time-series name is required"
        )

    # CSV dates are required even though write_observations supports a default
    # date. A loader row must be explicit so an omitted source date cannot be
    # silently replaced with the day on which the job happens to run.
    date_text = (
        str(source_row["date"]).strip()
        if source_row["date"] is not None
        else ""
    )
    if not date_text:
        raise ValueError(f"CSV record {record_number} date is required")

    # parse_date returns a date object expected by TimeSeriesObservation. Wrap
    # its error with the CSV record number and caller-selected format so a bad
    # row can be corrected without exposing any observation value in logs.
    try:
        observation_date = parse_date(date_text, date_format)
    except ValueError as exc:
        raise ValueError(
            f"CSV record {record_number} has an invalid date '{date_text}' "
            f"for format '{date_format}'"
        ) from exc

    # Numeric text becomes a float. Supported missing labels become a None value
    # plus an uppercase label, which TimeSeriesUtils stores in observation_str.
    observation_value, missing_value_label = _parse_observation(
        source_row["observation"],
        record_number=record_number,
    )
    # Include the label only for a missing numeric observation. Omitting it for
    # numeric rows preserves TimeSeriesUtils behavior where observation_str is
    # left unset for values that can be stored numerically.
    observation: dict[str, Any] = {
        "time_series_name": time_series_name,
        "value": observation_value,
        "date": observation_date,
    }
    if missing_value_label is not None:
        observation["missing_value_label"] = missing_value_label

    observations.append(observation)

# COMMAND ----------

# DBTITLE 1,Write one observation batch
# TimeSeriesUtils passes this runtime metadata to its manager when it creates the
# audit and transaction records. It describes the job, not the observation data.
timeseries_context = {
    "metadata_catalog": job_ctx.get("metadata_catalog"),
    "pipeline_name": job_ctx.get("job_name"),
    "notebook_path": job_ctx.get("current_notebook_path"),
    "current_user": job_ctx.get("current_user"),
    "job_id": job_ctx.get("job_id"),
    "job_runid": job_ctx.get("job_run_id"),
    "job_trigger_type": job_ctx.get("job_trigger_type"),
}
timeseries_utils = TimeSeriesUtils(tsm_ctx=timeseries_context)

# This is the only persistence call. Passing the complete validated list once
# produces one audit key and prevents row-by-row partial loads.
metadata_audit_skey = timeseries_utils.write_observations(
    observations=observations,
    full_table_name=full_table_name,
)

# COMMAND ----------

# DBTITLE 1,Return compact tool result
# Return identifiers and counts needed for orchestration and troubleshooting.
# Observation values are deliberately excluded from both this payload and logs.
result = {
    "tool": "load_timeseries_observations",
    "status": "completed",
    "file_path": file_path,
    "tbl_ref": tbl_ref,
    "full_table_name": full_table_name,
    "record_count": len(observations),
    "metadata_audit_skey": metadata_audit_skey,
}
logger.info(
    "Loaded %s time-series observation record(s) with metadata audit skey '%s'",
    result["record_count"],
    metadata_audit_skey,
)
dbutils.notebook.exit(json.dumps(result))
