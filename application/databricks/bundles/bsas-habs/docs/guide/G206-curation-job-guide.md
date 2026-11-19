# Curation Job Guide

This guide explains the optional `CURATION` Databricks workflow in the
DataForge template. The workflow combines curated-layer processing with an
optional integration stage under one job identity and run lifecycle. Use it
when these stages need a concurrency limit or trigger independent of
`DATAFLOW`.

The workflow is defined in
[resources/jobs/curation.yml](../../resources/jobs/curation.yml) and
implemented by notebooks under [jobs/curation](../../jobs/curation).

## Selection And Identity

`CURATION` is optional. Project initialization discovers it from the leading
metadata in `resources/jobs/curation.yml` and adds the resource include only
when the developer selects it.

The job resource declares two initialization values:

- `curation_job_name`, inferred as uppercase
  `<DOMAIN>-<DATASET>-CURATION` or supplied as a complete value that
  initialization uppercases.
- `curation_job_description`, inferred as `<dataset> curation job` or supplied
  as a complete value.

The job uses the shared run-as identity, permissions, alert recipients, and job
cluster. Queueing is disabled, and `max_concurrent_runs` is `1`, so an
overlapping trigger is not queued or run concurrently.

The template includes separate paused schedule examples for `dev`, `stg`, and
`prd` in the job YAML's `targets` section. Each example runs at 10 a.m.
Monday-Friday, including holidays, in `${var.timezone}` (default
`America/Toronto`, following daylight-saving changes). Edit the chosen target's
cron, timezone, or pause status independently. Set `pause_status: UNPAUSED`
in that target and deploy it only when scheduled execution is intended.

## Relationship To Dataflow

`CURATION` and the `DATAFLOW.std_to_curated` stage are independent options:

- Use `std_to_curated` when curated output is the final stage of the same
  ingestion and transformation run.
- Use `CURATION` when curated processing needs to run independently from
  ingestion and standardization.

Selecting `CURATION` does not disable, trigger, or depend on `DATAFLOW`. A
project should implement curated behavior in the workflow it intends to run.
When both entry points genuinely share domain logic, place that reusable logic
under `src/oeds/domain` and call it from each notebook rather than duplicating
the implementation.

## Parameters

| Parameter | Default | Purpose |
| --- | --- | --- |
| `rundate` | `""` | Optional business date. `common.py` defaults a blank value to today. |
| `debug` | `${var.debug}` | Controls shared debug logging. |
| `args` | `""` | Optional JSON object string. Supports the curation `mode` and project-specific inputs. |
| `job_run_dependency_check` | `"1"` | Runs the dependency check unless set to exactly `"0"`. |
| `job_run_integrate` | `"1"` | Runs integration unless set to exactly `"0"`. |

The reference `main` task parses `args` and requires a JSON object. Empty text
becomes `{}`. Tasks must not log the decoded object or use it for secrets.

The `curate` task resolves the optional `mode` key for project curation logic.
When omitted, `mode` defaults to `regular`. A supplied value must be a string;
the task strips surrounding whitespace, converts it to lowercase, and accepts
only `regular` or `full`:

```json
{"mode": "full"}
```

`regular` represents period-based curation for the selected run date, while
`full` represents recalculation of all historical data. The reference task
currently validates and logs the resolved mode but does not branch or perform
either type of project curation. Projects implement those behaviors when they
replace the placeholder logic.

## Workflow

```text
main
  -> optional dependency_check
  -> curate
  -> check_after_curate
       continue -> check_run_integrate
                     enabled  -> integrate -> on_complete
                     disabled -------------> on_complete
       complete ---------------------------> on_complete

main, dependency_check, curate, or integrate failure -> on_failure
```

The resource implements the optional branch with Databricks condition tasks:

1. `main` validates shared inputs and publishes a normalized `rundate` task
   value.
2. `check_after_main` continues only when `main` leaves `flow_action` as
   `continue`.
3. `check_run_dependency_check` runs `dependency_check` unless
   `job_run_dependency_check` is exactly `"0"`.
4. `check_after_dependency_check` continues only when the check leaves
   `flow_action` as `continue`.
5. `curate` runs after either a successful dependency check or the
   disabled-check branch.
6. `check_after_curate` continues only when curation leaves `flow_action` as
   `continue`. A `complete` value bypasses integration.
7. `check_run_integrate` runs `integrate` unless `job_run_integrate` is exactly
   `"0"`.
8. `integrate` runs after successful curation when enabled.
9. `on_complete` runs after successful integration, disabled integration, or a
   controlled early completion.
10. `on_failure` runs when `main`, `dependency_check`, `curate`, or `integrate`
    fails.

## Reference Tasks

### `main`

The main notebook loads [common.py](../../common.py), validates `rundate` and
`args`, logs the normalized date, and publishes it for later tasks:

```python
dbutils.jobs.taskValues.set(key="rundate", value=normalized_rundate)
```

Add run-level decisions here. Keep shared task values compact and avoid
publishing sensitive data.

### `dependency_check`

The reference notebook reads the shared date and resolves project-owned
operation-status dependencies sequentially. Its `dependencies` list is empty
by default so the generated workflow remains runnable. Populate it with exact
identity criteria or a time filter:

```python
dependencies = [
    {
        "dataset": "upstream_dataset",
        "layer": "standardization",
        "batch_id": rundate,
    },
]
```

Each item is passed to `OperationStatusManager.resolve_dependency`. The task
logs its `<dataset> in <layer>` identifier, criteria, and availability without
logging `job_context`. Every operation-status row represents a successful
operation. After resolving every item, the task raises one error containing
the missing-dependency count when no success record matches. Every dependency
requires `dataset` and `layer`. Use the upstream system's actual batch ID when
it differs from the curation run date.

Use `flow_action=complete` only when the absence of work is an expected,
successful outcome. Raise an exception when a required dependency is missing or
invalid so Databricks preserves the failure and runs `on_failure`.

### `curate`

The reference notebook reads and logs the date published by `main`. It also
parses and logs `args.mode` as `regular` or `full` for future use. Replace the
placeholder with business rules, joins, enrichment, aggregations, and curated
writes while keeping detailed diagnostics in logs.

The task records the successful operation before finishing naturally. The
reference placeholder therefore creates a curation marker. Replace the
placeholder with project curation logic and keep the marker after the output
commit:

```python
from oeds.domain.utils.operation import OperationStatusManager

OperationStatusManager().record_status(
    dataset=job_ctx["dataset"],
    layer="curation",
    batch_id=rundate,
    job_run_id=job_ctx.get("job_run_id"),
    job_name=job_ctx.get("job_name"),
    job_id=job_ctx.get("job_id"),
    job_trigger_type=job_ctx.get("job_trigger_type"),
    job_context=job_ctx,
)
```

A curation failure before marker persistence creates no marker. If the curated
output commits but marker persistence fails, log and propagate that failure so
the task cannot report success without its dependency marker.

### `integrate`

The reference notebook at `task_30_integrate.py` reads the normalized date
published by `main` and demonstrates three project integration paths:

1. Read the matching `tbl_sample` standardized batch through the schema
   registry and fail when it is empty.
2. Read the `amount` from the lowest-numbered standardized row, write it as
   `template.ts1#boc` for the run date, and register the change in the time-series
   transaction log. The AE time-series standard publishes registered changes to
   WebMart automatically. Aggregation remains the responsibility of the curation
   task. Register the sample series through the release workflow before running
   integration.
3. Select business columns, write one named CSV under
   `outbound_root/<rundate>` with the shared DataKit
   [`write_csv_file`](../reference/datakit/api/file_utils.md#write_csv_file)
   helper, and call internal DataBridge with `outbound.json`. The demo delivers the
   file to `outbound_root/delivered/<rundate>` and verifies its size.

Replace the sample table, aggregate, series name, output columns, and demo DataBridge
delivery handler with project-specific integration logic. The shared curation
dependency check and lifecycle handlers remain authoritative; do not duplicate
them in a separate job.

### Completion And Failure

`on_complete` is the extension point for success notifications, audit records,
and cleanup. It may run after successful integration, disabled integration, or
controlled early completion, so its behavior should be idempotent.

`on_failure` is the extension point for failure notification, incident records,
and cleanup that is safe after partial processing. Do not hide or replace the
original exception from the failed processing task.

## Flow Control

[common.py](../../common.py) initializes every notebook's `flow_action` task
value to `continue`. A task can stop the remaining processing path successfully:

```python
dbutils.jobs.taskValues.set(key="flow_action", value="complete")
dbutils.notebook.exit("Curation completed without downstream processing.")
```

Use this only for expected no-work outcomes. When `curate` sets
`flow_action=complete`, integration is skipped and `on_complete` runs.
Validation errors, unavailable required dependencies, curation or integration
errors, and write failures must raise an exception. A raised exception routes
to `on_failure`, without also running `on_complete`.

## Customization Checklist

- Populate the dependency list when upstream operation statuses are required.
- Replace the placeholder curation behavior and keep operation-status recording
  after the output commit succeeds.
- Replace the sample integration table, time series, CSV shape, and delivery
  handler with project behavior.
- Define and document any additional project-specific keys accepted through
  `args`.
- Keep sensitive inputs in approved secret or service configuration.
- Preserve the shared `rundate` task value when later tasks need one consistent
  processing date.
- Keep the completion and failure handlers safe to retry.
- Validate both values of `job_run_dependency_check` and `job_run_integrate`,
  plus every early-completion and failure route after changing the task graph.

## Related Guides

- [DataForge Template Project Guide](G001-dataforge-template-guide.md)
- [Init Project Guide](G101-init-project-guide.md)
- [Deployment Guide](G112-deployment-guide.md)
- [Dataflow Job Guide](G201-dataflow-job-guide.md)
- [Common Notebook Guide](G203-common-notebook-guide.md)
