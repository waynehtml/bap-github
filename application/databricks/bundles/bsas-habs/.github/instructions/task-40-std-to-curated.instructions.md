---
applyTo: "jobs/dataflow/task_40_std_to_curated.py"
---

# Task 40: Standardized To Curated

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md) and [DataForge Template Guide](../../docs/guide/G001-dataforge-template-guide.md).
4. Consult the [Schema Guide](../../docs/guide/G211-schema-guide.md) when the requested output uses managed tables or views.
5. Inspect [task_40_std_to_curated.py](../../jobs/dataflow/task_40_std_to_curated.py).

## Documentation status

There is no dedicated standardized-to-curated process guide or separate sample notebook. The current task notebook is an intentional placeholder, not a complete implementation example.

## Source-of-truth rules

- Treat the workflow guide as authoritative for this stage's boundary.
- Treat registered schemas and explicit developer requirements as authoritative for curated outputs.
- Do not infer business rules, joins, aggregations, publishing targets, or data grain from filenames or neighboring tasks.

## Implementation behavior

- Require a clear standardized source, curated target, output grain, business transformation, and write behavior before implementing.
- Reuse documented schema and shared data-processing APIs when they support the requested behavior.
- Keep raw parsing and technical standardization in `raw_to_std`.
- Publish only compact task values needed by completion handling or downstream systems.
- Ask for clarification when the required curated contract cannot be resolved from the request and repository context.
