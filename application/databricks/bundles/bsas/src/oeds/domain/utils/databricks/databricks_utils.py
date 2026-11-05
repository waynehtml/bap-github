"""Read job-run metadata and execute warehouse DDL through the Databricks SDK."""

from __future__ import annotations

import logging
import time
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

logger = logging.getLogger(__name__)


def execute_ddl(
    sql: str,
    warehouse_id: str,
    *,
    catalog: str | None = None,
    schema: str | None = None,
    timeout_seconds: int = 1800,
) -> None:
    """Execute one DDL statement on a SQL warehouse and wait for completion.

    Creates a WorkspaceClient using default SDK authentication. The caller
    supplies DDL; this function does not parse SQL or retrieve result rows.
    Catalog and schema optionally set the statement's resolution context.
    No Spark session is required.

    The deadline includes submission and polling time, but cannot interrupt
    an in-flight SDK request or its retries. On timeout or a polling error,
    cancellation is attempted; receipt does not confirm cancellation or undo
    completed DDL. Use the statement ID to inspect an uncertain outcome.

    Raises:
        TypeError: If an argument has an invalid type.
        ValueError: If required text is blank or the timeout is not positive.
        TimeoutError: If the completion deadline expires.
        RuntimeError: If execution fails or its status cannot be determined.

    Authentication and submission errors propagate. SQL text is not logged.
    """
    for name, value in (
        ("sql", sql),
        ("warehouse_id", warehouse_id),
        ("catalog", catalog),
        ("schema", schema),
    ):
        if value is None and name in ("catalog", "schema"):
            continue
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if not value.strip():
            raise ValueError(f"{name} must not be blank")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
        raise TypeError("timeout_seconds must be an integer")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    client = WorkspaceClient()
    deadline = time.monotonic() + timeout_seconds
    response = client.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=warehouse_id.strip(),
        catalog=catalog.strip() if catalog is not None else None,
        schema=schema.strip() if schema is not None else None,
        wait_timeout="0s",
    )
    statement_id = response.statement_id
    if not statement_id:
        raise RuntimeError("DDL submission returned no statement ID")
    logger.info("Submitted DDL statement '%s'", statement_id)

    while True:
        state = response.status.state if response.status else None
        if state == StatementState.SUCCEEDED:
            logger.info("DDL statement '%s' succeeded", statement_id)
            return None
        if state in (
            StatementState.FAILED,
            StatementState.CANCELED,
            StatementState.CLOSED,
        ):
            error = response.status.error
            detail = error.message if error and error.message else "No error details"
            raise RuntimeError(
                f"DDL statement '{statement_id}' ended in {state}: {detail}"
            )
        if state not in (StatementState.PENDING, StatementState.RUNNING):
            cancellation = _request_statement_cancellation(client, statement_id)
            raise RuntimeError(
                f"DDL statement '{statement_id}' returned unexpected state "
                f"{state}; {cancellation}"
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            cancellation = _request_statement_cancellation(client, statement_id)
            raise TimeoutError(
                f"DDL statement '{statement_id}' exceeded {timeout_seconds} "
                f"seconds; {cancellation}"
            )
        time.sleep(min(2.0, remaining))
        if time.monotonic() >= deadline:
            continue
        try:
            response = client.statement_execution.get_statement(
                statement_id=statement_id
            )
        except Exception as exc:
            cancellation = _request_statement_cancellation(client, statement_id)
            raise RuntimeError(
                f"Could not read status of DDL statement '{statement_id}'; "
                f"{cancellation}"
            ) from exc


def _request_statement_cancellation(
    client: WorkspaceClient, statement_id: str
) -> str:
    """Attempt cleanup without replacing the original execution failure."""
    try:
        client.statement_execution.cancel_execution(statement_id=statement_id)
    except Exception:
        logger.warning("Could not request cancellation for '%s'", statement_id)
        return "cancellation request failed; final execution state is unknown"
    return "cancellation requested; final execution state is unconfirmed"


def get_job_run_trigger_user(job_run_id: str | int) -> str | None:
    """Return the trimmed username that triggered a Databricks job run.

    Args:
        job_run_id: Positive numeric Databricks job-run identifier.

    Returns:
        The run's ``creator_user_name``, or ``None`` when it is unavailable.

    Input validation, Databricks SDK, and authentication errors propagate.
    """
    job_run = _get_job_run(job_run_id)
    return _optional_text(getattr(job_run, "creator_user_name", None))


def get_job_run_page_url(job_run_id: str | int) -> str | None:
    """Return the trimmed Databricks workspace URL for a job run.

    Args:
        job_run_id: Positive numeric Databricks job-run identifier.

    Returns:
        The run's page URL, or ``None`` when it is unavailable.

    Input validation, Databricks SDK, and authentication errors propagate.
    """
    job_run = _get_job_run(job_run_id)
    return _optional_text(getattr(job_run, "run_page_url", None))


def _get_job_run(job_run_id: str | int) -> Any:
    """Load one job run after validating its identifier."""
    normalized_run_id = _normalize_job_run_id(job_run_id)
    return WorkspaceClient().jobs.get_run(run_id=normalized_run_id)


def _normalize_job_run_id(job_run_id: str | int) -> int:
    """Require a positive numeric Databricks job-run identifier."""
    if isinstance(job_run_id, bool) or not isinstance(job_run_id, (str, int)):
        raise TypeError("job_run_id must be a string or integer")

    if isinstance(job_run_id, str):
        normalized_value = job_run_id.strip()
        if not normalized_value or not normalized_value.isdecimal():
            raise ValueError("job_run_id must be a positive integer")
        normalized_run_id = int(normalized_value)
    else:
        normalized_run_id = job_run_id

    if normalized_run_id <= 0:
        raise ValueError("job_run_id must be a positive integer")
    return normalized_run_id


def _optional_text(value: Any) -> str | None:
    """Return trimmed text or ``None`` for unavailable SDK metadata."""
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    return normalized_value or None


def get_job_task_keys(job_id: str | int) -> list[str]:
    """Return top-level task keys from a saved job in API order.

    Intended for jobs with at most 100 tasks; this helper does not request
    additional pages. Referenced jobs and nested loop tasks are not expanded.
    Uses default WorkspaceClient authentication.

    Args:
        job_id: Saved Databricks job identifier, converted with int().

    Returns:
        Configured task keys in API order, or [] when there are no tasks.

    Raises:
        ValueError: If job_id cannot be converted to an integer.
        RuntimeError: If job settings are missing or a task key is malformed.

    SDK, authentication, and job-lookup errors propagate to the caller.
    """
    try:
        normalized_job_id = int(job_id)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("job_id must be convertible to an integer") from exc

    job = WorkspaceClient().jobs.get(job_id=normalized_job_id)
    if job.settings is None:
        raise RuntimeError(f"Job {normalized_job_id} returned no settings")
    task_keys: list[str] = []
    for task in job.settings.tasks or []:
        task_key = task.task_key
        if not isinstance(task_key, str) or not task_key.strip():
            raise RuntimeError(
                f"Job {normalized_job_id} returned an invalid task key"
            )
        task_keys.append(task_key)
    return task_keys


__all__ = [
    "execute_ddl",
    "get_job_run_page_url",
    "get_job_run_trigger_user",
    "get_job_task_keys",
]
