# Databricks notebook source
# Enable IPython autoreload for interactive development. Scheduled jobs and
# non-IPython environments continue without it.
try:
    from IPython import get_ipython

    ipython = get_ipython()
    if ipython:
        ipython.run_line_magic("load_ext", "autoreload")
        ipython.run_line_magic("autoreload", "2")
except Exception:
    pass

# COMMAND ----------

# DBTITLE 1,Set flow_action
# Downstream tasks may replace "continue" with "complete" to exit gracefully.
try:
    dbutils.jobs.taskValues.set(key="flow_action", value="continue")
except Exception:
    pass

# COMMAND ----------

# Standard-library imports
import json
import uuid
from datetime import date, datetime
from pathlib import Path

# DataKit library imports
from oeds.core.env_utils import ENV
from oeds.core.misc_utils import param

# COMMAND ----------


def parse_bool(value: str, default: bool = False) -> bool:
    """Parse a string-like value as a Boolean.

    Args:
        value: Value to parse. Matching is case-insensitive and ignores
            surrounding whitespace.
        default: Value returned for ``None`` or an unrecognized string.

    Returns:
        ``True`` for ``true``, ``1``, ``yes``, or ``y``; ``False`` for
        ``false``, ``0``, ``no``, or ``n``; otherwise ``default``.
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
    """Parse a date using a configured Python format.

    Args:
        date_str: Date text to parse. An empty value returns ``default``.
        python_date_format: Format accepted by :func:`datetime.strptime`.
        default: Value returned when ``date_str`` is empty.

    Returns:
        The parsed date, or ``default`` when no date text is provided.

    Raises:
        ValueError: If ``date_str`` does not match ``python_date_format``.
    """

    if not date_str:
        return default
    try:
        return datetime.strptime(date_str, python_date_format).date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format '{date_str}'. Expected format: {python_date_format}"
        ) from exc


def parse_json(value: str):
    """Parse JSON text, returning an empty mapping for an empty value.

    Args:
        value: JSON text to parse. ``None`` and whitespace-only values return
            an empty mapping.

    Returns:
        The decoded JSON value, or an empty mapping when no text is provided.

    Raises:
        json.JSONDecodeError: If a non-empty value is not valid JSON.
    """
    if value is None:
        return {}

    text = str(value).strip()
    if not text:
        return {}

    return json.loads(text)


def resolve_bundle_root_dir(current_notebook_dir: str) -> str:
    """Resolve the bundle root from a notebook directory.

    Notebooks may live at any depth below the bundle root.

    Args:
        current_notebook_dir: Directory containing the current notebook.

    Returns:
        The inferred bundle root path.
    """
    current_dir = Path(current_notebook_dir)
    candidates = (current_dir, *current_dir.parents)

    for candidate in candidates:
        if (candidate / "common.py").is_file():
            return str(candidate)

    return str(current_dir.parent)

def resolve_secret(key: str, scope: str) -> str:
    """Resolve a nonblank secret key from the supplied scope."""
    if not key or not key.strip():
        raise ValueError("Secret key must not be blank")
    return dbutils.secrets.get(scope=scope, key=key.strip()).strip()


# COMMAND ----------

# DBTITLE 1,Build job context
# Project Metadata
DEFAULT_TEAM = "OEDS"
DEFAULT_DOMAIN = "BAP"
DEFAULT_PROJECT_TAG = "bap"
DEFAULT_CATALOG_TAG = "banking_and_payments"
DEFAULT_DATASET = "bsas"

# Job Metadata
DEFAULT_JOB_NAME = f"{DEFAULT_DOMAIN}-{DEFAULT_DATASET}-DATAFLOW".upper()
DEFAULT_JOB_ID = "123456789"
DEFAULT_JOB_RUN_ID = str(uuid.uuid4())
DEFAULT_JOB_TRIGGER_TYPE = "manual"
DEFAULT_WORKSPACE_URL = "https://adb-1700301391505163.3.azuredatabricks.net"

# Date/Geography settings
DEFAULT_TIMEZONE = "America/Toronto"
DEFAULT_HUMAN_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_PYTHON_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SPARK_DATE_FORMAT = "yyyy-MM-dd"
DEFAULT_HOLIDAY_GROUP = "nationalholidayscanada"

# Runtime settings
DEFAULT_ENV = "dev"
DEFAULT_DBK_RUNTIME_VERSION = "16.4.x-scala2.13"
DEFAULT_BUNDLE_ROOT = resolve_bundle_root_dir(ENV.CURRENT_DIR)
DEFAULT_NEXUS_URL = (
    "https://fcp4lnexuap01.bocad.bank-banque-canada.ca/nexus/repository/pypi-all/simple"
)
DEFAULT_NEXUS_INIT_PATH = str(Path(DEFAULT_BUNDLE_ROOT) / "cluster")

# Project Databricks resources
DEFAULT_CATALOG = f"{DEFAULT_ENV}_{DEFAULT_CATALOG_TAG}_cat"
DEFAULT_LAND_ROOT = (
    f"/Volumes/{DEFAULT_CATALOG}/reference_db/"
    f"vol_{DEFAULT_PROJECT_TAG}_land/{DEFAULT_DATASET}"
)
DEFAULT_TMP_ROOT = (
    f"/Volumes/{DEFAULT_CATALOG}/reference_db/"
    f"vol_{DEFAULT_PROJECT_TAG}_land/tmp/{DEFAULT_DATASET}"
)
DEFAULT_OUTBOUND_ROOT = (
    f"/Volumes/{DEFAULT_CATALOG}/reference_db/"
    f"vol_{DEFAULT_PROJECT_TAG}_land/outbound/{DEFAULT_DATASET}"
)
DEFAULT_CONFIG_ROOT = (
    f"/Volumes/{DEFAULT_CATALOG}/reference_db/"
    f"vol_{DEFAULT_PROJECT_TAG}_config/{DEFAULT_DATASET}"
)
DEFAULT_RAW_ROOT = f"/Volumes/{DEFAULT_ENV}_raw_cat/restricted_db/vol_internal_bsas"
DEFAULT_SECRETE_SCOPE = "lake-kv-oedataservices-scope"
DEFAULT_OEDS_SECRETE_SCOPE = "lake-kv-oedataservices-scope"

# Project Databricks catalogs
DEFAULT_FMD_CATALOG = f"{DEFAULT_ENV}_financial_markets_cat"
DEFAULT_CUR_CATALOG = f"{DEFAULT_ENV}_currency_cat"
DEFAULT_BAP_CATALOG = f"{DEFAULT_ENV}_banking_and_payments_cat"
DEFAULT_SUP_CATALOG = f"{DEFAULT_ENV}_oversight_cat"
DEFAULT_METADATA_CATALOG = f"{DEFAULT_ENV}_metadata_cat"
DEFAULT_REFERENCE_CATALOG = f"{DEFAULT_ENV}_reference_cat"
DEFAULT_APPLICATION_CATALOG = f"{DEFAULT_ENV}_application_cat"
DEFAULT_INTERNAL_CATALOG = f"{DEFAULT_ENV}_boc_internal_src_cat"

# System integration settings
DEFAULT_AZURE_SUBSCRIPTION_ID = "1de5fd2d-2313-461a-acc4-07cdc509cdf4"
DEFAULT_AZURE_TENANT_ID = "d5d43af4-5942-46a8-907b-711a17e948bd"
DEFAULT_SERVICE_SPN_ID_KEY = "app-2b501945-5940-4527-9cdd-51a07b77ceb7-appid"
DEFAULT_SERVICE_SPN_SECRETE_KEY = "app-2b501945-5940-4527-9cdd-51a07b77ceb7-secret"
# Databricks integration settings - jobs and SQL warehouses
DEFAULT_INTERNAL_DATABRICKS_WORKSPACE_URL = (
    "https://adb-1700301391505163.3.azuredatabricks.net"
)
DEFAULT_EXTERNAL_DATABRICKS_WORKSPACE_URL = (
    "https://adb-7405611352003885.5.azuredatabricks.net"
)
DEFAULT_INTERNAL_DATABRICKS_RESOURCE_ID = (
    "/subscriptions/1de5fd2d-2313-461a-acc4-07cdc509cdf4"
    "/resourceGroups/lake-cac-npd-rg-devplatform"
    "/providers/Microsoft.Databricks/workspaces/lake-cac-npd-dbw-devuc01"
)
DEFAULT_EXTERNAL_DATABRICKS_RESOURCE_ID = (
    "/subscriptions/1de5fd2d-2313-461a-acc4-07cdc509cdf4"
    "/resourceGroups/lake-cac-npd-rg-devplatform"
    "/providers/Microsoft.Databricks/workspaces/lake-cac-npd-dbw-devdmz01"
)
DEFAULT_SQL_WAREHOUSE_SERVERLESS_LARGE_ID = "c7a96b737254336e"
DEFAULT_SQL_WAREHOUSE_CLASSIC_MEDIUM_ID = "01461d896164c7ea"

# DataBridge ingestion service settings
DEFAULT_INTERNAL_DIS_JOB_ID = "987342006066143"
DEFAULT_EXTERNAL_DIS_JOB_ID = "539367079988378"
DEFAULT_DIS_AV_ROOT = (
    "https://lakecacnpdstdevavscan01.blob.core.windows.net/"
    f"avscan-{DEFAULT_PROJECT_TAG}/{DEFAULT_DATASET}"
)
DEFAULT_DIS_OEDISEXT_CLIENT_ID_KEY = "app-ec1ede6d-b2e2-4ec9-8db6-76dbf1410ec9-appid"
DEFAULT_DIS_OEDISEXT_CLIENT_SECRET_KEY = (
    "app-ec1ede6d-b2e2-4ec9-8db6-76dbf1410ec9-secret"
)

# Email service settings
DEFAULT_EMAIL_SERVICE_URL_KEY = "oeds-email-service-url"

# DataBridge email service
DEFAULT_DATABRIDGE_EMAIL_TENANT_ID_KEY = (
    "app-3fc6e6c5-eaa5-4948-ba9a-d3ceebf437db-tenantid"
)
DEFAULT_DATABRIDGE_EMAIL_CLIENT_ID_KEY = (
    "app-3fc6e6c5-eaa5-4948-ba9a-d3ceebf437db-appid"
)
DEFAULT_DATABRIDGE_EMAIL_CLIENT_SECRET_KEY = (
    "app-3fc6e6c5-eaa5-4948-ba9a-d3ceebf437db-secret"
)
DEFAULT_DATABRIDGE_EMAIL_SENDER_ACCOUNT = "dda-support-dev@bocqa.bank-banque-canada.ca"

# Time series data publishing settings
DEFAULT_DATAMART_ENDPOINTS_KEY = "datamart-endpoints"

# Project settings
# Recipient mappings
DEFAULT_EMAIL_MAPPINGS = (
    '{"DDA":"dda-support-dev@bank-banque-canada.ca"}'
)

def get_job_context():
    """Build the runtime context from task parameters and project defaults.

    Azure and Databricks integration values come from task parameters.
    Datamart endpoints are resolved from the OEDS secret scope; credential
    keys remain resolved by their consumers.

    Returns:
        A context mapping used by downstream notebook cells and tasks.
    """
    ctx = {}

    # ------------------------------------------------------------------
    # Properties from current execution context
    # ------------------------------------------------------------------
    ctx["current_user"] = str(ENV.CURRENT_USER or "").strip()
    ctx["current_notebook_path"] = str(ENV.CURRENT_NOTEBOOK_PATH or "").strip()
    ctx["current_notebook_dir"] = str(ENV.CURRENT_DIR or "").strip()

    # ------------------------------------------------------------------
    # Base task parameters
    # ------------------------------------------------------------------
    # Project Metadata
    ctx["team"] = param("team", DEFAULT_TEAM).strip().lower()
    ctx["domain"] = param("domain", DEFAULT_DOMAIN).strip().lower()
    ctx["dataset"] = param("dataset", DEFAULT_DATASET).strip().lower()

    # Job Metadata
    ctx["job_name"] = param("job_name", DEFAULT_JOB_NAME)
    ctx["job_id"] = param("job_id", DEFAULT_JOB_ID)
    ctx["job_run_id"] = param("job_run_id", DEFAULT_JOB_RUN_ID)
    ctx["job_trigger_type"] = param("job_trigger_type", DEFAULT_JOB_TRIGGER_TYPE)
    ctx["workspace_url"] = param("workspace_url", DEFAULT_WORKSPACE_URL)

    # Date/Geography settings
    ctx["timezone"] = param("timezone", DEFAULT_TIMEZONE).strip()
    ctx["human_date_format"] = param("human_date_format", DEFAULT_HUMAN_DATE_FORMAT)
    ctx["python_date_format"] = param("python_date_format", DEFAULT_PYTHON_DATE_FORMAT)
    ctx["spark_date_format"] = param("spark_date_format", DEFAULT_SPARK_DATE_FORMAT)
    ctx["holiday_group"] = str(
        param("holiday_group", DEFAULT_HOLIDAY_GROUP) or ""
    ).strip()

    # Runtime settings
    ctx["env"] = param("env", DEFAULT_ENV).strip().lower()
    ctx["dbk_runtime_version"] = param(
        "dbk_runtime_version", DEFAULT_DBK_RUNTIME_VERSION
    )
    # Bundle path
    ctx["bundle_root"] = param("bundle_root", DEFAULT_BUNDLE_ROOT)
    ctx["bundle_conf_dir"] = str(Path(ctx["bundle_root"]) / "conf")
    ctx["bundle_src_dir"] = str(Path(ctx["bundle_root"]) / "src")
    ctx["bundle_cluster_dir"] = str(Path(ctx["bundle_root"]) / "cluster")
    # Nexus url
    ctx["nexus_url"] = param("nexus_url", DEFAULT_NEXUS_URL)
    ctx["nexus_init_path"] = param("nexus_init_path", DEFAULT_NEXUS_INIT_PATH)

    # Project Databricks resources
    ctx["catalog"] = param("catalog", DEFAULT_CATALOG)
    ctx["land_root"] = param("land_root", DEFAULT_LAND_ROOT)
    ctx["tmp_root"] = param("tmp_root", DEFAULT_TMP_ROOT)
    ctx["outbound_root"] = param("outbound_root", DEFAULT_OUTBOUND_ROOT)
    ctx["config_root"] = param("config_root", DEFAULT_CONFIG_ROOT)
    ctx["raw_root"] = param("raw_root", DEFAULT_RAW_ROOT)
    ctx["secrete_scope"] = param("secrete_scope", DEFAULT_SECRETE_SCOPE)
    ctx["oeds_secrete_scope"] = param("oeds_secrete_scope", DEFAULT_OEDS_SECRETE_SCOPE)

    # Project Databricks catalogs
    ctx["fmd_catalog"] = param("fmd_catalog", DEFAULT_FMD_CATALOG)
    ctx["cur_catalog"] = param("cur_catalog", DEFAULT_CUR_CATALOG)
    ctx["bap_catalog"] = param("bap_catalog", DEFAULT_BAP_CATALOG)
    ctx["sup_catalog"] = param("sup_catalog", DEFAULT_SUP_CATALOG)
    ctx["metadata_catalog"] = param(
        "metadata_catalog", DEFAULT_METADATA_CATALOG
    )
    ctx["reference_catalog"] = param(
        "reference_catalog", DEFAULT_REFERENCE_CATALOG
    )
    ctx["application_catalog"] = param(
        "application_catalog", DEFAULT_APPLICATION_CATALOG
    )
    ctx["internal_catalog"] = param(
        "internal_catalog", DEFAULT_INTERNAL_CATALOG
    )

    # System Integration settings
    if not str(ctx["oeds_secrete_scope"] or "").strip():
        raise ValueError("oeds_secrete_scope must not be blank")

    # Service SPN
    ctx["azure_subscription_id"] = str(
        param("azure_subscription_id", DEFAULT_AZURE_SUBSCRIPTION_ID) or ""
    ).strip()

    ctx["azure_tenant_id"] = str(
        param("azure_tenant_id", DEFAULT_AZURE_TENANT_ID) or ""
    ).strip()

    ctx["service_spn_id_key"] = param("service_spn_id_key", DEFAULT_SERVICE_SPN_ID_KEY)
    ctx["service_spn_secrete_key"] = param(
        "service_spn_secrete_key", DEFAULT_SERVICE_SPN_SECRETE_KEY
    )

    # Databricks integration settings - jobs and SQL warehouses
    ctx["internal_databricks_workspace_url"] = str(
        param(
            "internal_databricks_workspace_url", DEFAULT_INTERNAL_DATABRICKS_WORKSPACE_URL
        )
        or ""
    ).strip()

    ctx["internal_databricks_resource_id"] = str(
        param(
            "internal_databricks_resource_id", DEFAULT_INTERNAL_DATABRICKS_RESOURCE_ID
        )
        or ""
    ).strip()

    ctx["external_databricks_workspace_url"] = str(
        param(
            "external_databricks_workspace_url", DEFAULT_EXTERNAL_DATABRICKS_WORKSPACE_URL
        )
        or ""
    ).strip()

    ctx["external_databricks_resource_id"] = str(
        param(
            "external_databricks_resource_id", DEFAULT_EXTERNAL_DATABRICKS_RESOURCE_ID
        )
        or ""
    ).strip()

    ctx["sql_warehouse_serverless_large_id"] = str(
        param(
            "sql_warehouse_serverless_large_id", DEFAULT_SQL_WAREHOUSE_SERVERLESS_LARGE_ID
        )
        or ""
    ).strip()

    ctx["sql_warehouse_classic_medium_id"] = str(
        param(
            "sql_warehouse_classic_medium_id", DEFAULT_SQL_WAREHOUSE_CLASSIC_MEDIUM_ID
        )
        or ""
    ).strip()

    # DataBridge ingestion service settings
    ctx["internal_dis_job_id"] = str(
        param("internal_dis_job_id", DEFAULT_INTERNAL_DIS_JOB_ID) or ""
    ).strip()
    ctx["external_dis_job_id"] = str(
        param("external_dis_job_id", DEFAULT_EXTERNAL_DIS_JOB_ID) or ""
    ).strip()
    ctx["dis_av_root"] = (
        str(param("dis_av_root", DEFAULT_DIS_AV_ROOT) or "").strip().rstrip("/")
    )
    ctx["dis_oedisext_client_id_key"] = str(
        param(
            "dis_oedisext_client_id_key",
            DEFAULT_DIS_OEDISEXT_CLIENT_ID_KEY,
        )
        or ""
    ).strip()
    ctx["dis_oedisext_client_secret_key"] = str(
        param(
            "dis_oedisext_client_secret_key",
            DEFAULT_DIS_OEDISEXT_CLIENT_SECRET_KEY,
        )
        or ""
    ).strip()

    # Email service settings
    ctx["email_service_url_key"] = param(
        "email_service_url_key", DEFAULT_EMAIL_SERVICE_URL_KEY
    )

    # DataBridge email service
    ctx["databridge_email_tenant_id_key"] = str(
        param("databridge_email_tenant_id_key", DEFAULT_DATABRIDGE_EMAIL_TENANT_ID_KEY)
        or ""
    ).strip()
    ctx["databridge_email_client_id_key"] = str(
        param("databridge_email_client_id_key", DEFAULT_DATABRIDGE_EMAIL_CLIENT_ID_KEY)
        or ""
    ).strip()
    ctx["databridge_email_client_secret_key"] = str(
        param(
            "databridge_email_client_secret_key",
            DEFAULT_DATABRIDGE_EMAIL_CLIENT_SECRET_KEY,
        )
        or ""
    ).strip()
    ctx["databridge_email_sender_account"] = str(
        param("databridge_email_sender_account", DEFAULT_DATABRIDGE_EMAIL_SENDER_ACCOUNT)
        or ""
    ).strip()

    # Time series data publishing settings
    ctx["datamart_endpoints_key"] = param(
        "datamart_endpoints_key", DEFAULT_DATAMART_ENDPOINTS_KEY
    )
    ctx["datamart_endpoints"] = resolve_secret(
        ctx["datamart_endpoints_key"], scope=ctx["oeds_secrete_scope"]
    )

    # ------------------------------------------------------------------
    # Project settings
    # ------------------------------------------------------------------
    # Recipient mappings
    ctx["email_mappings"] = str(
        param("email_mappings", DEFAULT_EMAIL_MAPPINGS) or ""
    ).strip()

    # ------------------------------------------------------------------
    # Job parameters
    # ------------------------------------------------------------------
    ctx["rundate"] = str(param("rundate", "") or "").strip()
    if not ctx["rundate"]:
        ctx["rundate"] = date.today().strftime(ctx["python_date_format"])
    ctx["debug"] = str(param("debug", "true") or "true").strip()
    ctx["args"] = str(param("args", "") or "").strip()
    ctx["task"] = str(param("task", "") or "").strip()

    return ctx


# COMMAND ----------

_ctx = get_job_context()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Initialize logging

# COMMAND ----------

import logging

import oeds.core.log_utils as logutils

debug_enabled = parse_bool(_ctx.get("debug"), default=False)
log_level = "debug" if debug_enabled else "info"
logutils.setup_logger(level=log_level)
logger = logging.getLogger(__name__)
# Log the job context for debugging purposes
logger.debug("Job context keys: %s", sorted(_ctx))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configure Python import paths

# COMMAND ----------

import importlib
import sys

conf_path = _ctx.get("bundle_conf_dir")
src_path = _ctx.get("bundle_src_dir")
for import_path in (conf_path, src_path):
    if str(import_path) not in sys.path:
        logger.info(f"Adding import path: {import_path}")
        sys.path.insert(0, str(import_path))

importlib.invalidate_caches()

# COMMAND ----------

# MAGIC %md
# MAGIC # Configure runtime managers
# MAGIC
# MAGIC This section provides:
# MAGIC
# MAGIC 1. Centralized configuration of runtime manager factories.
# MAGIC 2. Discovery of reference maps for the active environment.

# COMMAND ----------

from oeds.domain.utils.config.config_utils import ConfigManager
from oeds.domain.utils.schema.schema_utils import SchemaManager
from oeds.domain.utils.datafile.datafile_utils import DatafileManager
from oeds.domain.utils.reference.reference_utils import ReferenceManager
from oeds.domain.utils.calendar.calendar_utils import CalendarManager
from oeds.domain.utils.email.email_utils import EmailManager

# Initialize ConfigManager.
logger.info("Configuring config manager for env '%s' ...", _ctx.get("env"))
ConfigManager.initialize(_ctx.get("env"))

# Initialize SchemaManager.
logger.info("Configuring schema manager for env '%s' ...", _ctx.get("env"))
SchemaManager.initialize(
    _ctx.get("env"),
    catalog_mapping={
        "fmd_cat": _ctx["fmd_catalog"],
        "cur_cat": _ctx["cur_catalog"],
        "bap_cat": _ctx["bap_catalog"],
        "sup_cat": _ctx["sup_catalog"],
        "metadata_cat": _ctx["metadata_catalog"],
        "reference_cat": _ctx["reference_catalog"],
        "application_cat": _ctx["application_catalog"],
        "internal_cat": _ctx["internal_catalog"],
    },
    default_catalog=_ctx["catalog"],
)

# Configure DatafileManager.
logger.info("Configuring datafile manager for env '%s' ...", _ctx.get("env"))
DatafileManager.initialize(_ctx.get("env"))

# Configure ReferenceManager.
logger.info(
    "Configuring reference manager for catalog '%s' ...",
    _ctx.get("reference_catalog"),
)
ReferenceManager.initialize(_ctx.get("reference_catalog"))

# Configure CalendarManager.
logger.info(
    "Configuring calendar manager for holiday group '%s' and "
    "timezone '%s' ...",
    _ctx.get("holiday_group"),
    _ctx.get("timezone", DEFAULT_TIMEZONE),
)
CalendarManager.initialize(
    holiday_group=_ctx.get("holiday_group"),
    timezone=_ctx.get("timezone", DEFAULT_TIMEZONE),
)

# Configure EmailManager.
_email_recipient_mappings = parse_json(_ctx.get("email_mappings"))
logger.debug(
    "Configured recipient mapping count: %d",
    len(_email_recipient_mappings),
)
logger.info("Configuring email manager for provider 'logicapp' ...")
EmailManager.initialize(
    provider="logicapp",
    connection={
        "logicapp_url": dbutils.secrets.get(
            scope=_ctx["oeds_secrete_scope"],
            key=_ctx["email_service_url_key"],
        )
    },
    recipient_mappings=_email_recipient_mappings,
)
del _email_recipient_mappings
