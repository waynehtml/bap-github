# Operation Job Guide

This guide explains the optional fixed `OPERATION` job available to generated
DataForge projects. Select it during project initialization when project-owned
work needs an independently managed Databricks job rather than a stage in
`DATAFLOW` or dispatch through `SERVICE`.

## Layout

The operation job keeps its resource and notebook implementation under matching
`operation` names:

```text
resources/jobs/operation.yml
jobs/operation/task_00_main.py
```

Project initialization adds `resources/jobs/operation.yml` to the generated
bundle only when the developer selects OPERATION. Unselected job files remain
in the project as templates but are not deployed.

## Job Identity

The OPERATION identity variables are declared in `resources/jobs/operation.yml`.
When OPERATION is enabled, they use the same required identity-placeholder
contract as DATAFLOW and SERVICE. Their `infer` modes produce the uppercase
`<DOMAIN>-<DATASET>-OPERATION` name and the
`<dataset> operation job` description. Their `input` modes accept a confirmed
complete name or description without enforcing the inferred name structure.
Inferred and provided names are uppercased while description casing is
preserved. Changing the display name does not change the stable `OPERATION`
resource key.

The job tags are:

- `team`, `domain`, and `dataset` from the complex project variable.
- `type` fixed to `operation`.
- `criticality` fixed to `low`.

`type` and `criticality` are job resource metadata. They are not included in
the shared notebook `job_ctx`.

## Runtime Contract

`OPERATION` has one notebook task and uses the shared run-as identity, job
cluster, base parameters, and failure notifications. Queueing is disabled and
`max_concurrent_runs` is one.

The job exposes these parameters:

| Parameter | Required | Purpose |
| --- | --- | --- |
| `rundate` | No | Optional business date; defaults through `common.py`. |
| `debug` | No | Controls shared logging verbosity. |
| `args` | No | JSON object string for operation-specific inputs. |

The template includes separate paused schedule examples for `dev`, `stg`, and
`prd` in the job YAML's `targets` section. Each example runs at 10 a.m.
Monday-Friday, including holidays, in `${var.timezone}` (default
`America/Toronto`, following daylight-saving changes). Edit the chosen target's
cron, timezone, or pause status independently. Set `pause_status: UNPAUSED`
in that target and deploy it only when scheduled execution is intended.
Enable the schedule only after the operation behavior and run policy are approved.

## Placeholder Behavior

The template notebook loads `common.py`, parses `args`, and requires the parsed
value to be a JSON object. Until project logic replaces the placeholder, it
logs that no operation is configured and exits successfully with a compact
result containing:

- `status: not_configured`
- the resolved dataset and job name
- a short explanatory message

This successful no-op supports initial deployment validation. Do not treat it
as evidence that a business operation ran.

## Implementing An Operation

Replace the placeholder section in `jobs/operation/task_00_main.py` with the
project operation while preserving these boundaries:

1. Load `common.py` before using project configuration or shared services.
2. Parse and validate `args` without logging sensitive payload contents.
3. Keep reusable business logic under `src/oeds/domain` and project-owned
   configuration under `conf/oeds/config`.
4. Raise an exception for real failures so Databricks marks the run failed and
   sends configured alerts.
5. Keep notebook exit payloads compact and put diagnostics in logs.

Use `DATAFLOW` for the regular multi-stage dataset flow. Use `SERVICE` for named or
path-based release and maintenance dispatch. Do not turn `OPERATION` into a
second dispatcher.

## Permissions And Deployment

When enabled, OPERATION applies the same complex `${var.job_permissions}` value
as every other enabled job. The variable is declared in
`resources/jobs/common.yml`; its adjacent domain/target mapping provides one
complete permission list per target during Job Setup. Do not add
`resources.jobs` permission overrides.

Review the shared permission profile, run-as access, cluster policy, and
notification recipients before production deployment.

Adding this job to an existing generated project creates a new Databricks job
resource with the stable bundle key `OPERATION`. Changing only its display name
later updates the same resource.

## Validation

Before deploying a generated project:

- Confirm `resources/jobs/operation.yml` is explicitly included when OPERATION
  is intended to deploy.
- Resolve the name and description through their documented `infer` or `input`
  modes, and confirm both values are useful to operators.
- Confirm the display name is unique in the target workspace.
- Confirm the notebook path resolves under `jobs/operation`.
- Validate `dev`, `stg`, and `prd` bundle targets.
- Run the placeholder once in development and confirm the `not_configured`
  result before adding business logic.
- After implementation, test valid, empty, and invalid `args` and verify that
  real failures propagate to the job run.

## Related Guides

- [DataForge Template Project Guide](G001-dataforge-template-guide.md): see how
  OPERATION fits beside DATAFLOW and SERVICE.
- [Common Notebook Guide](G203-common-notebook-guide.md): use shared context and
  runtime services.
- [Service Job Guide](G202-service-job-guide.md): dispatch release, utility, and
  named service tasks.
- [Deployment Guide](G112-deployment-guide.md): validate and deploy the bundle.
