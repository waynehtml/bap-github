# Databricks notebook source
# MAGIC %md
# MAGIC ## Service Main Task
# MAGIC - Resolve a named service task or notebook path from job parameters.
# MAGIC - Validate service arguments.
# MAGIC - Run the requested service notebook and return its result.

# COMMAND ----------

# DBTITLE 1,Show widget for development purpose
# Development-only widgets.
dbutils.widgets.text("debug", "True")
dbutils.widgets.text("rundate", "")
dbutils.widgets.text("task", "")
dbutils.widgets.text("args", "")

# COMMAND ----------

# DBTITLE 1,Common notebook
# MAGIC %run ../../common

# COMMAND ----------

# DBTITLE 1,Import libraries
# Standard-library imports.
import logging
import re
from pathlib import Path

# COMMAND ----------

# DBTITLE 1,Init logging and context
# Initialize the service logger.
logger = logging.getLogger(__name__)

# Load the shared job context.
job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

# MAGIC %md
# MAGIC # Run service notebooks

# COMMAND ----------


def resolve_service_task(bundle_root: str, task: str) -> tuple[str, str, str]:
    """Resolve a service task to notebook execution metadata.

    Args:
        bundle_root: Root directory used to constrain relative notebook paths.
        task: Named service task or explicit notebook path.

    Returns:
        The task type, original task name, and resolved notebook path.

    Raises:
        ValueError: If a task name is invalid or a relative path escapes
            ``bundle_root``.
    """
    # Use the bundle root as the boundary for relative notebook paths.
    bundle_root_path = Path(bundle_root).resolve()

    # Treat path-like task values as explicit notebook paths.
    is_path = (
        task.startswith(("/Workspace", "."))
        or task.endswith(".py")
        or "/" in task
        or "\\" in task
    )

    if is_path:
        # Full workspace paths are already qualified for dbutils.notebook.run.
        if task.startswith("/Workspace"):
            return "notebook_path", task, task

        # Relative paths are resolved below the bundle root and cannot escape it.
        notebook_path = (bundle_root_path / task).resolve()
        notebook_path.relative_to(bundle_root_path)
        return "notebook_path", task, str(notebook_path)

    # Non-path values are named service tasks with a constrained name shape.
    if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9_-]*$", task):
        raise ValueError(
            f"Invalid service task '{task}'. Use letters, numbers, "
            "underscores, or hyphens."
        )

    # Named tasks map to notebooks in the fixed service task folder.
    notebook_path = (
        bundle_root_path / "jobs" / "service" / "tasks" / f"{task}.py"
    ).resolve()
    notebook_path.relative_to(bundle_root_path)
    return "named_task", task, str(notebook_path)


# COMMAND ----------

# Run an explicit notebook path or map a named task to the fixed task folder.
task = job_ctx.get("task", "").strip()
if not task:
    raise ValueError(
        "task must be provided as a notebook path or named service task"
    )

logger.debug(f"task: {task}")
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

bundle_root = job_ctx.get("bundle_root")
logger.debug(f"bundle_root: {bundle_root}")

task_type, task_name, task_path = resolve_service_task(bundle_root, task)
logger.debug(f"task_type: {task_type}")

try:
    logger.info(
        f"Running service {task_type}: {task_name} as notebook: {task_path}"
    )
    result = dbutils.notebook.run(task_path, 0, job_ctx)
    # Skip remaining tasks and continue to the completion handler.
    dbutils.jobs.taskValues.set(key="flow_action", value="complete")
    dbutils.notebook.exit(result)
except Exception as e:
    raise RuntimeError(
        f"Service notebook run failed for {task_type}: {task_name}"
    ) from e
