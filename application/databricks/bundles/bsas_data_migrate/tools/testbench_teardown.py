# Databricks notebook source
# MAGIC %md
# MAGIC ## Tear down a Testbench case
# MAGIC Run this notebook directly to remove the resources configured by a
# MAGIC Testbench case.
# MAGIC
# MAGIC The `args` widget accepts:
# MAGIC ```json
# MAGIC {
# MAGIC   "case_name": "default",
# MAGIC   "rundate": "2026-06-01"
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC `case_name` defaults to `default`, and `case_root` defaults to the
# MAGIC bundle's configured value. Other properties, such as `rundate`, must
# MAGIC match the values used when the case resources were created.

# COMMAND ----------

# DBTITLE 1,Development parameters
dbutils.widgets.text("debug", "True")
dbutils.widgets.text(
    "args",
    '{"case_name":"default","rundate":"2026-06-01"}',
)

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Load case and tear down resources
import logging
from typing import Any

from oeds.domain.utils.testbench.config import load_test_case
from oeds.domain.utils.testbench.environment import ResourceUtils

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
case_name_value = args.get("case_name", "default")
if not isinstance(case_name_value, str):
    raise TypeError("args.case_name must be a string")
case_name = case_name_value.strip()
if not case_name:
    raise ValueError("args.case_name cannot be blank")

test_config = load_test_case(
    case_name=case_name,
    case_root=case_root,
    context=args,
)
ResourceUtils(case_root=case_root).drop_resources(test_config)
logger.info("Completed Testbench teardown for case '%s'", case_name)
