# Databricks notebook source
# MAGIC %md
# MAGIC ## Raw To Standard Task
# MAGIC - Read raw files
# MAGIC - Standardize and transform
# MAGIC - Validate standardized records
# MAGIC - Load into the standardized tables

# COMMAND ----------

# DBTITLE 1,Show widget for development input
# Development-only widgets.
dbutils.widgets.text("debug", "True")

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../../common

# COMMAND ----------

# DBTITLE 1,Import libraries
# Standard-library imports
import logging
from datetime import date

# DataKit library imports
from oeds.core.df_utils import normalize_column_names, normalize_nulls, select_columns
from oeds.core.df_validator import Rules, validate_df
from oeds.core.file_reader import load_file_failfast
from oeds.core.uc_utils import delta_batch_update
from pyspark.sql import functions as F

# OEDS domain-specific imports
from oeds.domain.exceptions import RawToStdTaskError
from oeds.domain.utils.datafile import DatafileManager
from oeds.domain.utils.operation import OperationStatusManager

# COMMAND ----------

# DBTITLE 1,Init logging and context
logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Read Raw Files
# MAGIC - Read source files from raw zone
# MAGIC - Apply the expected schema and file options

# COMMAND ----------

# DBTITLE 1,Prepare raw file inputs
# Reuse the date selected by the main task so all stages process the same batch.
file_date = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="file_date",
    debugValue=date.today().isoformat(),
)
# The task owns the batch-date segment below the configured raw zone root.
raw_root = job_ctx.get("raw_root")
raw_file_ref = "file_sample"

logger.info("Reading raw file '%s' for file_date '%s'", raw_file_ref, file_date)

# COMMAND ----------

# DBTITLE 1,Read raw file
try:
    datafile_manager = DatafileManager.get_instance()
    # The datafile registry owns the relative path, format, schema, and reader options.
    raw_file_config = datafile_manager.find(raw_file_ref)
    raw_file_path = (
        f"{str(raw_root).rstrip('/')}/{str(file_date).strip('/')}/"
        f"{str(raw_file_config.path).lstrip('/')}"
    )
    logger.info("Resolved raw file '%s' to '%s'", raw_file_ref, raw_file_path)

    # Materialize the read inside the helper so malformed input fails in this task.
    raw_df = load_file_failfast(
        raw_file_path,
        raw_file_config.format,
        schema=raw_file_config.schema,
        options=raw_file_config.options,
    )
except Exception as exc:
    logger.exception(
        "Failed to read raw file '%s' for file_date '%s'",
        raw_file_ref,
        file_date,
    )
    raise RawToStdTaskError(
        f"Failed to read raw file '{raw_file_ref}' for file_date '{file_date}'"
    ) from exc

# COMMAND ----------

# DBTITLE 1,Capture source file path
try:
    # Promote hidden file metadata before later projections remove access to it.
    raw_df = raw_df.withColumn(
        "audit_source_file_path",
        F.col("_metadata.file_path").cast("string"),
    )
    logger.info("Captured source file path for raw records")
except Exception as exc:
    logger.exception("Failed to capture source file path from raw file metadata")
    raise RawToStdTaskError("Failed to capture source file path") from exc

# COMMAND ----------

# MAGIC %md
# MAGIC ### Standardize and Transform
# MAGIC - Rename and select required columns.
# MAGIC - Normalize nulls, strings, dates, and timestamps.
# MAGIC - Convert columns to target data types.
# MAGIC - Map codes and derive required fields.

# COMMAND ----------

# DBTITLE 1,Normalize column names
standardized_df = normalize_column_names(
    raw_df,
    lowercase=True,
    replace_spaces=True,
    replace_hyphens=True,
    remove_special=True,
    collapse_underscores=True,
    strip_underscores=True,
)

# COMMAND ----------

# DBTITLE 1,Select standardized columns
standardized_df = select_columns(
    standardized_df,
    [
        "number",
        "category",
        "country",
        "amount",
        "minimum_amount",
        "audit_source_file_path",
    ],
)

# COMMAND ----------

# DBTITLE 1,Normalize null values
standardized_df = normalize_nulls(
    standardized_df,
    null_values=["", "N/A", "NA", "NULL", "None"],
)

# COMMAND ----------

# DBTITLE 1,Add audit columns
# This sample's idempotent batch load requires both audit identifiers.
audit_batch_id = str(file_date).strip()
audit_load_id = str(job_ctx.get("job_run_id") or "").strip()
if not audit_batch_id:
    raise RawToStdTaskError("file_date is required for audit_batch_id")
if not audit_load_id:
    raise RawToStdTaskError("job_run_id is required for audit_load_id")

try:
    # Reuse one expression so both audit timestamps have the same value.
    audit_timestamp = F.current_timestamp()
    standardized_df = standardized_df.select(
        "number",
        "category",
        "country",
        "amount",
        "minimum_amount",
        F.lit(audit_batch_id).cast("string").alias("audit_batch_id"),
        F.lit(audit_load_id).cast("string").alias("audit_load_id"),
        audit_timestamp.alias("audit_created_ts"),
        audit_timestamp.alias("audit_last_update_ts"),
        F.col("audit_source_file_path").cast("string").alias("audit_source_file_path"),
    )
    logger.info(
        "Added UC audit columns for batch '%s' and load '%s'",
        audit_batch_id,
        audit_load_id,
    )
except Exception as exc:
    logger.exception(
        "Failed to add UC audit columns for batch '%s' and load '%s'",
        audit_batch_id,
        audit_load_id,
    )
    raise RawToStdTaskError(
        "Failed to add UC audit columns to standardized data"
    ) from exc

# COMMAND ----------

# MAGIC %md
# MAGIC ### Business Validation
# MAGIC - Apply business validation rules.
# MAGIC - Fail the task when standardized records violate required business rules.

# COMMAND ----------

# DBTITLE 1,Validate records
business_rules = [
    Rules.not_null("number", name="number_required"),
    Rules.unique("number", name="number_unique"),
    Rules.not_null("category", name="category_required"),
    Rules.in_set(
        "category",
        ["retail", "enterprise", "public"],
        name="category_supported",
    ),
    Rules.not_null("country", name="country_required"),
    Rules.in_set("country", ["CA", "US"], name="country_supported"),
    Rules.not_null("amount", name="amount_required"),
    Rules.not_null("minimum_amount", name="minimum_amount_required"),
    Rules.gte_col("amount", "minimum_amount", name="amount_meets_minimum"),
]

try:
    business_validation_result = validate_df(standardized_df, business_rules)
except Exception as exc:
    logger.exception("Failed to execute business validation")
    raise RawToStdTaskError("Failed to execute business validation") from exc

if not business_validation_result.success:
    failed_expectations = [
        result.expectation
        for result in business_validation_result.results
        if not result.success
    ]
    logger.error(
        "Business validation failed for %s rule(s): %s",
        len(failed_expectations),
        ", ".join(failed_expectations),
    )
    raise RawToStdTaskError(
        f"Business validation failed for {len(failed_expectations)} rule(s): "
        f"{', '.join(failed_expectations)}"
    )

logger.info("Business validation passed for %s rules", len(business_rules))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Load Standardized Tables
# MAGIC - Append or merge records into the Delta table.
# MAGIC - Write audit metrics and confirm the load succeeded.

# COMMAND ----------

# DBTITLE 1,Load standardized table
standardized_table_ref = "tbl_sample"

try:
    standardized_table = SchemaManager.get_instance().find(standardized_table_ref)
    logger.info(
        "Loading standardized batch '%s' from load '%s' into '%s'",
        audit_batch_id,
        audit_load_id,
        standardized_table.full_name,
    )

    # Replace the logical batch atomically so retries do not duplicate records.
    delta_batch_update(
        standardized_df,
        standardized_table.full_name,
        mode="replace",
        batch_column="audit_batch_id",
        batch_id=audit_batch_id,
    )
    logger.info(
        "Loaded standardized batch '%s' from load '%s' into '%s'",
        audit_batch_id,
        audit_load_id,
        standardized_table.full_name,
    )
except Exception as exc:
    logger.exception(
        "Failed to load standardized table '%s' for batch '%s' from load '%s'",
        standardized_table_ref,
        audit_batch_id,
        audit_load_id,
    )
    raise RawToStdTaskError(
        f"Failed to load standardized table '{standardized_table_ref}' "
        f"for batch '{audit_batch_id}'"
    ) from exc

# COMMAND ----------

# DBTITLE 1,Record successful standardization
# Persist the marker only after the Delta batch replacement commits.
try:
    OperationStatusManager().record_status(
        dataset=job_ctx["dataset"],
        layer="standardization",
        batch_id=audit_batch_id,
        job_run_id=job_ctx.get("job_run_id"),
        job_name=job_ctx.get("job_name"),
        job_id=job_ctx.get("job_id"),
        job_trigger_type=job_ctx.get("job_trigger_type"),
        job_context=job_ctx,
    )
except Exception as exc:
    logger.exception(
        "Loaded standardized table '%s' for batch '%s', but failed to record "
        "the successful operation",
        standardized_table_ref,
        audit_batch_id,
    )
    raise RawToStdTaskError(
        f"Loaded standardized table '{standardized_table_ref}' for batch "
        f"'{audit_batch_id}', but failed to record the successful operation"
    ) from exc
