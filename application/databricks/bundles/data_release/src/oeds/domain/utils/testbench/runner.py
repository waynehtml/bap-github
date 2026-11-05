"""Coordinate one DataForge Testbench case from loading through reporting.

The runner owns lifecycle sequencing and the execution log. Environment and
validation helpers retain responsibility for acquiring runtime services such as
the active Spark session.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit

from oeds.domain.utils.testbench.runner_context import RunnerContext

logger = logging.getLogger(__name__)

_CASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_RUN_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SKIP_ARGUMENTS = (
    "skip_setup",
    "skip_run",
    "skip_validate",
    "skip_teardown",
)


class TestbenchRunner:
    """Execute the fixed Testbench lifecycle and capture its Python logs.

    The forward stages are load, setup, run, and validate. Teardown is cleanup
    and is attempted after any of those stages fails once a case has loaded.
    Report is always invoked after teardown as an independent extension point.

    The runner keeps the first lifecycle exception as the primary failure so a
    later cleanup or reporting error cannot hide the original cause.
    """

    def __init__(
        self,
        *,
        dataset: str,
        case_name: str,
        case_root: str,
        args: dict[str, Any] | None = None,
        service_job_ctx: Mapping[str, Any],
    ) -> None:
        """Initialize a caller-owned Testbench runner.

        Args:
            dataset: Dataset being exercised by the case.
            case_name: Case filename without the ``.json`` suffix.
            case_root: Unity Catalog Volume root containing Testbench content.
            args: Optional case-variable overrides and lifecycle skip controls.
            service_job_ctx: Identity and run metadata for the service job.
        """
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise TypeError("args must be a JSON object")
        if not isinstance(service_job_ctx, Mapping):
            raise TypeError("service_job_ctx must be a mapping")

        resolved_case_root = self._normalize_case_root(case_root)
        service_job_run_id = self._normalize_run_identifier(
            service_job_ctx.get("job_run_id"),
            "service_job_ctx.job_run_id",
        )
        self.context = RunnerContext(
            dataset=self._normalize_run_identifier(dataset, "dataset"),
            case_name=self._normalize_case_name(case_name),
            case_root=str(resolved_case_root),
            case_args=dict(args),
            service_job_id=self._normalize_optional_job_id(
                service_job_ctx.get("job_id")
            ),
            service_job_name=self._normalize_optional_text(
                service_job_ctx.get("job_name"),
                "service_job_ctx.job_name",
            ),
            service_job_run_id=service_job_run_id,
            service_job_run_create_user=self._normalize_optional_text(
                service_job_ctx.get("job_run_create_user"),
                "service_job_ctx.job_run_create_user",
            ),
            service_job_run_url=self._normalize_optional_url(
                service_job_ctx.get("job_run_url"),
                "service_job_ctx.job_run_url",
            ),
            service_job_trigger_type=self._normalize_optional_text(
                service_job_ctx.get("job_trigger_type"),
                "service_job_ctx.job_trigger_type",
            ),
        )
        self._skip = {
            argument: self._skip_requested(argument) for argument in _SKIP_ARGUMENTS
        }

        # Lifecycle state is populated as stages complete and is also used to
        # decide which cleanup work is safe after a failure.
        self._test_config: dict[str, Any] | None = None
        self._resource_utils: Any | None = None

        # The handler is tracked explicitly because the live log is detached,
        # renamed, and reopened after Databricks assigns the case-job run ID.
        self._log_handler: logging.FileHandler | None = None

    def execute(self) -> str:
        """Execute all lifecycle stages and return the final absolute log path.

        Returns:
            The provisional log path, or its run-specific replacement when a
            case job was submitted successfully.

        Raises:
            Exception: The first exception raised by a lifecycle stage or log
                cleanup. Its original traceback is preserved.
        """
        primary_error: Exception | None = None
        primary_traceback: TracebackType | None = None
        failed_stage: str | None = None

        self._start_logging()
        self.context.case_started_at = datetime.now(timezone.utc)
        self.context.case_status = "RUNNING"
        try:
            # Forward lifecycle stages are dependency ordered. Once one fails,
            # later forward stages cannot run against incomplete state.
            try:
                self._load()
            except Exception as exc:
                primary_error = exc
                primary_traceback = exc.__traceback__
                failed_stage = "load"
                logger.exception("Testbench case loading failed.")

            if primary_error is None:
                try:
                    self._setup()
                except Exception as exc:
                    primary_error = exc
                    primary_traceback = exc.__traceback__
                    failed_stage = "setup"
                    logger.exception("Testbench setup failed.")

            if primary_error is None:
                try:
                    self._run()
                except Exception as exc:
                    primary_error = exc
                    primary_traceback = exc.__traceback__
                    failed_stage = "run"
                    logger.exception("Testbench run failed.")

            if primary_error is None:
                try:
                    self._validate()
                except Exception as exc:
                    primary_error = exc
                    primary_traceback = exc.__traceback__
                    failed_stage = "validate"
                    logger.exception("Testbench validation failed.")

            # Teardown is cleanup rather than a forward dependency. It remains
            # eligible after failure whenever loading produced a usable case.
            if self._test_config is None:
                logger.info(
                    "Skipping teardown because the Testbench case did not load."
                )
            else:
                try:
                    self._teardown()
                except Exception as exc:
                    if primary_error is None:
                        primary_error = exc
                        primary_traceback = exc.__traceback__
                        failed_stage = "teardown"
                    logger.exception("Testbench teardown failed.")

        finally:
            # The root logger must never retain this execution's file handler.
            try:
                self._stop_logging()
            except Exception as exc:
                if primary_error is None:
                    primary_error = exc
                    primary_traceback = exc.__traceback__
                    failed_stage = "logging"
                logger.exception("Testbench logging cleanup failed.")

        self.context.case_completed_at = datetime.now(timezone.utc)
        self.context.case_duration_seconds = (
            self.context.case_completed_at - self.context.case_started_at
        ).total_seconds()
        self.context.case_error = primary_error
        self.context.case_failed_stage = failed_stage
        self.context.case_status = (
            "FAILED" if primary_error is not None else "SUCCEEDED"
        )

        # Reporting is best-effort and cannot replace the lifecycle result.
        try:
            self._report()
        except Exception:
            logger.warning("Testbench report failed.")

        if primary_error is not None:
            raise primary_error.with_traceback(primary_traceback)
        if self.context.case_log_path is None:
            raise RuntimeError("Testbench execution log path was not initialized.")
        return self.context.case_log_path

    def _load(self) -> None:
        """Load and minimally validate the selected case."""
        from oeds.domain.utils.testbench.config import load_test_case

        test_config = load_test_case(
            case_name=self.context.case_name,
            case_root=self.context.case_root,
            context=self.context.case_args,
        )
        if not isinstance(test_config, dict):
            raise TypeError("Testbench case must resolve to a JSON object.")
        self._test_config = test_config
        logger.info("Testbench case '%s' loaded.", self.context.case_name)

    def _setup(self) -> None:
        """Provision resources for the loaded case unless setup is skipped."""
        if self._skip["skip_setup"]:
            logger.info("Skipping Testbench setup because skip_setup is enabled.")
            return
        self._get_resource_utils().create_resources(self._require_test_config())
        logger.info("Testbench setup completed.")

    def _run(self) -> None:
        """Submit and wait for the Databricks job configured by the case."""
        if self._skip["skip_run"]:
            logger.info("Skipping Testbench run because skip_run is enabled.")
            return

        from databricks_tools_core.jobs import (
            JobError,
            find_job_by_name,
            run_job_now,
            wait_for_run,
        )

        run_config = self._require_mapping(
            self._require_test_config().get("run"),
            "run",
        )
        job_config = self._require_mapping(run_config.get("job"), "run.job")
        self.context.target_job_name = self._require_text(
            job_config.get("name"),
            "run.job.name",
        )

        raw_parameters = job_config.get("parameters") or {}
        if not isinstance(raw_parameters, dict):
            raise ValueError(
                "Testbench case field 'run.job.parameters' must be an object."
            )
        job_parameters = {
            str(name): (
                json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            )
            for name, value in raw_parameters.items()
            if value is not None
        }
        timeout_seconds = int(job_config.get("timeout_seconds") or 3600)
        poll_interval_seconds = int(job_config.get("poll_interval_seconds") or 10)

        logger.info(
            "Finding Databricks job to run: %s",
            self.context.target_job_name,
        )
        self.context.target_job_id = find_job_by_name(self.context.target_job_name)
        if self.context.target_job_id is None:
            raise JobError(f"Job '{self.context.target_job_name}' not found")

        logger.info(
            "Starting Databricks job '%s' with job_id=%s",
            self.context.target_job_name,
            self.context.target_job_id,
        )
        self.context.target_job_run_id = run_job_now(
            job_id=self.context.target_job_id,
            job_parameters=job_parameters,
        )
        self.context.target_job_run_status = "RUNNING"
        logger.info(
            "Started case job run_id=%s; waiting for completion",
            self.context.target_job_run_id,
        )
        self._promote_log_file(self.context.target_job_run_id)

        try:
            run_result = wait_for_run(
                run_id=self.context.target_job_run_id,
                timeout=timeout_seconds,
                poll_interval=poll_interval_seconds,
            )
        except Exception:
            self.context.target_job_run_status = "UNKNOWN"
            raise
        self.context.target_job_run_url = run_result.run_page_url
        self.context.target_job_run_status = (
            run_result.result_state
            or run_result.lifecycle_state
            or "UNKNOWN"
        )
        logger.info("Databricks case job finished: %s", run_result.to_dict())
        if not run_result.success:
            raise JobError(
                run_result.message
                or (
                    f"Job run {self.context.target_job_run_id} did not finish "
                    "successfully."
                ),
                job_id=self.context.target_job_id,
                run_id=self.context.target_job_run_id,
            )

    def _validate(self) -> None:
        """Run the validations configured by the loaded case."""
        if self._skip["skip_validate"]:
            logger.info(
                "Skipping Testbench validation because skip_validate is enabled."
            )
            return

        from oeds.domain.utils.testbench.validation import ValidationRunner

        # Expected paths are execution-specific. Resolve them on a copy so the
        # fully loaded case remains unchanged for teardown and future stages.
        validation_config = copy.deepcopy(self._require_test_config())
        validate_config = validation_config.get("validate") or {}
        if isinstance(validate_config, dict):
            for verification in validate_config.get("verifications") or []:
                if not isinstance(verification, dict):
                    continue
                expected_config = verification.get("expected") or {}
                if not isinstance(expected_config, dict):
                    continue
                expected_path = expected_config.get("path")
                if isinstance(expected_path, str) and expected_path.strip():
                    resolved_path = self._get_resource_utils().resolve_test_path(
                        expected_path
                    )
                    expected_config["path"] = (
                        self._get_resource_utils().spark_source_path(resolved_path)
                    )

        validation_context = {
            "case_name": self.context.case_name,
            "case_root": self.context.case_root,
            "run_job_name": self.context.target_job_name,
            "run_job_id": self.context.target_job_id,
            "run_id": self.context.target_job_run_id,
        }
        ValidationRunner().run(validation_config, context=validation_context)
        logger.info("Testbench validation completed.")

    def _teardown(self) -> None:
        """Remove configured resources unless teardown is skipped."""
        if self._skip["skip_teardown"]:
            logger.info("Skipping Testbench teardown because skip_teardown is enabled.")
            return
        self._get_resource_utils().drop_resources(self._require_test_config())
        logger.info("Testbench teardown completed.")

    def _report(self) -> None:
        """Report the completed lifecycle without changing its outcome."""
        from oeds.domain.utils.testbench.report import ReportUtils

        ReportUtils.report(self.context)

    def _get_resource_utils(self) -> Any:
        """Create environment management lazily so it owns Spark acquisition."""
        if self._resource_utils is None:
            from oeds.domain.utils.testbench.environment import ResourceUtils

            self._resource_utils = ResourceUtils(case_root=self.context.case_root)
        return self._resource_utils

    def _start_logging(self) -> None:
        """Attach a direct file handler for this execution."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_directory = (
            Path(self.context.case_root)
            / "logs"
            / f"{timestamp}_{self.context.service_job_run_id}"
        )
        log_directory.mkdir(parents=True, exist_ok=False)
        log_path = log_directory / f"{self.context.case_name}.log"
        self._log_handler = self._create_log_handler(log_path, mode="x")
        logging.getLogger().addHandler(self._log_handler)
        self.context.case_log_path = str(log_path)
        logger.info("Testbench execution logging started at '%s'.", log_path)

    def _promote_log_file(self, case_job_run_id: int) -> None:
        """Rename the live log after the submitted case job receives an ID."""
        if self.context.case_log_path is None or self._log_handler is None:
            raise RuntimeError("Testbench execution logging is not initialized.")

        current_path = Path(self.context.case_log_path)
        final_path = current_path.with_name(
            f"{self.context.case_name}_{case_job_run_id}.log"
        )
        if final_path.exists():
            raise FileExistsError(f"Testbench log already exists at '{final_path}'.")

        old_path = current_path
        formatter = self._log_handler.formatter
        level = self._log_handler.level
        # Windows and some mounted filesystems cannot rename an open file, so
        # release the handler before promoting the provisional name.
        self._detach_log_handler()
        try:
            old_path.rename(final_path)
            self.context.case_log_path = str(final_path)
            self._log_handler = self._create_log_handler(final_path, mode="a")
        except Exception:
            resume_path = final_path if final_path.exists() else old_path
            self.context.case_log_path = str(resume_path)
            self._log_handler = self._create_log_handler(resume_path, mode="a")
            if formatter is not None:
                self._log_handler.setFormatter(formatter)
            self._log_handler.setLevel(level)
            logging.getLogger().addHandler(self._log_handler)
            raise

        if formatter is not None:
            self._log_handler.setFormatter(formatter)
        self._log_handler.setLevel(level)
        logging.getLogger().addHandler(self._log_handler)
        logger.info("Testbench execution logging continued at '%s'.", final_path)

    def _stop_logging(self) -> None:
        """Flush, detach, and close this runner's file handler."""
        if self._log_handler is None:
            return
        logger.info(
            "Testbench execution logging completed at '%s'.",
            self.context.case_log_path,
        )
        self._detach_log_handler()

    def _detach_log_handler(self) -> None:
        """Detach and close the current file handler."""
        handler = self._log_handler
        if handler is None:
            return
        logging.getLogger().removeHandler(handler)
        try:
            handler.flush()
        finally:
            handler.close()
            self._log_handler = None

    @staticmethod
    def _create_log_handler(path: Path, *, mode: str) -> logging.FileHandler:
        """Create a handler that follows the active root logging format."""
        root_logger = logging.getLogger()
        # Reuse the application's established formatter so the additional file
        # destination has the same record shape as existing logging handlers.
        formatter = next(
            (
                handler.formatter
                for handler in root_logger.handlers
                if handler.formatter is not None
            ),
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s - %(message)s"
            ),
        )
        handler = logging.FileHandler(path, mode=mode, encoding="utf-8")
        handler.setFormatter(formatter)
        return handler

    def _skip_requested(self, argument: str) -> bool:
        """Normalize one Boolean-or-binary-integer skip argument."""
        if argument not in self.context.case_args:
            return False
        value = self.context.case_args[argument]
        if isinstance(value, bool):
            return value
        if type(value) is int:
            if value in (0, 1):
                return bool(value)
            raise ValueError(f"{argument} must be 0, 1, false, or true")
        raise TypeError(f"{argument} must be 0, 1, false, or true")

    def _require_test_config(self) -> dict[str, Any]:
        """Return the loaded case or raise for invalid internal sequencing."""
        if self._test_config is None:
            raise RuntimeError("Testbench case has not been loaded.")
        return self._test_config

    @staticmethod
    def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
        """Read one required object from the case."""
        if not isinstance(value, dict) or not value:
            raise ValueError(f"Testbench case field '{field_name}' is required.")
        return value

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        """Read one required nonblank string from the case."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Testbench case field '{field_name}' is required.")
        return value.strip()

    @staticmethod
    def _normalize_case_name(case_name: str) -> str:
        """Require a safe case filename without a suffix."""
        if not isinstance(case_name, str):
            raise TypeError("case_name must be a string")
        resolved = case_name.strip()
        if not resolved:
            raise ValueError("case_name is required")
        if not _CASE_NAME_PATTERN.fullmatch(resolved):
            raise ValueError(
                "case_name must start with a letter or number and contain only "
                "letters, numbers, underscores, or hyphens"
            )
        return resolved

    @staticmethod
    def _normalize_case_root(case_root: str) -> PurePosixPath:
        """Require an absolute Unity Catalog Volume root."""
        if not isinstance(case_root, str):
            raise TypeError("case_root must be a string")
        value = case_root.strip()
        if not value:
            raise ValueError("case_root is required")
        path = PurePosixPath(value)
        parsed = urlsplit(value)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not path.is_absolute()
            or len(path.parts) < 5
            or path.parts[1] != "Volumes"
            or ".." in path.parts
            or "*" in value
            or "\\" in value
            or "\x00" in value
        ):
            raise ValueError(
                "case_root must be an absolute "
                "/Volumes/<catalog>/<schema>/<volume>/... path"
            )
        return path

    @staticmethod
    def _normalize_run_identifier(value: str | int, name: str) -> str:
        """Require a safe identifier for a log-directory path component."""
        if value is None:
            raise ValueError(f"{name} is required")
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise TypeError(f"{name} must be a string or integer")
        resolved = str(value).strip()
        if not resolved:
            raise ValueError(f"{name} is required")
        if not _RUN_IDENTIFIER_PATTERN.fullmatch(resolved):
            raise ValueError(
                f"{name} must contain only letters, numbers, dots, underscores, "
                "or hyphens"
            )
        return resolved

    @staticmethod
    def _normalize_optional_job_id(value: Any) -> str | int | None:
        """Normalize an optional service job identifier."""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise TypeError("service_job_ctx.job_id must be a string or integer")
        if isinstance(value, int):
            return value
        resolved = value.strip()
        return resolved or None

    @staticmethod
    def _normalize_optional_text(value: Any, name: str) -> str | None:
        """Normalize optional service metadata text."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        return value.strip() or None

    @classmethod
    def _normalize_optional_url(cls, value: Any, name: str) -> str | None:
        """Normalize an optional absolute HTTP(S) URL."""
        resolved = cls._normalize_optional_text(value, name)
        if resolved is None:
            return None
        parsed = urlsplit(resolved)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{name} must be an absolute HTTP(S) URL")
        return resolved


__all__ = ["TestbenchRunner"]
