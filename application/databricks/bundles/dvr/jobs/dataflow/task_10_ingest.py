# Databricks notebook source
# MAGIC %md
# MAGIC ## Ingest Task
# MAGIC - Call DataBridge to ingest source files to landing zone
# MAGIC - Optionally verify the files in the landing zone

# COMMAND ----------

# DBTITLE 1,Show widget for development purpose
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

# OEDS domain-specific imports
from oeds.domain.utils.ingest.ingest_utils import (
    DisConnectionOptions,
    run_ingest,
)

# COMMAND ----------

# DBTITLE 1,Init logging and context
logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Internal Ingestion
# MAGIC #### Step 1: Prepare the DataBridge Connection
# MAGIC Resolve the service-principal credentials and create connection options
# MAGIC for the internal DataBridge workspace.

# COMMAND ----------
# Prepare DataBridge connection parameters.
databricks_workspace_url = job_ctx.get("internal_databricks_workspace_url")
databricks_resource_id = job_ctx.get("internal_databricks_resource_id")
dis_job_id = int(job_ctx.get("internal_dis_job_id"))

# Prepare DataBridge authentication parameters.
azure_tenant_id = job_ctx.get("azure_tenant_id")
service_spn_id = dbutils.secrets.get(
    scope=job_ctx["secrete_scope"],
    key=job_ctx["service_spn_id_key"],
)
service_spn_secret = dbutils.secrets.get(
    scope=job_ctx["secrete_scope"],
    key=job_ctx["service_spn_secrete_key"],
)
logger.debug("Service SPN secret is configured: %s", bool(service_spn_secret))

connection = DisConnectionOptions(
    host=databricks_workspace_url,
    azure_tenant_id=azure_tenant_id,
    azure_client_id=service_spn_id,
    azure_client_secret=service_spn_secret,
    azure_workspace_resource_id=databricks_resource_id,
    dis_job_id=dis_job_id,
)

# COMMAND ----------
# MAGIC %md
# MAGIC #### Step 2: Prepare Ingestion Parameters
# MAGIC - Prepare client-side ingestion parameters.
# MAGIC - Keep server-side template values in the packaged configuration.
# MAGIC
# MAGIC DataBridge supports both **client-side** and **server-side** templating. Use
# MAGIC the following principles:
# MAGIC 1. **Hardcode static configurations**
# MAGIC    Environment-independent values should be defined directly in the
# MAGIC    ingestion config file.
# MAGIC 2. **Use client-side templating for client-known values**
# MAGIC    Use client-side templates for dynamic values known before
# MAGIC    submission, such as environment, `file_date`, source file name, or
# MAGIC    client-provided paths.
# MAGIC 3. **Use server-side templating for server-known or sensitive values**
# MAGIC    Use server-side templates for values only available at runtime or
# MAGIC    managed by DataBridge, such as secrets, credentials, runtime metadata, or
# MAGIC    server-generated values.
# MAGIC

# COMMAND ----------

# Environment tag
env = job_ctx.get("env")

# The main task prepares file_date and land_dir so downstream tasks share the
# same run paths.
file_date = dbutils.jobs.taskValues.get(
    taskKey="main", key="file_date", debugValue=date.today().isoformat()
)
logger.info(f"file_date: {file_date}")

land_dir_default = str(Path(job_ctx.get("land_root")) / file_date)
land_dir = dbutils.jobs.taskValues.get(
    taskKey="main", key="land_dir", debugValue=land_dir_default
)
logger.info(f"land_dir: {land_dir}")

# Compose ingestion parameters
ingestion_params = {
    "env": env,
    "file_date": file_date,
    "land_dir": land_dir,
}

# COMMAND ----------

# MAGIC %md
# MAGIC #### Step 3: Run Internal Ingestion
# MAGIC The executable default below uses the internal DataBridge connection and the
# MAGIC packaged `default.json` configuration. `run_ingest` loads and resolves
# MAGIC the configuration, waits for a terminal state, and verifies the `upload`
# MAGIC task output with its default 300/10-second verification timing.
# MAGIC Unsuccessful ingestion or verification raises `IngestTaskError`.

# COMMAND ----------

ingest_task_result = run_ingest(
    connection=connection,
    config_file="default.json",
    template_params=ingestion_params,
)
logger.info("Ingestion finished successfully")

# COMMAND ----------

# MAGIC %md
# MAGIC ### External Ingestion
# MAGIC
# MAGIC External ingestion uses the external DataBridge workspace and uploads downloaded
# MAGIC files to anti-virus scan storage with
# MAGIC `oedis.handler.azureblobstorage.upload`.
# MAGIC
# MAGIC The external scenario requires:
# MAGIC
# MAGIC 1. `DisConnectionOptions` built from the external workspace URL, resource
# MAGIC    ID, and DataBridge job ID.
# MAGIC 2. Template parameters containing the anti-virus root, tenant ID, and the
# MAGIC    Key Vault key names used by DataBridge.
# MAGIC 3. `FileVerificationOptions` that remap the anti-virus destination root to
# MAGIC    the final landing root while preserving each relative file path.
# MAGIC
# MAGIC Use client-side `[[...]]` templates for values supplied by Dataforge.
# MAGIC Keep credential values as server-side `{{...}}` Key Vault templates so
# MAGIC only their key names are sent by the client. The external upload task can
# MAGIC use the following configuration shape:
# MAGIC
# MAGIC ```json
# MAGIC {
# MAGIC   "id": "upload",
# MAGIC   "handler": "oedis.handler.azureblobstorage.upload",
# MAGIC   "params": {
# MAGIC     "connection": {
# MAGIC       "uri": "[[dis_av_root]]",
# MAGIC       "tenant_id": "[[tenant_id]]",
# MAGIC       "client_id": "{{ keyvault(scope='<oedis-secret-scope>', key='[[dis_oedisext_client_id_key]]') }}",
# MAGIC       "client_secret": "{{ keyvault(scope='<oedis-secret-scope>', key='[[dis_oedisext_client_secret_key]]') }}"
# MAGIC     },
# MAGIC     "requests": [
# MAGIC       {
# MAGIC         "include": ["*.csv"],
# MAGIC         "dst_dir": "[[file_date]]",
# MAGIC         "recursive": false
# MAGIC       }
# MAGIC     ]
# MAGIC   }
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC Use the roots themselves, rather than dated directories, for verification
# MAGIC remapping because `FileVerificationOptions` preserves relative suffixes.

# COMMAND ----------

# External ingestion example. Uncomment this cell and replace the internal run.
# from oeds.domain.utils.ingest.ingest_utils import FileVerificationOptions
#
# external_connection = DisConnectionOptions(
#     host=job_ctx.get("external_databricks_workspace_url"),
#     azure_tenant_id=job_ctx.get("azure_tenant_id"),
#     azure_client_id=service_spn_id,
#     azure_client_secret=service_spn_secret,
#     azure_workspace_resource_id=job_ctx.get(
#         "external_databricks_resource_id"
#     ),
#     dis_job_id=int(job_ctx.get("external_dis_job_id")),
# )
#
# external_template_params = {
#     **ingestion_params,
#     "dis_av_root": job_ctx.get("dis_av_root"),
#     "tenant_id": job_ctx.get("azure_tenant_id"),
#     "dis_oedisext_client_id_key": job_ctx.get(
#         "dis_oedisext_client_id_key"
#     ),
#     "dis_oedisext_client_secret_key": job_ctx.get(
#         "dis_oedisext_client_secret_key"
#     ),
# }
#
# external_file_verification = FileVerificationOptions(
#     dest_root=job_ctx.get("dis_av_root"),
#     land_root=job_ctx.get("land_root"),
# )
#
# external_ingest_task_result = run_ingest(
#     connection=external_connection,
#     config_file="default.json",
#     template_params=external_template_params,
#     verification=external_file_verification,
# )
# logger.info("Ingestion finished successfully")
