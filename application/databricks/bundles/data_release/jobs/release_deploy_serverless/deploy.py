# Databricks notebook source
# Self-contained for serverless compute — no dependency on common/oeds.

# COMMAND ----------
import logging
import concurrent.futures
from databricks.sdk import WorkspaceClient
from rules import get_step

# COMMAND ----------
dbutils.widgets.text("catalog", "")
dbutils.widgets.text("release_version", "")
dbutils.widgets.text("max_parallelism", "")
dbutils.widgets.text("stage", "")
dbutils.widgets.text("sql_warehouse_id", "")
dbutils.widgets.text("debug", "false")

catalog = dbutils.widgets.get("catalog")
release_version = dbutils.widgets.get("release_version")
max_parallelism = int(dbutils.widgets.get("max_parallelism"))
stage_name = dbutils.widgets.get("stage")
sql_warehouse_id = dbutils.widgets.get("sql_warehouse_id")
debug = dbutils.widgets.get("debug").strip().lower() in ("true", "1", "yes", "y")

# COMMAND ----------
# Simple standalone logging setup — replaces oeds.core.log_utils.setup_logger
logging.basicConfig(
    level=logging.DEBUG if debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# COMMAND ----------
if not catalog:
    raise ValueError("catalog is required")
if not release_version:
    raise ValueError("release_version is required")
if not stage_name:
    raise ValueError("stage is required")
if not sql_warehouse_id:
    raise ValueError("sql_warehouse_id is required")

logger.info(f"Catalog          : {catalog}")
logger.info(f"Release Version  : {release_version}")
logger.info(f"Stage            : {stage_name}")
logger.info(f"Parallelism      : {max_parallelism}")

# COMMAND ----------
step = get_step(release_version, stage_name)
logger.info(f"Files            : {len(step.files)}")

# COMMAND ----------
_w_client = None

def get_workspace_client() -> WorkspaceClient:
    global _w_client
    if _w_client is None:
        _w_client = WorkspaceClient()
    return _w_client


def run_statement(statement: str, label: str):
    logger.info(f"START: {label}")

    w = get_workspace_client()
    resp = w.statement_execution.execute_statement(
        warehouse_id=sql_warehouse_id,
        statement=statement,
        catalog=catalog,
        wait_timeout="50s",
    )

    if resp.status.state.value != "SUCCEEDED":
        raise RuntimeError(
            f"Statement failed for {label}: "
            f"state={resp.status.state.value}, error={resp.status.error}"
        )

    logger.info(f"END: {label}")


def run_sql_file(file_path: str):
    with open(file_path, "r") as f:
        sql_text = f.read()

    statements = [s.strip() for s in sql_text.split(";") if s.strip()]

    if not statements:
        logger.info(f"No statements found in {file_path}, skipping")
        return

    for i, stmt in enumerate(statements):
        run_statement(stmt, label=f"{file_path} [stmt {i+1}/{len(statements)}]")

# COMMAND ----------
if not step.files:
    logger.info(f"No files found for stage '{step.name}', nothing to do.")
else:
    logger.info(f"===== START STAGE: {step.name} =====")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallelism) as executor:
        futures = [executor.submit(run_sql_file, f) for f in step.files]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    logger.info(f"===== END STAGE: {step.name} =====")
    