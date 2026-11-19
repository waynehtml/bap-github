# Dataflow Job Guide

This guide explains the `DATAFLOW` Databricks workflow in the template project and how developers should customize it for a real dataset pipeline.

DATAFLOW is an optional workload choice during project initialization. Select it
when the generated project uses the staged dataset pipeline described here.

The workflow is defined in [resources/jobs/dataflow.yml](../../resources/jobs/dataflow.yml) and implemented by notebooks under [jobs/dataflow](../../jobs/dataflow). It is designed as a staged pipeline with explicit gates, shared runtime context, task values, skip controls, success handling, and failure handling.

## Scheduling

The template includes separate paused schedule examples for `dev`, `stg`, and
`prd` in the job YAML's `targets` section. Each example runs at 10 a.m.
Monday-Friday, including holidays, in `${var.timezone}` (default
`America/Toronto`, following daylight-saving changes). Edit the chosen target's
cron, timezone, or pause status independently. Set `pause_status: UNPAUSED`
in that target and deploy it only when scheduled execution is intended.

## Workflow Mental Model

The `DATAFLOW` job is a Databricks Asset Bundle job for dataset processing. It separates orchestration from task implementation:

- [resources/jobs/dataflow.yml](../../resources/jobs/dataflow.yml) defines the job graph, dependencies, condition tasks, and job parameters.
- [resources/jobs/common.yml](../../resources/jobs/common.yml) defines the shared cluster settings and base notebook parameters.
- [common.py](../../common.py) builds the shared `job_ctx` dictionary used by all notebooks.
- [jobs/dataflow](../../jobs/dataflow) contains task notebooks where project-specific workflow behavior is implemented.
- `dbutils.jobs.taskValues` passes small control and path values between tasks.

The default flow is:

1. Prepare run context in `main`.
2. Optionally ingest files into the landing zone.
3. Optionally copy landed files to the raw zone.
4. Optionally transform raw data to standardized data.
5. Optionally transform standardized data to curated outputs.
6. Optionally integrate curated outputs with downstream consumers.
7. Run completion handling.
8. Run failure handling if a processing stage fails.

## Job-Level Design

The `DATAFLOW` job includes:

- Job identity from variables declared alongside the job in
  `resources/jobs/dataflow.yml`: `${var.dataflow_job_name}` and
  `${var.dataflow_job_description}`. Initialization can infer the uppercase
  `<DOMAIN>-<DATASET>-DATAFLOW` name and the
  `<dataset> dataflow job` description, or accept either complete value from
  the developer. Inferred and provided names are uppercased; description
  casing is preserved.
- Tags for `team`, `domain`, `dataset`, `type`, and `criticality`.
- Permissions from the target's shared `${var.job_permissions}` profile.
- `run_as` service principal from `${var.job_runas_account}`.
- Queueing enabled so overlapping triggers are queued instead of rejected.
- A shared job cluster defined by `common_job_cluster`.
- Job-level parameters for run date, debug mode, optional arguments, and stage toggles.

The run parameters are:

| Parameter | Required | Purpose |
| --- | --- | --- |
| `rundate` | No | Optional business date; defaults to today. |
| `debug` | No | Enables debug logging when set to true. |
| `args` | No | Optional JSON object string for curation mode and project-specific run parameters. |

The stage toggle parameters are:

- `job_run_ingest`
- `job_run_land_to_raw`
- `job_run_raw_to_std`
- `job_run_std_to_curated`
- `job_run_integrate`

Each toggle defaults to `"1"`. Set a toggle to `"0"` at run time to skip that stage.

Databricks pushes job-level parameters to every notebook task. [common.py](../../common.py) keeps `args` as unchanged text in `job_ctx`; a task parses and validates it only when needed:

```python
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")
```

An empty value parses as `{}`. Keep operational controls such as `rundate`,
`debug`, and stage toggles as explicit job parameters, and use `args` only for
the optional curation mode and project-specific extensions. Do not put secrets
in `args`, and do not log the decoded object or the complete `job_ctx`.

The `std_to_curated` task resolves the optional `args.mode` value. A missing
mode defaults to `regular`; supplied strings are stripped, converted to
lowercase, and must be `regular` or `full`. `regular` represents curation for
the current batch, while `full` represents recalculation of all historical
data. The reference task validates and logs the mode for future project logic
but does not yet branch or recalculate data.

All notebooks receive `common_base_parameters`, which include project metadata, date settings, environment, bundle paths, storage roots, secret scopes, Databricks workspace references, DataBridge job IDs, email mappings, and Datamart endpoints.

## Stage Use Cases

### `main`

Use the `main` stage for run-level decisions and shared values that every later stage should use.

- Stop the workflow gracefully for holidays, no-work days, already-processed batches, or missing source windows.
- Calculate shared processing values such as `file_date`, `land_dir`, `raw_dir`, batch ID, source system, or processing window.
- Publish small shared task values that downstream stages must use consistently.
- Add lightweight preflight checks before ingestion starts.

The reference `main` notebook publishes normalized `rundate` and `file_date`
with `dbutils.jobs.taskValues.set`. Curated processing uses `rundate`, while
file-oriented stages consume the same `file_date` processing batch.

### `ingest`

Use the `ingest` stage to bring source files into the landing zone through DataBridge.

- Replace the sample ingestion config with the project source requests.
- Use internal or external DataBridge settings as needed.
- Resolve project-specific values such as source path, file date, landing path, and batch parameters before calling DataBridge.
- Keep server-known or sensitive values in DataBridge server-side templates.
- Add landed-file verification when the source flow needs anti-virus delay handling, file-size checks, mandatory file checks, or checksum checks.

### `land_to_raw`

Use the `land_to_raw` stage to promote landed files into the raw storage layout used by the project.

- Copy files into raw; do not move or delete durable landing files. Cleanup is owned by the storage retention policy.
- Use source-specific file patterns.
- Add validation or quarantine logic before raw promotion.
- Adjust the raw folder layout by date, source, version, entity, or batch.
- Publish raw output paths when later stages need multiple raw locations.

### `raw_to_std`

Use the `raw_to_std` stage to convert raw source data into standardized technical tables.

- Read raw files or raw tables.
- Parse and validate source data.
- Normalize columns and data types.
- Write standardized tables.
- Record an operation-status row only after the standardized write commits.
- Track row counts, rejected rows, quality results, or standardized output tables for later stages.
- Follow the [Raw To Standardized Flow Guide](G240-raw-to-standardized-flow-guide.md) for registry-driven reads, transformations, validation, audit fields, and Delta batch loading.

The operation-status row is the durable success marker for the standardized
batch. If its write fails after the Delta load commits, the task fails and
reports that the business output succeeded but status persistence failed.

### `std_to_curated`

Use the `std_to_curated` stage to produce curated business outputs from standardized data.

The reference task parses and logs `args.mode`, reads the normalized `rundate`
published by `main`, and records a successful curation operation after the
placeholder processing finishes. Keep the status record after project curated
outputs commit.

- Apply business rules, joins, enrichment, and aggregations.
- Write curated tables, views, or publishable outputs.
- Update timeseries outputs when the project requires them.
- Publish summary values for notifications, audit records, or downstream systems.

Keep this stage when curated output belongs to the same pipeline run. Select
the independent [Curation Job](G206-curation-job-guide.md) instead when curated
processing needs its own job identity, trigger, concurrency, or run lifecycle.
Selecting `CURATION` does not disable or trigger this stage.

### `integrate`

Use the `integrate` stage to disseminate curated outputs to downstream systems
as part of the same DataFlow run.

The reference task reads the normalized `rundate` published by `main`, logs
that project integration is not configured, and returns a compact successful
`not_configured` result. Replace the placeholder only after the integration
source, consumer, output contract, delivery target, and retry behavior are
explicit.

- Publish curated results to downstream databases, APIs, files, or messaging
  systems.
- Deliver outbound files through DataBridge when the project contract requires
  it.
- Keep aggregations and curated business transformations in
  `std_to_curated`.
- Raise an error when a required integration fails so `on_failure` runs.

The stage has its own `job_run_integrate` toggle. Skipping
`std_to_curated` does not automatically skip integration, which permits an
integration-only rerun from existing curated data. A controlled completion
from `std_to_curated` bypasses integration and routes to `on_complete`.

### `on_complete`

Use the `on_complete` stage for successful completion and controlled early completion.

- Send success notifications.
- Write audit records or run metrics.
- Trigger downstream systems.
- Clean temporary files when needed.
- Keep the logic idempotent because this task may run after a stage skip or graceful early exit.

### `on_failure`

Use the `on_failure` stage for failed processing runs.

- Send failure notifications.
- Write audit or incident records.
- Add cleanup logic that is safe after partial processing.
- Preserve the original task failure for troubleshooting.
- Include useful run metadata such as environment, dataset, job run ID, run date, and known output paths.

## Passing Values Between Tasks

The workflow uses three value-passing mechanisms.

Bundle variables are resolved into job settings and notebook parameters by Databricks Asset Bundles. They are declared in `databricks.yml` and [resources/jobs/common.yml](../../resources/jobs/common.yml), then referenced from [resources/jobs/dataflow.yml](../../resources/jobs/dataflow.yml) with `${var.*}` syntax.

Notebook base parameters are passed through `common_base_parameters`. [common.py](../../common.py) reads those parameters and returns a normalized `job_ctx` dictionary. Most task notebooks should use `job_ctx` for environment, paths, secret scopes, workspace settings, and project metadata.

Task values are used for small values created by one task and consumed by later tasks. The template uses task values for:

- `flow_action`: controls whether the next processing stage should continue.
- `land_dir`: landing directory for the run.
- `raw_dir`: raw directory for the run.
- `file_date`: intended shared processing/file date.

Set task values with:

```python
dbutils.jobs.taskValues.set(key="raw_dir", value=raw_dir)
```

Read task values with:

```python
raw_dir = dbutils.jobs.taskValues.get(
    taskKey="main",
    key="raw_dir",
    debugValue=raw_dir_default,
)
```

Use task values for compact strings, numbers, and flags. Put large diagnostics in logs or storage instead of task values.

## Controlling Workflow Execution

Use workflow control in two different ways:

- Use `flow_action=complete` when the workflow should stop early and still finish successfully.
- Raise an exception when the workflow should fail.

`flow_action` is for graceful, successful early completion. Typical examples are holidays, no eligible source window, no files expected for the run, or an already-processed batch.

[common.py](../../common.py) sets `flow_action` to `continue` by default when a notebook starts. A task can stop downstream processing by setting:

```python
dbutils.jobs.taskValues.set(key="flow_action", value="complete")
dbutils.notebook.exit("Workflow completed without downstream processing.")
```

The matching condition task checks:

```yaml
left: "{{tasks.main.values.flow_action}}"
op: EQUAL_TO
right: "continue"
```

If the condition is false, the workflow skips the downstream stage path and routes to `on_complete`. The job is expected to finish successfully.

Do not use `flow_action=complete` for real errors. If the task cannot safely continue because required data is missing, validation failed, DataBridge failed, or output writes failed, raise an exception from the task notebook. Databricks marks the task as failed, and the `on_failure` task can run through the `run_if: AT_LEAST_ONE_FAILED` dependency rule.

Stage toggles control whether a stage is run for a specific job run:

- `job_run_ingest = "0"` skips ingestion.
- `job_run_land_to_raw = "0"` skips land-to-raw.
- `job_run_raw_to_std = "0"` skips raw-to-standardized.
- `job_run_std_to_curated = "0"` skips standardized-to-curated.
- `job_run_integrate = "0"` skips integration.

To skip a stage, open the Databricks job run parameters and set the matching `job_run_*` parameter to `"0"` before starting the run. Leave the value as `"1"` to run the stage.

Examples:

- Reprocess from existing landed files: set `job_run_ingest` to `"0"`.
- Reprocess from existing raw files: set `job_run_ingest` and `job_run_land_to_raw` to `"0"`.
- Stop after raw promotion: set `job_run_raw_to_std`,
  `job_run_std_to_curated`, and `job_run_integrate` to `"0"`.
- Run only curated processing from existing standardized data: set
  `job_run_ingest`, `job_run_land_to_raw`, `job_run_raw_to_std`, and
  `job_run_integrate` to `"0"`.
- Run only integration from existing curated data: set `job_run_ingest`,
  `job_run_land_to_raw`, `job_run_raw_to_std`, and
  `job_run_std_to_curated` to `"0"`; leave `job_run_integrate` as `"1"`.

Use `flow_action=complete` for expected business outcomes where the workflow should finish successfully, such as holidays or no eligible work. Use stage toggles for operator-controlled run-time skips.

## Failure Behavior

The template defines task-specific exception types in [src/oeds/domain/exceptions.py](../../src/oeds/domain/exceptions.py), including:

- `MainTaskError`
- `IngestTaskError`
- `LandToRawTaskError`
- `RawToStdTaskError`
- `StdToCuratedTaskError`
- `OnCompleteTaskError`
- `OnFailureTaskError`

Raise these when a task cannot safely continue. Keep `on_failure` focused on notification, audit, and cleanup logic that should happen after the original task has failed.

## Validation Checklist

Before deploying a customized workflow, check:

- Every notebook path in [resources/jobs/dataflow.yml](../../resources/jobs/dataflow.yml) exists.
- Every processing stage has the intended condition and dependency wiring.
- Every `${var.*}` reference used by the job is declared in `databricks.yml`.
- Every base parameter read by [common.py](../../common.py) is passed by `common_base_parameters` or has an intentional fallback.
- Every task value read from another task is set by that task or has an acceptable `debugValue` for local development only.
- `flow_action` is used only for graceful completion, not for failures.
- Stage toggles skip only the intended stage and still allow valid downstream paths.
- `on_complete` and `on_failure` dependencies include any new stages.
- Task-specific exceptions are raised for real failures.
- Logs include enough context to investigate the job run without exposing secrets.

## Related Guides

- [DataForge Template Project Guide](G001-dataforge-template-guide.md): overview of the template project.
- [Init Project Guide](G101-init-project-guide.md): initialize bundle configuration for a copied project.
- [Curation Job Guide](G206-curation-job-guide.md): run curated-layer processing
  independently from `DATAFLOW`.
- [Service Job Guide](G202-service-job-guide.md): use the service job for release notebooks and named service tasks.
- [Land To Raw Flow Guide](G230-land-to-raw-flow-guide.md): validate and copy landing batches into raw without deleting landing files.
- [Raw To Standardized Flow Guide](G240-raw-to-standardized-flow-guide.md): convert raw batches into validated standardized Delta tables.
- [DataFrame Validator Guide](G245-dataframe-validator-guide.md): define business validation rules for standardized records.
- [Landing Zone Best Practices](../standards-and-practices/landing_zone_best_practices.md): preserve landing data for reload, audit, and recovery.
- [Schema Guide](G211-schema-guide.md): define Unity Catalog tables and views used by workflow tasks.
- [Calendar Guide](G301-calendar-guide.md): initialize the calendar from reference holidays and calculate run dates.
