# Databricks notebook source
# Purpose:
# - Automatically reloads imported Python modules when their source code changes.
# - Makes iterative development faster: you can edit code in workspace files (or repo),
#   re-run cells, and your changes take effect without restarting the notebook/kernel.
#
# Notes:
# - Best for interactive/dev workflows.
# - In production job runs, you can remove or disable to reduce surprises and improve reproducibility:
#   use `%autoreload 0`.
try:
    from IPython import get_ipython

    ipython = get_ipython()
    if ipython:
        ipython.run_line_magic("load_ext", "autoreload")
        ipython.run_line_magic("autoreload", "2")
except Exception:
    # Safe fallback when IPython is unavailable (e.g., scheduled jobs or unit tests).
    pass

# COMMAND ----------

# MAGIC %pip install --index-url https://fcp4lnexuap01.bocad.bank-banque-canada.ca/nexus/repository/pypi-all/simple --trusted-host fcp4lnexuap01.bocad.bank-banque-canada.ca -r /Workspace/bap/.bundle/habs/files/cluster/requirements.txt -q

# COMMAND ----------

# DBTITLE 1,Set flow_action
# Set default flow_action as continue. 
# In case that you want to exit the whole pipeline gracefully, set the value to "complete". 
try:
    dbutils.jobs.taskValues.set(key="flow_action", value="continue")
except Exception:
    pass

# COMMAND ----------

# Standard libraries
from datetime import date, datetime
import json
import uuid
from pathlib import Path

# OEDS common libraries
from oeds.core.misc_utils import param
from oeds.core.env_utils import ENV

# COMMAND ----------

def parse_bool(value: str, default: bool = False) -> bool:
    """
    Parse a truthy/falsey string to bool. If parsing fails, return default.
    """
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return default

def parse_date(date_str: str, python_date_format: str, default=None) -> date:

    if not date_str:
        return default
    try:
        return datetime.strptime(date_str, python_date_format).date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format '{date_str}'. Expected format: {python_date_format}"
        ) from exc

def parse_json(value: str):
    """
    Parse a JSON string.

    - If value is empty or only whitespace, return {}.
    - If parsing fails, raise
    """
    if value is None:
        return {}

    text = str(value).strip()
    if not text:
        return {}

    return json.loads(text)

def resolve_bundle_root_dir(current_notebook_dir: str) -> str:
    """
    Resolve the bundle root from a notebook directory.

    Notebooks can live directly below the bundle root, such as examples/ or tools/,
    or below jobs/<job_name>/ for workflow task notebooks.
    """
    current_dir = Path(current_notebook_dir)
    for parent in (current_dir, *current_dir.parents):
        if parent.name == "jobs":
            return str(parent.parent)

    return str(current_dir.parent)

# COMMAND ----------

# DBTITLE 1,Build job context
DEFAULT_TEAM = "OEDS"
DEFAULT_DOMAIN = "BAP"
DEFAULT_PIPELINE = "habs_wp1"
DEFAULT_DATASET = "dataset"

DEFAULT_ENV = "dev"
DEFAULT_DBK_RUNTIME_VERSION = "16.4.x-scala2.13"
DEFAULT_JOB_NAME = "BAP-HABS-WORKPACKAGE1"
DEFAULT_JOB_ID = "123456789"
DEFAULT_JOB_RUN_ID = str(uuid.uuid4())
DEFAULT_JOB_TRIGGER_TYPE = "manual"
DEFAULT_WORKSPACE_URL = "https://adb-1700301391505163.3.azuredatabricks.net"
DEFAULT_BUNDLE_ROOT = resolve_bundle_root_dir(ENV.CURRENT_DIR)
DEFAULT_CATALOG = f"{DEFAULT_ENV}_banking_and_payments_cat"
DEFAULT_CONFIG_ROOT = f"/Volumes/{DEFAULT_CATALOG}/reference_db/vol_bap_config"
DEFAULT_SECRET_SCOPE = "lake-kv-oedataservices-scope"
DEFAULT_OEDS_SECRET_SCOPE = "lake-kv-oedataservices-scope"
DEFAULT_AZURE_TENANT_ID_KEY = "app-2b501945-5940-4527-9cdd-51a07b77ceb7-tenantid"
DEFAULT_SERVICE_SPN_ID_KEY = "app-2b501945-5940-4527-9cdd-51a07b77ceb7-appid"
DEFAULT_SERVICE_SPN_SECRET_KEY = "app-2b501945-5940-4527-9cdd-51a07b77ceb7-secret"
DEFAULT_INTERNAL_DATABRICKS_WORKSPACE_URL = "https://adb-1700301391505163.3.azuredatabricks.net"
DEFAULT_INTERNAL_DATABRICKS_RESOURCE_ID = "/subscriptions/1de5fd2d-2313-461a-acc4-07cdc509cdf4/resourceGroups/lake-cac-npd-rg-devplatform/providers/Microsoft.Databricks/workspaces/lake-cac-npd-dbw-devuc01"
DEFAULT_INTERNAL_DIS_JOB_ID = "140598343443137"
DEFAULT_EXTERNAL_DATABRICKS_WORKSPACE_URL = "https://adb-7405611352003885.5.azuredatabricks.net"
DEFAULT_EXTERNAL_DATABRICKS_RESOURCE_ID = "/subscriptions/1de5fd2d-2313-461a-acc4-07cdc509cdf4/resourceGroups/lake-cac-npd-rg-devplatform/providers/Microsoft.Databricks/workspaces/lake-cac-npd-dbw-devdmz01"
DEFAULT_EXTERNAL_DIS_JOB_ID = "0"
DEFAULT_EMAIL_SERVICE_URL_KEY = "OEDS-EMAIL-SERVICE-URL"
DEFAULT_EMAIL_MAPPINGS = '{"DDA":"dda-support-dev@bank-banque-canada.ca","DM":"dda-support-dev@bank-banque-canada.ca"}'
DEFAULT_DATAMART_ENDPOINTS = '[{"URL":"https://api-dev.bank-banque-canada.ca/datamart/v1/api/uc/pipeline/ingest", "SCOPE":"api://1dae7513-113d-460e-a2a8-3f4045ca7e25/.default"}]'
DEFAULT_NEXUS_URL = "https://fcp4lnexuap01.bocad.bank-banque-canada.ca/nexus/repository/pypi-all/simple"
DEFAULT_NEXUS_INIT_PATH = ""
DEFAULT_HABS_CATALOG = f"{DEFAULT_ENV}_ext_ora_habs_cat"
DEFAULT_FMBODW_CATALOG = f"{DEFAULT_ENV}_ext_ora_fmbodw_cat"

def get_job_context():
    ctx = {}

    # ------------------------------------------------------------------
    # Properties from current execution context
    # ------------------------------------------------------------------
    ctx["current_user"] = param("current_user", ENV.CURRENT_USER)
    ctx["current_notebook_path"] = param("current_notebook_path", ENV.CURRENT_NOTEBOOK_PATH)
    ctx["current_notebook_dir"] = param("current_notebook_dir", ENV.CURRENT_DIR)

    # ------------------------------------------------------------------
    # Base task parameters
    # ------------------------------------------------------------------
    # team name
    ctx["team"] = param("team", DEFAULT_TEAM).strip().lower()
    # domain name
    ctx["domain"] = param("domain", DEFAULT_DOMAIN).strip().lower()
    # pipeline name
    ctx["pipeline"] = param("pipeline", DEFAULT_PIPELINE).strip().lower()
    # dataset name
    ctx["dataset"] = param("dataset", DEFAULT_DATASET).strip().lower()

    # Date/Geo Settings
    ctx["timezone"] = param("timezone", "America/Toronto").strip()
    ctx["human_date_format"] = param("human_date_format", "YYYY-MM-DD")
    ctx["python_date_format"] = param("python_date_format", "%Y-%m-%d")
    ctx["spark_date_format"] = param("spark_date_format", "yyyy-MM-dd")

    # Runtime
    ctx["env"] = param("env", DEFAULT_ENV).strip().lower()
    ctx["dbk_runtime_version"] = param("dbk_runtime_version", DEFAULT_DBK_RUNTIME_VERSION)
    # Properties provided by Databricks job runtime
    ctx["job_name"] = param("job_name", DEFAULT_JOB_NAME)
    ctx["job_id"] = param("job_id", DEFAULT_JOB_ID)
    ctx["job_run_id"] = param("job_run_id", DEFAULT_JOB_RUN_ID)
    ctx["job_trigger_type"] = param("job_trigger_type", DEFAULT_JOB_TRIGGER_TYPE)
    ctx["workspace_url"] = param("workspace_url", DEFAULT_WORKSPACE_URL)

    # Bunlde path
    ctx["bundle_root"] = param("bundle_root", DEFAULT_BUNDLE_ROOT)
    ctx["bundle_src_dir"] = str(Path(ctx["bundle_root"]) / "src")
    ctx["bundle_cluster_dir"] = str(Path(ctx["bundle_root"]) / "cluster")

    # UC
    env = ctx["env"]
    ctx["catalog"] = param("catalog", DEFAULT_CATALOG)
    ctx["habs_catalog"] = param("habs_catalog", DEFAULT_HABS_CATALOG)
    ctx["fmbodw_catalog"] = param("fmbodw_catalog", DEFAULT_FMBODW_CATALOG)
    ctx["config_root"] = param("config_root", DEFAULT_CONFIG_ROOT)

    # project/default secret scope
    ctx["secret_scope"] = param("oeds_secret_scope", DEFAULT_OEDS_SECRET_SCOPE)
    # OEDS secret scope
    ctx["oeds_secret_scope"] = param("oeds_secret_scope", DEFAULT_OEDS_SECRET_SCOPE)


    # Internal ingestion service
    ctx["internal_databricks_workspace_url"] = param(
        "internal_databricks_workspace_url",
        DEFAULT_INTERNAL_DATABRICKS_WORKSPACE_URL
    )
    ctx["internal_databricks_resource_id"] = param(
        "internal_databricks_resource_id",
        DEFAULT_INTERNAL_DATABRICKS_RESOURCE_ID
    )
    internal_dis_job_id_str = param(
        "internal_dis_job_id",
        DEFAULT_INTERNAL_DIS_JOB_ID
    )
    ctx["internal_dis_job_id"] = int(internal_dis_job_id_str)

    # External ingestion service
    ctx["external_databricks_workspace_url"] = param(
        "external_databricks_workspace_url",
        DEFAULT_EXTERNAL_DATABRICKS_WORKSPACE_URL
    )
    ctx["external_databricks_resource_id"] = param(
        "external_databricks_resource_id",
        DEFAULT_EXTERNAL_DATABRICKS_RESOURCE_ID
    )
    external_dis_job_id_str = param(
        "external_dis_job_id",
        DEFAULT_EXTERNAL_DIS_JOB_ID)
    ctx["external_dis_job_id"] = int(external_dis_job_id_str or "0")

    # Email service URL key
    ctx["email_service_url_key"] = param(
        "email_service_url_key",
        DEFAULT_EMAIL_SERVICE_URL_KEY)
    # Business notification email list
    email_mappings_str = param("email_mappings", DEFAULT_EMAIL_MAPPINGS)
    ctx["email_mappings"] = parse_json(email_mappings_str)
    
    # Datamart
    datamart_endpoints_str = param(
        "datamart_endpoints",
        DEFAULT_DATAMART_ENDPOINTS
    )
    ctx["datamart_endpoints"] = parse_json(datamart_endpoints_str)

    # Nexus
    ctx["nexus_url"] = param(
        "nexus_url",
        DEFAULT_NEXUS_URL
    )
    ctx["nexus_init_path"] = param(
        "nexus_init_path",
        DEFAULT_NEXUS_INIT_PATH
    )

    # ------------------------------------------------------------------
    # Properties passed by job parameters
    # ------------------------------------------------------------------
    # Run date, default as today if empty
    rundate_str = param("rundate", "").strip()
    ctx["rundate"] = parse_date(rundate_str, ctx["python_date_format"], default=date.today())
    # Debug mode
    debug_str = param("debug", "true").strip()
    ctx["debug"] = parse_bool(debug_str, default=False)

    ## service job parameters
    # task
    ctx["task"] = param("task", "").strip()
    # args must be a valid JSON string
    args_str = param("args", "").strip()
    ctx["args"] = parse_json(args_str)

    # ------------------------------------------------------------------
    # constants
    # ------------------------------------------------------------------
    # Common catalog
    ctx["metadata_cat"] = f'{ctx["env"]}_metadata_cat'
    ctx["reference_cat"] = f'{ctx["env"]}_reference_cat'

    return ctx

# COMMAND ----------

# Get job context
_ctx = get_job_context()

# COMMAND ----------

# Set up logging
import logging
import oeds.core.log_utils as logutils
log_level = "debug" if _ctx.get("debug") else "info"
logutils.setup_logger(level=log_level)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Add the src directory into Python import path
import sys
src_path = _ctx.get("bundle_src_dir")
if str(src_path) not in sys.path:
    logger.info(f"Adding import path: {src_path}")
    sys.path.insert(0, str(src_path))

# COMMAND ----------

# Initialize packaged configuration before managers load their registries.
from oeds.domain.utils.config import ConfigManager

ConfigManager.initialize(_ctx["env"])

# COMMAND ----------

def initialize_email_manager(job_ctx):
    """Initialize email delivery only in tasks that send notifications."""
    from oeds.domain.utils.email import EmailManager

    email_service_url = dbutils.secrets.get(
        scope=job_ctx["oeds_secret_scope"],
        key=job_ctx["email_service_url_key"],
    )
    EmailManager.initialize(
        provider="logicapp",
        connection={"logicapp_url": email_service_url},
        recipient_mappings=job_ctx["email_mappings"],
    )
    return EmailManager.get_instance()

