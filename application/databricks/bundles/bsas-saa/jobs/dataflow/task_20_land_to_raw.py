# Databricks notebook source
# MAGIC %md
# MAGIC ## Land To Raw Task
# MAGIC - Read the shared processing date from task values
# MAGIC - Resolve landing and raw storage paths
# MAGIC - Copy landed files into the raw zone by file pattern

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
from datetime import date, datetime  # noqa: F401
from pathlib import Path

# DataKit library imports
import oeds.core.file_utils as fileutils
from oeds.core.file_validator import (
    find_files,
    validate_file_count,
    validate_non_empty_files,
)

# OEDS domain-specific imports
from oeds.domain.exceptions import LandToRawTaskError

# COMMAND ----------

# DBTITLE 1,Init logging and context
logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Prepare Land To Raw Parameters
# MAGIC - Read the processing date prepared by the main task
# MAGIC - Build the landing and raw directories

# COMMAND ----------

# file_date is the shared processing date from the main task.
file_date = dbutils.jobs.taskValues.get(
    taskKey="main", key="file_date", debugValue=date.today().isoformat()
)
logger.info(f"file_date: {file_date}")

# land_dir identifies the landing batch to validate and copy.
land_dir_default = str(Path(job_ctx.get("land_root")) / file_date)
land_dir = dbutils.jobs.taskValues.get(
    taskKey="main", key="land_dir", debugValue=land_dir_default
)
logger.info(f"land_dir: {land_dir}")

# raw_dir identifies the destination batch in the raw zone.
raw_dir_default = str(Path(job_ctx.get("raw_root")) / file_date)
raw_dir = dbutils.jobs.taskValues.get(
    taskKey="main", key="raw_dir", debugValue=raw_dir_default
)
logger.info(f"raw_dir: {raw_dir}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Validate Landed Files
# MAGIC Optional validation. Remove the following block if validation is not required.
# MAGIC Validate landing files one rule at a time. Each result can fail the task
# MAGIC independently or allow validation to continue.

# COMMAND ----------

# Find matching files under the landing directory.
try:
    landed_files = find_files(land_dir, pattern="*", recursive=True)
except Exception as exc:
    logger.error(f"Failed to find landed files under {land_dir}. {exc}")
    raise LandToRawTaskError(
        f"Failed to find landed files under {land_dir}. {exc}"
    ) from exc

try:
    # Validate that the landing batch contains at least one file.
    file_count_result = validate_file_count(landed_files, minimum_count=1)
    if not file_count_result.success:
        raise LandToRawTaskError(file_count_result.error_message)

    # Validate that every discovered file contains data.
    non_empty_result = validate_non_empty_files(landed_files)
    if not non_empty_result.success:
        logger.debug(
            "Empty landed files: %s", [file.path for file in non_empty_result.files]
        )
        raise LandToRawTaskError(non_empty_result.error_message)
except LandToRawTaskError:
    raise
except Exception as exc:
    logger.error(f"Failed to validate landed files under {land_dir}. {exc}")
    raise LandToRawTaskError(
        f"Failed to validate landed files under {land_dir}. {exc}"
    ) from exc

# COMMAND ----------

# MAGIC %md
# MAGIC ### Copy Landed Files To Raw
# MAGIC Copy the validated landing batch into the raw zone while preserving its
# MAGIC subdirectory structure.

# COMMAND ----------

try:
    logger.info("Copying files from %s to %s", land_dir, raw_dir)
    copied_files = fileutils.copy_selected_files(
        land_dir,
        raw_dir,
        pattern="*",
        recursive=True,
    )
except Exception as exc:
    logger.error(f"Failed to copy files from {land_dir} to {raw_dir}. {exc}")
    raise LandToRawTaskError(
        f"Failed to copy files from {land_dir} to {raw_dir}. {exc}"
    ) from exc

logger.info("Copied %s file(s) from %s to %s", len(copied_files), land_dir, raw_dir)
