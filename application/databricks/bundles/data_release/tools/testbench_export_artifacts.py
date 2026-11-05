# Databricks notebook source
# MAGIC %md
# MAGIC ## Export a Testbench table artifact
# MAGIC Run this notebook directly to export one configured fixture or expected
# MAGIC dataset from a Testbench case.
# MAGIC
# MAGIC The `args` widget accepts:
# MAGIC ```json
# MAGIC {
# MAGIC   "artifact_name": "customer_fixture",
# MAGIC   "overwrite": false,
# MAGIC   "rundate": "2026-06-01"
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC `artifact_name` is required. `case_name` defaults to `default`,
# MAGIC `case_root` defaults to the bundle's configured value, and `overwrite`
# MAGIC defaults to `false`. Other properties, such as `rundate`, override
# MAGIC matching variables declared by the selected case.

# COMMAND ----------

# DBTITLE 1,Development parameters
dbutils.widgets.text("debug", "True")
dbutils.widgets.text(
    "args",
    '{"artifact_name":"customer_fixture","overwrite":true,'
    '"rundate":"2026-06-01"}',
)

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Load case and export artifact
import logging
from dataclasses import asdict
from typing import Any

from oeds.domain.utils.testbench.artifact import TableArtifactExporter
from oeds.domain.utils.testbench.config import load_test_case

logger = logging.getLogger(__name__)
job_ctx = get_job_context()


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{name} is required")
    return normalized_value


args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

case_root_value = (
    args["case_root"] if "case_root" in args else job_ctx.get("case_root")
)
case_root = _required_string(case_root_value, "case_root")
artifact_name = _required_string(args.get("artifact_name"), "args.artifact_name")
case_name_value = args.get("case_name", "default")
if not isinstance(case_name_value, str):
    raise TypeError("args.case_name must be a string")
case_name = case_name_value.strip()
if not case_name:
    raise ValueError("args.case_name cannot be blank")
overwrite = args.get("overwrite", False)
if not isinstance(overwrite, bool):
    raise TypeError("args.overwrite must be a boolean")

test_config = load_test_case(
    case_name=case_name,
    case_root=case_root,
    context=args,
)
exporter = TableArtifactExporter(case_root=case_root)
export_result = exporter.export_configured_artifact(
    test_config=test_config,
    artifact_name=artifact_name,
    overwrite=overwrite,
)

result = {
    "tool": "testbench_export_artifacts",
    "status": "completed",
    "case_name": case_name,
    "artifact_name": artifact_name,
}
result.update(asdict(export_result))
logger.info(
    "Completed Testbench artifact '%s' from case '%s'",
    artifact_name,
    case_name,
)
logger.info("Testbench artifact export result: %s", result)
