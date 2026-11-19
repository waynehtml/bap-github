# Databricks notebook source

# COMMAND ----------
import logging
import concurrent.futures
from rules import get_steps, parse_folders, DEFAULT_FOLDERS

logger = logging.getLogger(__name__)

# COMMAND ----------
dbutils.widgets.text("catalog", "")
dbutils.widgets.text("release_version", "")
dbutils.widgets.text("max_parallelism", "")
# Comma-separated folders (relative to the release root), executed in this order.
dbutils.widgets.text("folders", ",".join(DEFAULT_FOLDERS))
dbutils.widgets.text("fmd_catalog", "")
dbutils.widgets.text("ref_catalog", "")

catalog = dbutils.widgets.get("catalog")
release_version = dbutils.widgets.get("release_version")
max_parallelism = int(dbutils.widgets.get("max_parallelism") or 4)
folders = parse_folders(dbutils.widgets.get("folders"))
fmd_catalog = dbutils.widgets.get("fmd_catalog")
ref_catalog = dbutils.widgets.get("ref_catalog")

if not catalog:
    raise ValueError("catalog is required")
if not release_version:
    raise ValueError("release_version is required")

logger.info(f"Catalog          : {catalog}")
logger.info(f"Release Version  : {release_version}")
logger.info(f"Folders (order)  : {folders}")
logger.info(f"Parallelism      : {max_parallelism}")
logger.info(f"FMD Catalog      : {fmd_catalog}")
logger.info(f"REF Catalog      : {ref_catalog}")

# COMMAND ----------
spark.sql(f"USE CATALOG {catalog}")
logger.info(f"Using catalog: {catalog}")

# COMMAND ----------
steps = get_steps(release_version, folders)
for s in steps:
    logger.info(f"{s.folder:<20}: {len(s.files)} files")

# COMMAND ----------
# Central place for token -> value substitutions available to SQL files.
# Only scripts that actually contain the placeholder are affected.
SQL_PARAMS = {
    "fmd_catalog": fmd_catalog,
    "ref_catalog": ref_catalog,
}

def apply_params(sql_text: str, file_path: str) -> str:
    for key, value in SQL_PARAMS.items():
        placeholder = f"{{{key}}}"
        if placeholder in sql_text:
            if not value:
                raise ValueError(
                    f"{file_path} requires '{placeholder}' but no value was provided "
                    f"(widget '{key}' is empty)"
                )
            sql_text = sql_text.replace(placeholder, value)
    return sql_text

def run_sql_file(file_path: str):
    """
    Execute every statement in a SQL file, in order, via Spark SQL.
    Supports multiple semicolon-separated statements per file.
    """
    logger.info(f"START: {file_path}")

    with open(file_path, "r") as f:
        sql_text = f.read()

    sql_text = apply_params(sql_text, file_path)
    
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]

    if not statements:
        logger.info(f"No statements found in {file_path}, skipping")
        return

    for i, stmt in enumerate(statements):
        logger.info(f"  RUN stmt {i+1}/{len(statements)} from {file_path}")
        spark.sql(stmt)

    logger.info(f"END: {file_path}")

# COMMAND ----------
# Folders run sequentially in the given order; files within a folder run in parallel.
for step in steps:
    if not step.files:
        logger.info(f"No files in '{step.folder}', skipping.")
        continue

    logger.info(f"===== START: {step.folder} =====")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallelism) as executor:
        futures = [executor.submit(run_sql_file, f) for f in step.files]
        for future in concurrent.futures.as_completed(futures):
            future.result()  # re-raise on failure; stops later folders
    logger.info(f"===== END: {step.folder} =====")
    