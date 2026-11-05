---
applyTo: "jobs/dataflow/task_50_integrate.py"
---

# Task 50: Integrate

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the
   [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md) and
   [DataForge Template Guide](../../docs/guide/G001-dataforge-template-guide.md).
4. Read the
   [DataBridge reference](../../docs/reference/databridge/docs/README.md)
   before adding DataBridge delivery behavior.
5. Inspect [task_50_integrate.py](../../jobs/dataflow/task_50_integrate.py).

## Documentation status

There is no dedicated DataFlow integration process guide or separate sample
notebook. The current task notebook is an intentional successful no-op
placeholder. The Curation integration task is independent and is not a
DataFlow implementation reference.

## Source-of-truth rules

- Treat `resources/jobs/dataflow.yml` as authoritative for integration gating,
  stage skips, and lifecycle routing.
- Require explicit integration sources, consumers, output contracts, delivery
  targets, and retry behavior before replacing the placeholder.
- Do not infer integration behavior from the Curation workflow or copy its
  project-specific reference implementation into DataFlow.

## Implementation behavior

- Keep curation transformations and aggregations in `std_to_curated`; use this
  task for explicitly requested dissemination, export, or delivery behavior.
- Preserve integration-only reruns from existing curated data unless the
  developer explicitly changes the workflow contract.
- Keep the structured `not_configured` result until concrete integration
  requirements are available.
- Raise errors for failed required integrations so the workflow reaches
  `on_failure`; do not return partial success.
- Ask for clarification when sources, consumers, formats, delivery targets,
  credentials, idempotency, or retry behavior cannot be resolved from the
  request and repository context.
