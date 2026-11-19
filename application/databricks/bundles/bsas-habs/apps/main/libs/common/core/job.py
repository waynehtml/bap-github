"""Databricks job operations using a caller-supplied workspace SDK client."""

import logging
from typing import Any

from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)


class DatabricksJobClient:
    """Start, cancel, and inspect runs using a caller-owned authenticated client.

    Authentication is configured separately through create_workspace_client.
    SDK errors propagate to the caller.
    """

    def __init__(self, *, client: WorkspaceClient, job_id: int) -> None:
        """Use the supplied client and validate the configured job ID.

        Args:
            client: Authenticated workspace SDK client owned by the caller.
            job_id: Positive integer ID of the job to start and list runs for.

        Raises:
            ValueError: job_id is not a positive integer.

        Example:
            from libs.common.core.workspace import create_workspace_client

            workspace = create_workspace_client(
                host=workspace_host,
                auth_mode="obo",
                user_token=user_token,
            )
            client = DatabricksJobClient(client=workspace, job_id=job_id)
            run_id = client.run(job_parameters={"task": "refresh"})
        """
        if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
            raise ValueError("job_id must be a positive integer.")
        self.job_id = job_id
        self.client = client
        logger.info("Initialized job client for job %s.", self.job_id)

    def _extract_job_status(self, run_obj: Any) -> str:
        """Return RUNNING, FAILED, or SUCCESS as a string.

        Pending, waiting, and terminating runs count as RUNNING. Successful
        terminal runs include SUCCESS_WITH_FAILURES. Other terminal outcomes,
        including cancellation and skipping, count as FAILED. Missing or
        unsupported status raises instead of inventing an outcome.

        Args:
            run_obj: An SDK job run or task run object. Prefer its current
                status model, falling back to legacy state fields when absent.

        Returns:
            A plain string: RUNNING, FAILED, or SUCCESS. RUNNING means the run
            is still active, including preparation, retry waits, and cleanup.

        Raises:
            RuntimeError: Lifecycle information is missing or unsupported, or
                a terminated run has no result code to determine its outcome.
        """
        run_status = getattr(run_obj, "status", None)
        legacy_state = getattr(run_obj, "state", None)
        lifecycle = getattr(run_status, "state", None)
        if lifecycle is None:
            lifecycle = getattr(legacy_state, "life_cycle_state", None)
        # SDK fields may be enums; compare their values as plain strings.
        lifecycle = getattr(lifecycle, "value", lifecycle)
        termination = getattr(run_status, "termination_details", None)
        result = getattr(termination, "code", None)
        if result is None:
            result = getattr(legacy_state, "result_state", None)
        result = getattr(result, "value", result)

        if lifecycle in {
            "BLOCKED",
            "PENDING",
            "QUEUED",
            "RUNNING",
            "TERMINATING",
            "WAITING",
            "WAITING_FOR_RETRY",
        }:
            status = "RUNNING"
        elif lifecycle in {"SKIPPED", "INTERNAL_ERROR"}:
            status = "FAILED"
        elif lifecycle == "TERMINATED" and result:
            status = (
                "SUCCESS"
                if result in {"SUCCESS", "SUCCESS_WITH_FAILURES"}
                else "FAILED"
            )
        else:
            raise RuntimeError("Run status is missing or cannot be classified.")

        return status

    def _extract_job_parameters(self, run: Any) -> dict[str, str | None]:
        """Return job parameters under their original names and values.

        JSON text remains a string; no decoding or flattening occurs. This
        preserves the values supplied to the job and avoids key collisions.
        Args:
            run: SDK run containing a job_parameters collection.

        Returns:
            Parameter names mapped to their original string values, or None
            for absent values. No parameters produces an empty dictionary.
            For example, an args value of '{"date": "2026-01-01"}' stays a
            string stored under args rather than becoming a top-level date.

        Raises:
            RuntimeError: A parameter name is missing or duplicated.
        """
        parameters = {}
        for parameter in getattr(run, "job_parameters", None) or []:
            name = getattr(parameter, "name", None)
            if not isinstance(name, str) or not name:
                raise RuntimeError("Job parameter is missing its name.")
            if name in parameters:
                raise RuntimeError("Job parameters contain duplicate names.")
            parameters[name] = getattr(parameter, "value", None)
        return parameters

    def _extract_task_error(self, run: Any, status: str) -> str | None:
        """Collect actual task failures for a run with an already normalized status.

        Args:
            run: SDK job run whose tasks will be inspected. Child runs and task
                output are fetched as needed, so this helper performs API I/O.
            status: The parent run's RUNNING, FAILED, or SUCCESS classification.
                Used for the job-level fallback when no task error is found.

        Returns:
            One string with task-labeled errors separated by blank lines, or
            None if no error is available. Prefer task output and stack traces;
            fall back to task termination messages and then the failed job's
            termination message. Missing error text does not imply success.

        Skip tasks excluded by dependencies or conditions. Follow nested jobs
        and for-each iterations to identify the task that actually failed.
        A job classified as SUCCESS may still contain failed intermediate tasks.
        Error collection covers the task data returned by the installed SDK.

        Raises:
            RuntimeError: A task's status cannot be classified. SDK errors also
                propagate rather than returning a partially collected result.
        """
        errors = []
        tasks = list(getattr(run, "tasks", None) or [])
        pending_tasks = [
            (task, getattr(task, "task_key", None) or str(task.run_id))
            for task in tasks
        ]

        for task, label in pending_tasks:
            task_status = self._extract_job_status(task)
            if task_status != "FAILED":
                continue
            termination = getattr(
                getattr(task, "status", None), "termination_details", None
            )
            legacy_state = getattr(task, "state", None)
            code = getattr(termination, "code", None)
            if code is None:
                code = getattr(legacy_state, "result_state", None)
            code = getattr(code, "value", code)
            # Dependency skips describe consequences, not the originating failure.
            if code in {
                "SKIPPED",
                "EXCLUDED",
                "DISABLED",
                "UPSTREAM_FAILED",
                "UPSTREAM_CANCELED",
                "MAX_CONCURRENT_RUNS_EXCEEDED",
                "MAXIMUM_CONCURRENT_RUNS_REACHED",
                "MAX_JOB_QUEUE_SIZE_EXCEEDED",
            }:
                continue

            message = getattr(termination, "message", None) or getattr(
                legacy_state, "state_message", None
            )
            task_run_id = getattr(task, "run_id", None)
            if task_run_id is not None:
                if getattr(task, "for_each_task", None) is not None:
                    task_run = self.client.jobs.get_run(run_id=task_run_id)
                    iterations = getattr(task_run, "iterations", None) or []
                    if iterations:
                        # Extending this list lets the loop visit child iterations.
                        pending_tasks.extend(
                            (iteration, f"{label}/{iteration.run_id}")
                            for iteration in iterations
                        )
                        continue
                else:
                    output = self.client.jobs.get_run_output(run_id=task_run_id)
                    child_run_id = getattr(
                        getattr(output, "run_job_output", None), "run_id", None
                    )
                    if child_run_id is not None:
                        # The child job holds the underlying task error.
                        child_status = self.get_run_status(child_run_id)
                        message = (
                            child_status["task_error"]
                            or getattr(output, "error", None)
                            or message
                        )
                    else:
                        output_error = getattr(output, "error", None)
                        trace = getattr(output, "error_trace", None)
                        if trace:
                            # Tracebacks often already contain the error summary.
                            message = (
                                f"{output_error}\n{trace}"
                                if output_error and output_error not in trace
                                else trace
                            )
                        else:
                            message = output_error or message
            if message:
                errors.append(f"{label}: {message}")

        # Startup or scheduling failures may have no task output at all.
        if not errors and status == "FAILED":
            termination = getattr(
                getattr(run, "status", None), "termination_details", None
            )
            message = getattr(termination, "message", None) or getattr(
                getattr(run, "state", None), "state_message", None
            )
            if message:
                errors.append(message)

        return "\n\n".join(errors) if errors else None

    def run(
        self,
        *,
        job_parameters: dict[str, str] | None = None,
        idempotency_token: str | None = None,
    ) -> int:
        """Submit a job run and return its ID without waiting for completion.

        Args:
            job_parameters: String parameter names and values passed to the job.
            idempotency_token: Optional SDK idempotency token. Reuse the same
                token when retrying the same logical submission.

        Returns:
            The submitted run ID, which can be passed to get_run_status.
            A returned ID confirms submission, not successful completion.

        Raises:
            RuntimeError: Submission returns no run ID. SDK errors propagate.
        """
        run = self.client.jobs.run_now(
            job_id=self.job_id,
            job_parameters=job_parameters,
            idempotency_token=idempotency_token,
        )
        run_id = run.response.run_id
        if run_id is None:
            raise RuntimeError("Job submission did not return a run ID.")
        logger.info("Started job %s (run_id=%s).", self.job_id, run_id)
        return run_id

    def cancel(self, run_id: int) -> None:
        """Request cancellation of a run without waiting for it to terminate.

        Args:
            run_id: Job or task run ID accepted by the Jobs API.

        Cancellation is asynchronous. Call get_run_status to observe the final
        outcome; successful submission of this request does not mean it has
        finished. The SDK checks permissions and propagates request failures.
        """
        self.client.jobs.cancel_run(run_id=run_id)
        logger.info("Requested cancellation of run %s.", run_id)

    def get_active_run(self) -> int | None:
        """Return the most recently started active run ID, or None if absent.

        Restrict the lookup to the configured job_id and use the Jobs API's
        descending start-time ordering. This is a snapshot, not a lock against
        concurrent submissions; the SDK's active_only filter defines activity.
        """
        runs = self.client.jobs.list_runs(job_id=self.job_id, active_only=True, limit=1)
        for run in runs:
            return run.run_id
        logger.info("No active run found for job %s.", self.job_id)
        return None

    def get_last_run(self) -> int | None:
        """Return the latest completed run by start time, or None if absent.

        Restrict the lookup to the configured job_id. Completed runs include
        successful and unsuccessful outcomes. Ordering is by start time, so
        this does not necessarily select the run that finished most recently.
        """
        runs = self.client.jobs.list_runs(
            job_id=self.job_id, completed_only=True, limit=1
        )
        for run in runs:
            return run.run_id
        logger.info("No completed run found for job %s.", self.job_id)
        return None

    def get_recent_job_status(self) -> dict[str, Any] | None:
        """Return the latest active run, otherwise the latest completed run.

        Searches the configured Databricks workflow. Returns None if no run exists. The result contains get_run_status
        fields plus active_or_completed, recording which lookup found the run.
        A run may finish between lookup and status retrieval; use status for
        its actual state. SDK and status-extraction errors propagate.
        """
        run_id = self.get_active_run()
        active_or_completed = "active"
        if run_id is None:
            run_id = self.get_last_run()
            active_or_completed = "completed"
        if run_id is None:
            return None

        job_status = self.get_run_status(run_id)
        job_status["active_or_completed"] = active_or_completed
        return job_status

    def get_run_status(self, run_id: int) -> dict[str, Any]:
        """Return a job run summary with its actual task failure details.

        Args:
            run_id: Positive job run ID. If a task run ID is supplied, retrieve
                its parent job run so the result summarizes the whole job.
                This lookup is not restricted to the constructor's job_id.

        Returns:
            A dictionary containing exactly these fields:
                job_id: ID of the job returned by the API.
                job_run_id: ID of the parent job run being summarized.
                job_parameters: Original parameter names and string values.
                status: RUNNING, FAILED, or SUCCESS.
                start_time: Start timestamp in Unix epoch milliseconds.
                end_time: End timestamp in Unix epoch milliseconds; may be 0
                    while active.
                run_duration: SDK-reported duration in milliseconds, including
                    repairs. It is not computed from the timestamps here.
                task_error: Task-labeled failures and available traces, or None.

            Missing timing fields remain None. SUCCESS_WITH_FAILURES maps to
            SUCCESS, so a successful job can still contain task_error text.

        Raises:
            ValueError: run_id is not a positive integer.
            RuntimeError: Identifiers or classifiable status are missing, or
                job parameter names are invalid. SDK errors propagate.

        This method may make multiple API calls to resolve parent runs and
        collect task errors. It does not log parameter values or error payloads.

        Example:
            summary = client.get_run_status(run_id)
            status = summary["status"]
            task_error = summary["task_error"]
        """
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            raise ValueError("run_id must be a positive integer.")
        run = self.client.jobs.get_run(run_id=run_id)
        parent_run_id = getattr(run, "job_run_id", None)
        # Task metadata alone does not describe the overall job outcome.
        if parent_run_id is not None and parent_run_id != run.run_id:
            run = self.client.jobs.get_run(run_id=parent_run_id)
        if run.job_id is None or run.run_id is None:
            raise RuntimeError("Job run metadata is missing job_id or run_id.")
        status = self._extract_job_status(run)
        parameters = self._extract_job_parameters(run)
        task_error = self._extract_task_error(run, status)

        return {
            "job_id": run.job_id,
            "job_run_id": run.run_id,
            "job_parameters": parameters,
            "status": status,
            "start_time": getattr(run, "start_time", None),
            "end_time": getattr(run, "end_time", None),
            "run_duration": getattr(run, "run_duration", None),
            "task_error": task_error,
        }
