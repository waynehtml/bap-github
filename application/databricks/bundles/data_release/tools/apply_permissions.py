# Databricks notebook source
# MAGIC %md
# MAGIC ## Apply schema permissions
# MAGIC Grant the configured Unity Catalog permissions with the permission module.
# MAGIC
# MAGIC Run the service job with following parameters:
# MAGIC - task: tools/apply_permissions
# MAGIC - args: {"schema_ref":"","execute":true,"config_file":""}
# MAGIC
# MAGIC `args` parameters:
# MAGIC - `schema_ref`: Optional schema reference. Leave empty to process every configured permission entry.
# MAGIC - `execute`: Execute the generated `GRANT` statements. Set to `false` to preview them in the logs.
# MAGIC - `config_file`: Optional packaged permission config file. Leave empty to use `default.json`.

# COMMAND ----------

# DBTITLE 1,Widgets for development parameters
# For development only
dbutils.widgets.text("debug", "True")
dbutils.widgets.text(
    "args",
    '{"schema_ref":"","execute":true,"config_file":""}',
)

# COMMAND ----------

# DBTITLE 1,Load common notebook
# MAGIC %run ../common

# COMMAND ----------

# DBTITLE 1,Get job context
import json
import logging

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("job context keys: %s", sorted(job_ctx))

# COMMAND ----------

from oeds.domain.utils.permission import PermissionManager

args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

# An empty schema reference tells the permission module to process every
# permission entry in the selected registry.
schema_ref = str(args.get("schema_ref") or "").strip() or None
config_file = str(args.get("config_file") or "").strip() or None
execute = args.get("execute", True)
if not isinstance(execute, bool):
    raise TypeError("execute must be a boolean")

# SchemaManager resolves configured references to environment-specific Unity
# Catalog object names before grants are generated.
permission_manager = PermissionManager.initialize(
    job_ctx.get("env")
).get_instance()
selected_config_file = config_file or "default.json"

logger.info(
    "Applying schema permissions: env=%s, schema_ref=%s, config_file=%s, execute=%s",
    permission_manager.env,
    schema_ref or "all",
    selected_config_file,
    execute,
)
# Preview mode follows the same resolution path but logs the GRANT statements
# without submitting them to Spark.
permission_manager.apply_permissions(
    schema=schema_ref,
    execute=execute,
    config_file=config_file,
)

# Keep the notebook output compact; detailed resolution and SQL diagnostics are
# available in the job logs.
result = {
    "tool": "apply_permissions",
    "status": "completed",
    "env": permission_manager.env,
    "schema_ref": schema_ref,
    "config_file": selected_config_file,
    "execute": execute,
}
logger.info("Apply permissions tool completed: %s", result)
dbutils.notebook.exit(json.dumps(result))
