# Databricks notebook source
# MAGIC %run ../../common

# COMMAND ----------

import json

from databricks.sdk.runtime import dbutils
from oeds.domain.utils.email import EmailManager
from oeds.domain.utils.ingest.ingest_utils import DisConnectionOptions

job_ctx = get_job_context()

# COMMAND ----------

# Configure the service identity through bundle variables before running this example.
dis_connection = DisConnectionOptions(
    host=job_ctx["internal_databricks_workspace_url"],
    azure_tenant_id=job_ctx["azure_tenant_id"],
    azure_client_id=dbutils.secrets.get(
        scope=job_ctx["secrete_scope"], key=job_ctx["service_spn_id_key"]
    ),
    azure_client_secret=dbutils.secrets.get(
        scope=job_ctx["secrete_scope"], key=job_ctx["service_spn_secrete_key"]
    ),
    azure_workspace_resource_id=job_ctx["internal_databricks_resource_id"],
    dis_job_id=int(job_ctx["internal_dis_job_id"]),
)
EmailManager.initialize(
    provider="databridge",
    connection={
        "dis_connection": dis_connection,
        "ingest_config_file": "email.json",
        "tmp_root": job_ctx["tmp_root"],
        "job_run_id": job_ctx["job_run_id"],
        "sender_email": job_ctx["databridge_email_sender_account"],
        "graph_secret_scope": job_ctx["oeds_secrete_scope"],
        "graph_tenant_id_key": job_ctx["databridge_email_tenant_id_key"],
        "graph_client_id_key": job_ctx["databridge_email_client_id_key"],
        "graph_client_secret_key": job_ctx["databridge_email_client_secret_key"],
        "wait_timeout_sec": 1800,
        "wait_poll_sec": 10,
        "max_total_attachment_bytes": 10485760,
    },
    config_file="default.json",
    recipient_mappings=json.loads(job_ctx["email_mappings"]),
)
email_manager = EmailManager.get_instance()

# COMMAND ----------

# This cell submits an email job and waits for it to finish.
email_manager.send_email(
    template_ref="failure",
    variables={
        "ENV": job_ctx["env"].upper(),
        "audit_skey": "example",
        "code": "EXAMPLE_NOTIFICATION",
        "state": "EXAMPLE",
        "message": "DataBridge email provider example.",
        "email_table_html": "",
    },
    attachments=[{"name": "details.csv", "content": "step,status\nexample,complete\n"}],
)

# COMMAND ----------

# Direct emails use the same provider without loading a registry entry.
# Set explicit recipients before running this optional example.
# email_manager.send_direct_email(
#     recipients=["team@example.com"],
#     subject="DataBridge email example",
#     body="<p>Example completed.</p>",
# )
