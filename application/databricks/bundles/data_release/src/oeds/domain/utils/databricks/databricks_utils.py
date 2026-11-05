"""Read job-run metadata through the Databricks SDK."""

from __future__ import annotations

from typing import Any

from databricks.sdk import WorkspaceClient


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


__all__ = ["get_job_run_page_url", "get_job_run_trigger_user"]
