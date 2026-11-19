# Databricks notebook source
# Put DataForge's src on the Python path; supply the parameters in README.md.
import logging
import uuid

from oeds.domain.utils.otel_logging.otel_logging_utils import (
    ZerobusLoggingConfig, configure_logging,
)


def parameter(name):
    value = dbutils.widgets.get(name)  # noqa: F821 (provided by Databricks)
    if not value or "{{" in value:
        raise ValueError(f"Missing/unresolved notebook task parameter: {name}")
    return value


context = {
    "databricks.job.id": parameter("job_id"),
    "databricks.job.run_id": parameter("job_run_id"),
    "databricks.task.name": parameter("task_name"),
    "databricks.task.run_id": parameter("task_run_id"),
}
runtime = configure_logging(
    tenant_id=parameter("logging_entra_tenant_id"),
    client_id=parameter("logging_entra_client_id"),
    client_secret=dbutils.secrets.get(  # noqa: F821
        scope=parameter("logging_secret_scope"),
        key=parameter("logging_secret_key"),
    ),
    workspace_url=parameter("zerobus_workspace_url"),
    table_name=parameter("zerobus_table_name"),
    config=ZerobusLoggingConfig(
        endpoint=parameter("zerobus_endpoint"),
        service_name="dataforge",
        resource_attributes=context,
    ),
)
logger = logging.getLogger("dataforge")
marker = str(uuid.uuid4())
try:
    # Replace these smoke-test statements with your existing task body.
    logger.info("DataForge logging smoke test", extra={"smoke_test_id": marker})
    logger.info("Task completed", extra={"smoke_test_id": marker})
except Exception:
    logger.exception("Task failed", extra={"smoke_test_id": marker})
    raise
finally:
    # Keep cleanup with the task body, not in a later cell that may not execute.
    report = runtime.shutdown()
    print("Logging smoke-test marker:", marker)
    print("SDK outcome counters (not Delta verification):", report)
