# Databricks notebook source
# MAGIC %md
# MAGIC ## Load files from file load mappings
# MAGIC Use this tool to load files from the landing zone into tables for initial data population or reference-table updates.
# MAGIC
# MAGIC Run the job with following parameters:
# MAGIC - task: tools/load_file
# MAGIC - args: {"ref":"load_sample","mode":"overwrite","file_base_uri":""}
# MAGIC
# MAGIC `args` parameters:
# MAGIC - `ref`: Required file-load mapping reference.
# MAGIC - `mode`: Optional write-mode override (`append` or `overwrite`). Leave empty to use each mapping's configured mode.
# MAGIC - `file_base_uri`: Optional base URI joined to the configured datafile
# MAGIC   path. Leave empty to use the job's `land_root`.

# COMMAND ----------

# DBTITLE 1,Widgets for Development parameters
# For development only
dbutils.widgets.text("debug", "True")
dbutils.widgets.text(
    "args",
    '{"ref":"load_sample","mode":"overwrite","file_base_uri":""}',
)

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Get job context
# Standard libraries
import json
import logging

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context with keys: %s", sorted(job_ctx))

# COMMAND ----------

from oeds.domain.utils.fileloader import FileLoader

# Parse parameters
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")
logger.debug(f"args: {args}")
ref = str(args.get("ref") or "").strip()
logger.info(f"ref is {ref}")
if not ref:
    raise ValueError("args.ref is required")
mode = str(args.get("mode") or "").strip() or None
logger.info(f"mode is {mode}")
file_base_uri = str(args.get("file_base_uri") or "").strip() or None
logger.info(f"file_base_uri is {file_base_uri}")
land_root = str(job_ctx.get("land_root") or "").strip().rstrip("/") or None
effective_file_base_uri = file_base_uri or land_root
logger.info(f"effective_file_base_uri is {effective_file_base_uri}")
file_loader = FileLoader.initialize(job_ctx.get("env")).get_instance()

# Load file
file_loader.load_file(
    ref=ref,
    file_base_uri=effective_file_base_uri,
    mode=mode,
    context=job_ctx,
)

result = {"tool": "load_file", "status": "completed", "ref": ref}
logger.info("Completed file load for ref '%s'", ref)
dbutils.notebook.exit(json.dumps(result))
