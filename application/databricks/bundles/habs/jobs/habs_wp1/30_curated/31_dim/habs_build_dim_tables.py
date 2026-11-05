# Databricks notebook source
# MAGIC %run ../../../../common

# COMMAND ----------
# Standard libraries
if dbutils.widgets.get("build_dim") != "1":
    logger.info("Skipping RAW build.")
    dbutils.notebook.exit("SKIPPED")


import logging
import concurrent.futures
import runpy
import time
from pathlib import Path

job_ctx = get_job_context()
logger = logging.getLogger(__name__)
logger.debug(f"job_ctx: {job_ctx}")

logger.info("Starting dimension table updates...")

# COMMAND ----------

MAX_PARALLELISM = 8

tables_folder = Path("tables")

scripts = sorted(
    p for p in tables_folder.glob("*.py")
    if p.name != "__init__.py"
)

logger.info(f"Found {len(scripts)} dimension notebook(s).")

# COMMAND ----------


import copy

def run_dimension(script: Path):

    start = time.time()

    logger.info(f"START: {script.name}")

    script_logger = logging.getLogger(script.stem)

    runpy.run_path(
        str(script),
        run_name="__main__",
        init_globals={
            "job_ctx": copy.deepcopy(job_ctx),
            "logger": script_logger,
            "spark": spark,
        },
    )

    elapsed = time.time() - start

    logger.info(f"END: {script.name} ({elapsed:.1f}s)")

# COMMAND ----------

with concurrent.futures.ThreadPoolExecutor(
    max_workers=MAX_PARALLELISM
) as executor:

    futures = [
        executor.submit(run_dimension, script)
        for script in scripts
    ]

    for future in concurrent.futures.as_completed(futures):
        future.result()

logger.info("All dimension tables completed successfully.")
