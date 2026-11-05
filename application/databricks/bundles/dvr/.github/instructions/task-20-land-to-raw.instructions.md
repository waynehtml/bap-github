---
applyTo: "jobs/dataflow/task_20_land_to_raw.py"
---

# Task 20: Land To Raw

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md), [Land To Raw Flow Guide](../../docs/guide/G230-land-to-raw-flow-guide.md), and [Landing Zone Best Practices](../../docs/standards-and-practices/landing_zone_best_practices.md).
4. Inspect [task_20_land_to_raw.py](../../jobs/dataflow/task_20_land_to_raw.py), which is both the implementation and reference notebook.

## Source-of-truth rules

- Treat the land-to-raw guide as authoritative for validation order, supported copy choices, and stage boundaries.
- Use the workflow guide for task values and orchestration behavior.
- Treat the task notebook as the current reference implementation. Report conflicts with documentation before proceeding.

## Implementation behavior

- Select existing documented file validation and copy functions that match the developer's requested file pattern, recursion, and copy behavior.
- Complete validation before copying so validation failures leave raw storage unchanged.
- Copy durable landing files; do not move or delete them.
- Keep parsing, standardization, business validation, and table loading in later tasks.
- Ask for clarification only when file selection or copy behavior materially affects the documented implementation choice and cannot be resolved from repository context.
