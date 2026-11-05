---
applyTo: "jobs/dataflow/task_10_ingest.py,conf/oeds/config/ingest/**/*.json"
---

# Task 10: Ingest

Before modifying this task or its configuration:

1. Follow the [DataForge instructions](../../AGENTS.md), especially the ingestion configuration rules.
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md) and [DataBridge Client Guide](../../docs/guide/G220-ingest-client-guide.md).
4. Inspect [task_10_ingest.py](../../jobs/dataflow/task_10_ingest.py), which is both the implementation and reference notebook.
5. Inspect:
   - the [default ingestion config](../../conf/oeds/config/ingest/default.json)
   - the version-matched DataBridge top-level and handler schemas
   - relevant examples from the version-matched DataBridge `examples/` directory
   - relevant test evidence from the version-matched DataBridge `tests/config/` directory

## Source-of-truth rules

- Treat DataBridge schemas as authoritative for pipeline and handler configuration.
- Use the DataBridge client guide for client behavior and the workflow guide for the task boundary.
- Use examples as supported patterns and DataBridge test configs only as test evidence, never as production templates.
- If the matching DataBridge source or documentation is unavailable, do not infer unsupported configuration fields; request the DataBridge version and reference source.
- Report conflicts between schemas, documentation, and code before changing the contract.

## Implementation behavior

- Reuse the documented DataBridge client, template rendering, result handling, and verification APIs.
- Preserve DataForge `[[ ... ]]` and DataBridge `{{ ... }}` template ownership.
- Do not copy credentials, environment-specific paths, workspace identifiers, or secret values from examples or tests.
- Keep server orchestration in DataBridge and client preparation, submission, and verification in DataForge.
- Ask for clarification only when source, destination, handler, templating ownership, or verification requirements cannot be resolved from the request and repository context.
