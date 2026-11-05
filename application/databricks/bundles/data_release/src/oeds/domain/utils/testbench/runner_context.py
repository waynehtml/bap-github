"""Runtime state shared by Testbench lifecycle and reporting components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RunnerContext:
    """Keep the mutable execution state for one Testbench case."""

    dataset: str

    case_name: str
    case_root: str
    case_args: dict[str, Any] = field(default_factory=dict)
    case_status: str = "PENDING"
    case_failed_stage: str | None = None
    case_error: Exception | None = None
    case_started_at: datetime | None = None
    case_completed_at: datetime | None = None
    case_duration_seconds: float | None = None
    case_log_path: str | None = None

    service_job_id: str | int | None = None
    service_job_name: str | None = None
    service_job_run_id: str = ""
    service_job_run_create_user: str | None = None
    service_job_run_url: str | None = None
    service_job_trigger_type: str | None = None

    target_job_id: int | None = None
    target_job_name: str | None = None
    target_job_run_id: int | None = None
    target_job_run_url: str | None = None
    target_job_run_status: str | None = None


__all__ = ["RunnerContext"]
