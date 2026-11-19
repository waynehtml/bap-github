---
applyTo: "jobs/dataflow/task_30_raw_to_std.py"
---

# Task 30: Raw To Standardized

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md) and [Raw To Standardized Flow Guide](../../docs/guide/G240-raw-to-standardized-flow-guide.md).
4. Consult the [Datafile Guide](../../docs/guide/G225-datafile-developer-guide.md) and [DataFrame Validator Guide](../../docs/guide/G245-dataframe-validator-guide.md) for the APIs selected by the requested implementation.
5. Inspect [task_30_raw_to_std.py](../../jobs/dataflow/task_30_raw_to_std.py), which is both the implementation and reference notebook.

## Source-of-truth rules

- Treat registered datafile and table definitions as authoritative for source and target contracts.
- Use the raw-to-standardized guide for stage order, audit fields, validation, and Delta loading behavior.
- Use API-specific guides for supported functions and parameters.
- Report conflicts between registered contracts, documentation, and the reference notebook before proceeding.

## Implementation behavior

- Preserve the read, transform, audit, validate, then load sequence.
- Reuse documented DatafileManager, DataFrame utility, validation, and Delta load APIs.
- Fail before writing when source parsing, transformation, or business validation fails.
- Preserve required and recommended audit columns and idempotent batch-loading behavior.
- Do not add curated business publishing that belongs to the next task.
- Ask for clarification only when source registry, transformation, validation, target table, or batch semantics cannot be resolved from the request and repository context.
