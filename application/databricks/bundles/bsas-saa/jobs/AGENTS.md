# Job Instructions

## Shared job guidance

- Inspect the affected workflow under `../resources/jobs/` and its owning
  guide before changing task parameters, dependencies, or lifecycle routing.
  Preserve its contracts and report conflicts between code and documentation.
- Keep task outputs compact and structured. Use the project-owned task's
  actual behavior and requirements rather than copying another workflow.

## DataFlow only

The following rules apply only to the named tasks under `dataflow/`. They do
not define behavior for Curation, Operation, Service, or other jobs.
[DataFlow YAML](../resources/jobs/dataflow.yml) owns wiring, parameters,
stage skips, integration gating, and lifecycle routing. Consult the
[DataFlow guide](../docs/guide/G201-dataflow-job-guide.md) for stage boundaries.

### `dataflow/task_00_main.py`

Keep run-level decisions, processing dates, paths, and shared task values here.
Use `flow_action=complete` only for successful early completion; raise errors
for failures. Keep ingestion and transformations downstream. Consult the
[calendar guide](../docs/guide/G301-calendar-guide.md) for date behavior.

### `dataflow/task_10_ingest.py`

Use documented DataBridge client preparation, submission, result handling, and
verification APIs. Preserve DataForge `[[ ... ]]` and DataBridge `{{ ... }}`
template ownership. Keep server orchestration in DataBridge. Consult the
[client guide](../docs/guide/G220-ingest-client-guide.md), the
[server contract](../docs/reference/databridge/docs/README.md), and the
[configuration instructions](../conf/oeds/config/AGENTS.md) for ingestion JSON.

### `dataflow/task_20_land_to_raw.py`

Complete file validation before copying so validation failures leave raw
storage unchanged. Copy durable landing files; never move or delete them.
Keep parsing and table loading downstream. Use the
[land-to-raw guide](../docs/guide/G230-land-to-raw-flow-guide.md) and
[landing practices](../docs/standards-and-practices/landing_zone_best_practices.md).

### `dataflow/task_30_raw_to_std.py`

Preserve read, transform, audit, validate, then load order. Fail before writing
on parsing, transformation, or business-validation errors. Registered datafile
and table definitions own source and target contracts. Preserve audit columns
and idempotent batch loading; keep curated publishing downstream. Consult the
[stage guide](../docs/guide/G240-raw-to-standardized-flow-guide.md),
[datafile guide](../docs/guide/G225-datafile-developer-guide.md), and
[validator guide](../docs/guide/G245-dataframe-validator-guide.md).

### `dataflow/task_40_std_to_curated.py`

Require explicit standardized sources, curated targets, output grain,
transformations, and write semantics. Do not infer business logic from the
placeholder or neighboring tasks. Keep raw parsing in `raw_to_std`; use
registered output contracts and the
[schema guide](../docs/guide/G211-schema-guide.md).

### `dataflow/task_50_integrate.py`

Preserve the structured `not_configured` result until sources, consumers,
formats, delivery targets, idempotency, and retry requirements are defined.
Keep transformations in `std_to_curated`. Preserve integration-only reruns
from existing curated data. Raise errors for failed required deliveries so
`on_failure` runs. Do not copy Curation's project-specific integration behavior.
Consult the server contract above before adding DataBridge delivery.

### `dataflow/task_90_on_complete.py`

Keep actions idempotent across normal completion, skipped stages, and graceful
early completion. Require explicit notification, audit, cleanup, or downstream
trigger requirements. For email, use `EmailManager` and configured registries
from the [email guide](../docs/guide/G303-email-developer-guide.md) and
[email example](../examples/email/send_email.py), not raw transport payloads.
Keep failure recovery and business transformations out of this task.

### `dataflow/task_91_on_failure.py`

Preserve the original processing failure. Limit actions to requested
notifications, incident/audit records, and cleanup safe after partial work.
Do not retry or reimplement processing here. Notification or cleanup errors
must not obscure the original failure. Use the documented email APIs above;
do not infer recipients, incident destinations, or cleanup scope.
