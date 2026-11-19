# Release Guide

This guide explains how to create release notebooks, deploy the Databricks Asset Bundle, and run release notebooks through the `SERVICE` job after deployment.

`SERVICE` is optional. Select it during project initialization before using this
release workflow; otherwise its resource is not included or deployed.

Use this guide for changes that must be applied after code is deployed, such as creating Unity Catalog tables or views, registering timeseries metadata, loading reference data, migrating data, or applying one-time data corrections.

## Release Flow

A typical release has four steps:

1. Create the mandatory release document for the release version.
2. Create one or more release notebooks under [releases](../../releases).
3. Deploy the project with `SERVICE` enabled through the Azure DevOps Databricks Asset Bundle pipeline.
4. Run each release notebook through the deployed `SERVICE` job in sequence.

Release notebooks should be committed with the code change that needs them. Do not run a release notebook until the code and bundle resources it depends on have been deployed to the target environment.

## Mandatory Release Document

Every release must include a Markdown file named:

```text
release-<version>-00.md
```

Use
[release-0.0.0-00.md](../../examples/release/release-0.0.0-00.md)
as the starting pattern. The `00` sequence places the document before the release
scripts for the same version.

At minimum, the document must contain release information, including the purpose
of the release and the release scripts or execution steps it includes. It may
also serve as an automation coordination script that runs the other release
scripts in the required order. When it coordinates automation, keep the
execution order explicit and ensure failures stop the release rather than
allowing partial success to appear complete.

The release document is mandatory even when automation coordination is not
needed.

## Release Notebooks

Create release notebooks in the project [releases](../../releases) folder. Use the samples under [examples/release](../../examples/release) as the starting pattern.

The template samples include:

- [release-0.0.0-11-create-tables.py](../../examples/release/release-0.0.0-11-create-tables.py)
- [release-0.0.0-12-create-views.py](../../examples/release/release-0.0.0-12-create-views.py)
- [release-0.0.0-13-apply-permissions.py](../../examples/release/release-0.0.0-13-apply-permissions.py)

Use this naming convention:

```text
release-<version>-<sequence>-<description>.py
```

Examples:

```text
release-1.0.0-11-create-tables.py
release-1.0.0-12-create-views.py
release-1.0.0-13-load-reference-data.py
release-1.0.0-14-register-timeseries.py
release-1.0.1-11-fix-customer-status.py
```

The version identifies the release package. The sequence number controls the order within that release. Leave gaps between sequence numbers when useful so another step can be inserted later. Keep the description short and action-oriented.

Create separate release notebooks for separate types of changes. For example:

- Table creation
- View creation
- Permission or grant changes
- Reference data loads
- Data corrections
- Backfill preparation
- Timeseries registration

Small, focused release notebooks are easier to review, rerun, and troubleshoot than one large release notebook that performs unrelated work.

## Release Notebook Pattern

Release notebooks should follow the sample pattern:

1. Define development widgets for local notebook runs.
2. Load [common.py](../../common.py) with `%run ../common`.
3. Read `job_ctx = get_job_context()`.
4. Parse release parameters from `job_ctx["args"]` with `parse_json()`.
5. Use existing managers and utilities from `src/oeds/domain`.
6. Raise exceptions for real failures.

The release notebook receives `args` as a JSON string and must validate that
the parsed value is an object. Keep the arguments explicit and stable.

```python
args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")
```

Example arguments for table creation:

```json
{"ref":"","replace":true}
```


## Deploy Code And Bundle Resources

Use Azure DevOps to run the Databricks Asset Bundle deployment pipeline before running release notebooks.

Use the deployment pipeline registered by the owning domain repository.
DataForge does not include a project-local deployment pipeline. In the shared
source repository, `pipelines/oeds-dbk-dab-deploy-v2.yaml` and
`pipelines/oeds-dbk-dab-deploy-v3.yaml` are wrappers intended to be copied into
a domain repository with its `pipelines/variables/` configuration. Confirm the
registered pipeline's YAML and parameters before creating a manual run.

The shared wrappers expose these parameters:

| Parameter | Meaning | Typical value |
| --- | --- | --- |
| `bundle_path` | Path to the copied project bundle folder. | `application/databricks/bundles/<project-folder-name>` |
| `target_wks` | Workspace selected from the domain repository's configuration. | `UC01` or `DMZ` |
| `target_env` | Databricks target environment. | `dev`, `stg`, or `prd` |
| `debug` | Enables Databricks CLI debug logging. | `false` unless troubleshooting deployment |

The domain repository's variable templates supply the service connection,
workspace URLs, and build agent settings. The v3 wrapper additionally exposes
`migrate_before_deploy`; enable it only when intentionally migrating an existing
Terraform deployment.

## Run Release Notebooks Through The Service Job

After deploying a project that includes `SERVICE`, run release notebooks through
that job, which is usually named `{domain}-{dataset}-Service`.

The `SERVICE` job is defined in [resources/jobs/service.yml](../../resources/jobs/service.yml). It has these job parameters:

| Parameter | Required | Purpose |
| --- | --- | --- |
| `rundate` | No | Optional business date for the run. |
| `debug` | No | Enables debug logging when set to true. |
| `task` | Yes | Release notebook path or named service task. |
| `args` | No | Optional JSON object string passed to the release notebook. |

The service entry point is [jobs/service/task_00_main.py](../../jobs/service/task_00_main.py). It resolves `task` in three ways:

- A full `/Workspace/...` path runs that notebook directly.
- A relative path runs a notebook below the deployed bundle root.
- A task name runs `jobs/service/tasks/<task>.py`.

For release notebooks, use the deployed notebook path. The most explicit option is the full workspace path after deployment. Use the exact workspace root configured by `workspace.root_path` in `databricks.yml`.

Example service job parameters:

```text
task: /Workspace/triton/.bundle/<bundle-name>/files/releases/release-1.0.0-11-create-tables.py
args: {"ref":"","replace":true}
```

You can also use a relative path when running through the deployed service job:

```text
task: releases/release-1.0.0-11-create-tables.py
args: {"ref":"","replace":true}
```

Relative paths are resolved under the deployed `bundle_root` passed to the service job.

## Release Execution Order

Run release notebooks in sequence number order for the target release version.

Example:

1. `release-1.0.0-11-create-tables.py`
2. `release-1.0.0-12-create-views.py`
3. `release-1.0.0-13-apply-permissions.py`
4. `release-1.0.0-14-load-reference-data.py`
5. `release-1.0.0-15-register-timeseries.py`

The permission sample uses `oeds.domain.utils.permission` and the existing
permission configuration. Copy it into `releases/` and include it in the release
document after creating all configured objects. Run with
`{"schema_ref":""}` to apply every configured entry, or supply one reference.
The sample uses the manager defaults: `default.json` with environment-first
resolution and `execute=True`. Views receive `SELECT` without grants
on their dependencies. See [direct object grants](G212-schema-permission-guide.md#direct-object-grants)
for prerequisites and targeted execution.

Run each notebook as a separate `SERVICE` job run unless there is a clear reason to combine steps. Separate runs make it easier to identify which release step failed and rerun only that step.


## Related Guides

- [DataForge Template Project Guide](G001-dataforge-template-guide.md): overview of the template project.
- [Init Project Guide](G101-init-project-guide.md): initialize a copied project bundle.
- [Deployment Guide](G112-deployment-guide.md): understand Databricks Asset Bundle deployment, Azure DevOps parameters, and pre/post deployment hooks.
- [Service Job Guide](G202-service-job-guide.md): use the service job for release notebooks and named service tasks.
- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand the dataflow processing workflow.
- [Schema Guide](G211-schema-guide.md): define tables and views used by release notebooks.
- [Permission Module Developer Guide](G212-schema-permission-guide.md): configure Unity Catalog grants and apply them through the Python API or release notebooks.
