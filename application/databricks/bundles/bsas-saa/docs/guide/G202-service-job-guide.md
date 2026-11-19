# Service Job Guide

This guide explains the template `SERVICE` job, how it is defined in the Databricks Asset Bundle, and how developers should use it for release notebooks and named service tasks.

SERVICE is required and automatically included during project initialization.
It provides release and maintenance task dispatch even when no optional
processing workflows are selected.

The service job is defined in [resources/jobs/service.yml](../../resources/jobs/service.yml), and its entry notebook is [jobs/service/task_00_main.py](../../jobs/service/task_00_main.py).

## Naming Convention

The service job name comes from variables declared alongside the job in
[resources/jobs/service.yml](../../resources/jobs/service.yml):

Both values use the standard placeholder schema. Their `infer` modes produce
the uppercase `<DOMAIN>-<DATASET>-SERVICE` name and the
`<dataset> service job` description; their `input` modes accept complete
developer-provided values. Inferred and provided names are uppercased while
description casing is preserved.

For example, if:

```yaml
project:
  domain: FMD
  tag: triton
  catalog: financial_markets
  dataset: CORRA
```

the service job is named:

```text
FMD-CORRA-SERVICE
```

The inferred structure helps operators distinguish this job from DATAFLOW and
OPERATION, but it is not enforced when the developer selects `input`. The
uppercase requirement applies to both inferred and provided names.

## What The Service Job Is For

Use the `SERVICE` job for operational work that should run inside the deployed bundle context but is not part of the regular `DATAFLOW` pipeline.

Typical use cases:

- Run release notebooks after deployment.
- Create or refresh Unity Catalog tables and views.
- Load reference or migration data.
- Register timeseries metadata.
- Run one-time data corrections.
- Execute predefined maintenance tasks.
- Expose controlled operations for a Databricks App or another caller.

Do not put recurring dataset pipeline stages in the service job. Those belong in
the `DATAFLOW` job. Use `OPERATION` when independently managed work needs a stable
job definition instead of task or path dispatch through `SERVICE`.

## Job Definition

The `SERVICE` job uses the same shared bundle patterns as `DATAFLOW`:

- Job name and description from bundle variables.
- Tags for `team`, `domain`, and `dataset`, plus the fixed `service`
  type and `low` criticality tags.
- Permissions from the target's shared `${var.job_permissions}` profile.
- `run_as` service principal from `${var.job_runas_account}`.
- Failure email notifications from `${var.job_alert_emails}`.
- The classic cluster or serverless environment selected in the final compute
  setup step of project initialization.
- Shared notebook base parameters from `common_base_parameters`.

The service job has queueing disabled and `max_concurrent_runs: 1`. This keeps operational tasks serialized so two release or maintenance operations do not accidentally run at the same time.

## Parameters

The `SERVICE` job exposes these run parameters:

| Parameter | Required | Purpose |
| --- | --- | --- |
| `rundate` | No | Optional business date string. [common.py](../../common.py) keeps it as text and defaults it to today using `python_date_format`. |
| `debug` | No | Enables debug logging and diagnostics when set to true. |
| `task` | Yes | Notebook path or named service task to run. |
| `args` | No | Optional JSON object string passed to the target notebook as its `args` widget. |

`task` must be provided. When supplied, `args` must parse as a JSON object. An omitted or empty value is treated as `{}`.

## How `task` Is Resolved

[jobs/service/task_00_main.py](../../jobs/service/task_00_main.py) resolves `task` in three ways.

### Full Workspace Path

Use a full `/Workspace/...` path to run a deployed notebook directly.

Example:

```text
task: /Workspace/oedataservices/.bundle/<bundle-name>/files/releases/release-1.0.0-11-create-tables.py
args: {"ref":"","replace":true}
```

Use the exact workspace path from the deployed bundle. The deployment root is controlled by `workspace.root_path` in `databricks.yml`.

### Relative Bundle Path

Use a relative path to run a notebook under the deployed bundle root.

Example:

```text
task: releases/release-1.0.0-11-create-tables.py
args: {"ref":"","replace":true}
```

Relative paths are resolved under `bundle_root`, which is passed through `common_base_parameters`.

### Load Time-Series Observations Tool

Use the packaged `tools/load_timeseries_observations.py` notebook to load one
bounded, headered CSV file into a configured time-series table:

```text
task: tools/load_timeseries_observations
args: {"file_path":"/Volumes/catalog/schema/volume/observations.csv","tbl_ref":"tbl_ts"}
```

The required `tbl_ref` is resolved through the schema registry. The optional
`time_series_name_col`, `date_col`, and `observation_col` arguments default to
columns with those respective names, except that the value column defaults to
`observation`. `date_format` is a Python `datetime.strptime` format and defaults
to `%Y-%m-%d`.

The observation column accepts numeric values or the case-insensitive labels
`ND`, `NA`, and `NC`. Labels are normalized to uppercase and stored as the
missing-value label for a null numeric observation. Blank dates and observations,
unsupported labels, invalid dates, missing configured columns, and empty files
fail the tool before the time-series write begins. All rows are collected as one
bounded batch and produce one metadata audit key.

### Named Service Task

Use a simple task name to run a predefined notebook under [jobs/service/tasks](../../jobs/service/tasks).

Example:

```text
task: test
args: {}
```

The service entry point maps this to:

```text
jobs/service/tasks/test.py
```

Task names may contain letters, numbers, underscores, and hyphens. They cannot contain spaces or arbitrary path characters.

## How Job Context Is Passed

The service entry notebook reads `task` and `args` from `job_ctx`. It parses
`args` with the shared `parse_json()` helper and validates that the result is a
JSON object. It passes the complete job context, including direct integration
values and existing secret-key fields, directly to the target notebook:

```python
result = dbutils.notebook.run(task_path, 0, job_ctx)
```

The target notebook reads forwarded Azure and Databricks integration values
directly when it rebuilds the context. Datamart endpoints still use the
forwarded `datamart_endpoints_key` and `oeds_secrete_scope` for a fresh lookup.
See [Direct Integration Values](G203-common-notebook-guide.md#direct-integration-values)
and [OEDS Integration Secrets](G203-common-notebook-guide.md#oeds-integration-secrets)
for configuration and required scope permissions.

Target notebooks load `common.py` to rebuild `job_ctx` from the forwarded
bindings. `task`, `args`, `rundate`, `debug`, `email_mappings`,
`datamart_endpoints`, and the DataBridge job IDs remain strings. Consumers parse a
value only where they require a date, Boolean, JSON object, or integer.

The context contains resolved integration values. Do not log or echo the
context or forwarded mapping.

Example target notebook pattern:

```python
dbutils.widgets.text("args", "{}")
%run ../../../common

job_ctx = get_job_context()
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")
```

## Adding A New Service Task

To add a named service task:

1. Create a notebook under [jobs/service/tasks](../../jobs/service/tasks), for example `refresh_cache.py`.
2. Keep the task name simple, for example `refresh_cache`.
3. Parse `job_ctx["args"]` with `parse_json()` when the task accepts arguments.
4. Raise exceptions for failures so the service job fails visibly.
5. Document the task name and expected `args`.

After deployment, run it with:

```text
task: refresh_cache
args: {"scope":"all"}
```

Use named service tasks for approved operational actions that should have a stable name. Use notebook paths for one-off release notebooks.

## Completion And Failure Behavior

When the target notebook completes, the service entry notebook sets `flow_action` to `complete` and exits with the target notebook result.

If the target notebook or task fails, the service entry notebook raises an exception. Databricks marks the service job run as failed.

Use `flow_action=complete` only for successful service completion. Raise an exception for real errors.

## Related Guides

- [Release Guide](G111-release-guide.md): create release notebooks and run them through the service job.
- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand the dataflow pipeline job.
- [Operation Job Guide](G204-operation-job-guide.md): use a dedicated fixed
  operation instead of service dispatch.
- [DataForge Template Project Guide](G001-dataforge-template-guide.md): overview of the template project.
