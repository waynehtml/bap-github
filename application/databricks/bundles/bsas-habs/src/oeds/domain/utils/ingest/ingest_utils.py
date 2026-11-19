"""Packaged configuration and synchronous DataBridge ingestion utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from oeds.domain.exceptions import IngestTaskError
import oeds.domain.utils.config.config_utils as config_utils

from .client.dis_client import DisClient
from .client.ingest_result import IngestResult
from .client.verify_result import VerifyResult

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_FILE = "default.json"
_DEFAULT_CONFIG_PACKAGE = "oeds.config.ingest"


@dataclass(frozen=True)
class DisConnectionOptions:
    """Connection and authentication settings used to create a DataBridge client."""

    host: str
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str = field(repr=False)
    azure_workspace_resource_id: str
    dis_job_id: int


@dataclass(frozen=True)
class FileVerificationOptions:
    """Settings for verifying files produced by a successful ingestion run."""

    upload_task_key: str = "upload"
    dest_root: str | None = None
    land_root: str | None = None
    timeout_sec: int = 300
    poll_sec: int = 10


@dataclass(frozen=True)
class IngestTaskResult:
    """Successful ingestion result and its optional verification result."""

    ingest_result: IngestResult
    verify_result: VerifyResult | None


def load_config(filename: str = _DEFAULT_CONFIG_FILE) -> str:
    """Load one packaged ingestion config file as a UTF-8 string."""
    if not filename or not str(filename).strip():
        raise ValueError("filename is required")

    config_name = str(filename).strip()
    package_name = _DEFAULT_CONFIG_PACKAGE
    logger.info(
        "Loading ingestion config '%s' from package '%s'", config_name, package_name
    )

    config_manager = config_utils.ConfigManager.get_instance(package_name)
    config_text = config_manager.load_config_resource(config_name)
    logger.debug(
        "Loaded ingestion config '%s' from package '%s' with %s characters",
        config_name,
        package_name,
        len(config_text),
    )
    return config_text


def run_ingest(
    *,
    connection: DisConnectionOptions,
    template_params: dict[str, Any],
    config_file: str | None = None,
    config_template: str | None = None,
    rundate: date | None = None,
    service_params: dict[str, Any] | None = None,
    debug: bool = True,
    wait_timeout_sec: int = 1800,
    wait_poll_sec: int = 10,
    verification: FileVerificationOptions | None = (
        FileVerificationOptions()  # noqa: B008
    ),
) -> IngestTaskResult:
    """Resolve a DataBridge config source, run ingestion, and verify its files.

    Args:
        connection: Connection and authentication settings for the DataBridge job.
        template_params: Values used to render client-side templates.
        config_file: Relative filename or path in the packaged
            ``oeds.config.ingest`` resources. Mutually exclusive with
            ``config_template``.
        config_template: Raw JSON template text. Mutually exclusive with
            ``config_file``.
        rundate: Optional business date forwarded to DataBridge.
        service_params: Optional parameters exposed to the DataBridge runtime.
        debug: Whether DataBridge debug behavior is enabled.
        wait_timeout_sec: Maximum time to wait for ingestion completion.
        wait_poll_sec: Interval between ingestion status polls.
        verification: File verification settings, or ``None`` to skip verification.

    Returns:
        The successful ingestion result and optional verification result.

    Raises:
        IngestTaskError: If the config source is ambiguous or missing, or if
            loading, client creation, rendering, ingestion, status handling,
            or verification fails.
    """
    if (config_file is None) == (config_template is None):
        raise IngestTaskError(
            "Provide exactly one of config_file or config_template."
        )

    resolved_config_template = config_template
    if config_file is not None:
        try:
            resolved_config_template = load_config(config_file)
        except Exception as exc:
            raise IngestTaskError(
                f"Failed to load ingestion config file '{config_file}'."
            ) from exc

    if resolved_config_template is None:
        raise IngestTaskError("Failed to resolve the ingestion config source.")

    try:
        dis_client = DisClient(
            host=connection.host,
            azure_tenant_id=connection.azure_tenant_id,
            azure_client_id=connection.azure_client_id,
            azure_client_secret=connection.azure_client_secret,
            azure_workspace_resource_id=connection.azure_workspace_resource_id,
            dis_job_id=connection.dis_job_id,
        )
    except Exception as exc:
        raise IngestTaskError("Failed to create DataBridge client.") from exc

    try:
        resolved_config = dis_client.resolve_config_template(
            config_template=resolved_config_template,
            template_params=template_params,
        )
    except Exception as exc:
        raise IngestTaskError("Failed to resolve ingestion config file.") from exc

    try:
        ingest_result = dis_client.ingest(
            config=resolved_config,
            rundate=rundate,
            params=service_params,
            debug=debug,
            wait=True,
            wait_timeout_sec=wait_timeout_sec,
            wait_poll_sec=wait_poll_sec,
        )
    except Exception as exc:
        raise IngestTaskError("Failed to call the DataBridge ingestion service.") from exc

    ingest_status = ingest_result.get_status()
    job_run_id = ingest_result.get_job_run_id()
    run_page_url = ingest_result.get_job_run_page_url()
    logger.info(
        "Ingestion returned status=%s, job_run_id=%s, run_page_url=%s",
        ingest_status,
        job_run_id,
        run_page_url,
    )

    if ingest_status == "TIMEOUT":
        raise IngestTaskError(
            "DataBridge ingestion service timed out while waiting for "
            f"job_run_id={job_run_id}, "
            f"run_page_url={run_page_url or 'unavailable'}. "
            "The Databricks job may still be running."
        )

    if ingest_status == "FAILED":
        task_run_id = ingest_result.get_task_run_id()
        task_run_error = ingest_result.get_task_run_error()
        task_run_error_trace = ingest_result.get_task_run_error_trace()
        logger.info(
            "Ingestion failed with job_run_id=%s, task_run_id=%s, "
            "run_page_url=%s, error=%s",
            job_run_id,
            task_run_id,
            run_page_url,
            task_run_error,
        )
        if task_run_error_trace:
            logger.info("Ingestion task error trace:\n%s", task_run_error_trace)
        raise IngestTaskError(
            f"DataBridge ingestion service failed for job_run_id={job_run_id}, "
            f"task_run_id={task_run_id}, "
            f"run_page_url={run_page_url or 'unavailable'}, "
            f"error={task_run_error or 'unavailable'}."
        )

    if ingest_status != "SUCCESS":
        raise IngestTaskError(
            f"Unhandled ingestion status '{ingest_status}' for "
            f"job_run_id={job_run_id}, "
            f"run_page_url={run_page_url or 'unavailable'}."
        )

    logger.info(
        "Ingestion succeeded with job_run_id=%s, task_run_id=%s, run_page_url=%s",
        job_run_id,
        ingest_result.get_task_run_id(),
        run_page_url,
    )

    verify_result: VerifyResult | None = None
    if verification is not None:
        try:
            verify_result = dis_client.verify_file_by_file_size(
                dest_dir_path=verification.dest_root,
                land_dir_path=verification.land_root,
                timeout_sec=verification.timeout_sec,
                poll_sec=verification.poll_sec,
                upload_task_key=verification.upload_task_key,
            )
        except Exception as exc:
            raise IngestTaskError("Failed to verify landed files.") from exc

    if verify_result is not None:
        logger.info(
            "File verification returned status=%s, expected=%s, "
            "matched=%s, unmatched=%s",
            verify_result.status,
            verify_result.expected,
            verify_result.matched,
            verify_result.unmatched,
        )
        if not verify_result.is_success:
            raise IngestTaskError(
                "File verification did not complete successfully. "
                f"status={verify_result.status}, "
                f"matched={len(verify_result.matched)}, "
                f"unmatched={len(verify_result.unmatched)}"
            )

    return IngestTaskResult(
        ingest_result=ingest_result,
        verify_result=verify_result,
    )


__all__ = [
    "DisConnectionOptions",
    "FileVerificationOptions",
    "IngestTaskResult",
    "load_config",
    "run_ingest",
]
