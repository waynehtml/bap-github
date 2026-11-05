---
applyTo: "jobs/dataflow/task_00_main.py"
---

# Task 00: Main

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md).
4. Read the [Calendar Guide](../../docs/guide/G301-calendar-guide.md) when changing holiday, processing-date, or calendar behavior.
5. Inspect [task_00_main.py](../../jobs/dataflow/task_00_main.py), which is both the implementation and reference notebook.

## Source-of-truth rules

- Treat `resources/jobs/dataflow.yml` as authoritative for workflow parameters, dependencies, and task wiring.
- Use the workflow guide for the `main` stage boundary and the calendar guide for documented calendar APIs.
- Treat the task notebook as the current implementation. Report conflicts between code and documentation instead of silently choosing one.

## Implementation behavior

- Keep run-level decisions, shared processing dates, paths, and compact downstream task values in this task.
- Use `flow_action=complete` only for successful early completion; raise a task-specific exception for real failures.
- Do not add ingestion, transformation, or publishing work that belongs to downstream tasks.
- Ask for clarification only when the requested business-date or early-completion rule cannot be determined from the request and repository context.
