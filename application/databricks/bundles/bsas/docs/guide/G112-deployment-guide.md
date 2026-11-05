# Deployment Guide

This guide explains how deployment works for projects copied from the Databricks template bundle. It is written for developers who need to understand what is deployed, how the Azure DevOps pipeline passes deployment settings to Databricks, and how to extend deployment with pre-deploy and post-deploy scripts.

## Deployment Model

This is a Databricks-first project. Databricks resources are defined and deployed with Databricks Asset Bundles.

In a copied project, the active deployment file is:

```text
databricks.yml
```

The template folder does not keep an active `databricks.yml` by default. Instead, a new project creates it from:

- [default.databricks.yml](../../default.databricks.yml): full commented bundle skeleton.
- adjacent domain mapping comments in the default and enabled resource YAML.
- project-specific values collected during initialization.

Use [Init Project Guide](G101-init-project-guide.md) before deployment if the copied project does not yet have `databricks.yml`.

## Azure DevOps Pipeline

Configure the project deployment pipeline to invoke the shared
`oeds-dbk-dab-deploy-v3-template.yaml` template with the bundle path and target.
The shared template owns authentication and Databricks CLI execution.

## Pipeline Parameters

Developers choose these values when manually running the pipeline:

| Parameter | Values | Meaning |
| --- | --- | --- |
| `bundle_path` | string | Path to the copied project bundle folder. Use `application/databricks/bundles/<project-folder-name>`. |
| `devops_project` | `triton`, `paycan`, `currency`, `banking`, `oeds` | Azure DevOps project whose service connection should be used. |
| `target_env` | `dev`, `stg`, `prd` | Databricks bundle target and environment. This selects workspace URL, project-specific service connection, target overrides, and permissions. |
| `agent_name` | configured agent names | Specific build agent that should run deployment. Keep the default unless an agent must be selected. |
| `debug` | `true`, `false` | Enables Databricks CLI debug logging. Use `false` for normal deployments. |

Example manual run values:

```text
bundle_path: application/databricks/bundles/my_project
devops_project: triton
target_env: dev
agent_name: fcp9ldopsam01
debug: false
```

`bundle_path` must point to the folder that contains the active `databricks.yml`.

The pipeline combines `devops_project` and `target_env` to select the service
connection:

| DevOps project | Dev | Stg | Prd |
| --- | --- | --- | --- |
| `triton` | `lake-dscn-bocqa01` | `lake-dscn-stgbocad` | `lake-dscn-prdbocad` |
| `paycan` | `lake-dscn-bocqa01` | `lake-dscn-stgbocad` | `lake-dscn-prdbocad` |
| `currency` | `lake-dscn-bocqa01` | `lake-dscn-stgbocad01` | `lake-dscn-prdbocad01` |
| `banking` | `lake-dscn-bocqa01` | `lake-dscn-stgbocad01` | `lake-dscn-prdbocad01` |
| `oeds` | `lake-dscn-bocqa01` | `lake-dscn-bocad01` | `lake-dscn-bocad01` |

## Deployment Flow

A normal deployment follows this sequence:

1. A developer starts a manual Azure DevOps pipeline run.
2. Azure DevOps resolves `devops_project` and `target_env` to the Databricks host and service connection.
3. The pipeline checks out the project repository and the shared `lake-devops` repository.
4. The shared pipeline authenticates to Azure and Databricks using the selected service connection and `azure_resource_id`.
5. The pipeline changes into `bundle_path`, where `databricks.yml` and the bundle resources live.
6. The v3 shared template explicitly runs the optional `scripts.pre_deploy`
   bundle script when it is defined.
7. The shared deployment template validates and deploys the Databricks Asset Bundle for `target_env`.
8. Databricks creates or updates the included jobs, their permissions, and
   synced job files. App source and resource templates are excluded from this
   bundle and deploy separately.
9. The v3 shared template explicitly runs the optional `scripts.post_deploy`
   bundle script when it is defined.
10. The required `SERVICE` job lets operators or release owners run release
    notebooks through it for schema, data, permission, or one-time operational
    changes.

Project initialization reads each job resource's leading purpose and required
metadata, automatically deploys every required job, and allows any number of
optional jobs, including none. A job deploys only when its file is explicitly
included in `databricks.yml`. SERVICE is required; selecting no optional jobs
still deploys SERVICE. DATAFLOW,
CURATION, and OPERATION each include separate paused schedule examples for
`dev`, `stg`, and `prd` in their job YAML's `targets` section. Each example is
10 a.m. Monday-Friday, including holidays, in `${var.timezone}` (default
`America/Toronto`, following daylight-saving changes). Edit each target's cron,
timezone, and pause status independently; set `pause_status: UNPAUSED` and
deploy that target to enable its schedule. Excluding a job file also excludes
its target schedules. SERVICE has no schedule. OPERATION's initial notebook
returns a successful `not_configured` result until replaced.

The exact Databricks CLI commands live in the shared `lake-devops` template. From this project, the important contract is that the local pipeline passes `target_env`, `dbk_host`, `bundle_path`, `service_connection`, `azure_resource_id`, `pool_name`, `agent_name`, and `debug`.

## Optional Inline Bundle Scripts

[resources/script.yml](../../resources/script.yml) defines the
`pre_deploy` and `post_deploy` hooks and `deploy_databench_config`. App scripts
live under top-level `scripts` in [resources/apps/main.yml](../../resources/apps/main.yml). Selection variables and target overrides are
centralized in [default.databricks.yml](../../default.databricks.yml).
The default bundle template
includes `resources/script.yml`, and project initialization preserves that
include. Including a script definition does not select it for execution.
The v3 pipeline calls `pre_deploy` before deployment and `post_deploy` only after
successful deployment. Running `databricks bundle deploy` alone does not invoke
these hooks.

Structured `script_rules` comments beside each selection variable define target
restrictions (`targets`) and setup dependencies (`requires: job` or `app`).
Initialization filters the merged selections after both setup decisions, preserving
order and repetitions without adding scripts. DataBench publishing is restricted
to dev; app repair and startup require App Setup. Change these rules in YAML,
without maintaining a matching script-name list in the skill. These are
initialization rules, not deployment-time enforcement of later manual edits.

Both `pre_deploy_scripts` and `post_deploy_scripts` are comma-separated strings
with empty-string defaults. Target overrides in `default.databricks.yml` select
`restore_app_secret_access` before deployment in dev, staging, and production.
Dev runs `deploy_databench_config` first. All three targets select `start_app`
after successful deployment. When App Setup is declined, initialization removes
`restore_app_secret_access` and `start_app` from all root and target selections,
preserving unrelated scripts and order. The app YAML and its scripts are included
only when app setup is enabled. Each hook receives its resolved selection through
`env` and runs the names in their listed order. Whitespace around names is
trimmed, and empty entries are skipped. Duplicate names run again in their
listed positions. Neither hook name may appear in a list. Script existence is
not checked in advance: the Databricks CLI reports unknown names when invoked.
A command failure stops the hook and fails the pipeline step. Use script names
only; `bundle run` can also execute other runnable bundle resources. There is
no automatic retry or rollback.

Add shared project scripts under `scripts:` in `resources/script.yml`. If a
separate file is needed, explicitly add its include. Keep script names unique
across included files:

```yaml
scripts:
  prepare_files:
    env:
      DEPLOY_TARGET: ${bundle.target}
    content: |
      set -euo pipefail
      echo "Preparing files for $DEPLOY_TARGET"
```

Select names in execution order in the Deployment scripts section of
`default.databricks.yml`, or override them in its existing target variables.
In initialized projects, edit the active `databricks.yml` instead. Keep selections
centralized; feature script files should only define scripts. Target overrides
replace the complete selection rather than appending names, for example:

```yaml
targets:
  dev:
    variables:
      pre_deploy_scripts: "deploy_databench_config, restore_app_secret_access, prepare_files"
      post_deploy_scripts: "start_app"
```

Use `""` to disable a phase for a target. Define custom script environment mappings with `env` so
Databricks resolves bundle substitutions before execution.

Invoke a hook explicitly outside the pipeline:

```bash
databricks bundle run pre_deploy --target dev
databricks bundle deploy --target dev
# Run only if deployment succeeded:
databricks bundle run post_deploy --target dev
```

Scripts run on the Linux deployment agent from the bundle root, using Python 3
and Databricks CLI 1.8.0+ for native script environment mappings. Child commands
inherit authentication and use the same target. Use target configuration,
`BUNDLE_VAR_` environment variables, or the bundle variable-overrides file for
variable overrides; the hooks do not forward outer command-line `--var` options.
The bundle must validate before pre-deploy can start. Each named script runs in
a separate process; shell exports do not persist between scripts.

Keep scripts idempotent, propagate failures, and avoid logging credentials or
sensitive payloads. For multi-command shell scripts, use `set -euo pipefail` to
stop on errors. Use post-deploy for work that requires deployed resources. Use
the required SERVICE job and its release notebooks for schema changes and
operational work rather than adding those operations to every deployment.

## App Startup After Deployment

`start_app` in [resources/apps/main.yml](../../resources/apps/main.yml)
validates the selected bundle and submits a start/restart for every configured
app in alphabetical resource-key order using `databricks bundle run`. It uses
resource keys, not deployed app names. No configured apps is a successful no-op.
Validation, JSON parsing, or a start command failure stops execution and fails
the post-deploy hook; earlier requests are not rolled back or retried.

Success means all CLI start/restart commands succeeded, not that the apps became
healthy. The script does not poll app status. It uses inherited authentication
and target configuration; use target settings or inherited `BUNDLE_VAR_*`
overrides because outer `--var` arguments are not forwarded. The v3 pipeline
invokes this hook after successful deployment. A plain `bundle deploy` does not.
App inclusion and source synchronization must still be enabled explicitly.

## DataBench Configuration Deployment

The dev target override in `default.databricks.yml` selects
`deploy_databench_config` before bundle deployment.
It recursively copies all contents of
[`src/oeds/domain/config/databench/`](../../src/oeds/domain/config/databench/),
including the placeholder README, directly into `${var.databench_root}/config`.
For example, `suite/settings.json` becomes
`${var.databench_root}/config/suite/settings.json`, without an extra `databench`
directory. The CLI destination uses the `dbfs:/Volumes/...` form.

Matching files are overwritten and destination-only files are retained. The
script uses the deployment identity and requires an existing destination Volume
with write access; it does not create the catalog, schema, or Volume. If the
source directory is absent, the script logs a skip message and succeeds without
calling Databricks. There is no destination check before copying. Any copy
failure, including permission or connectivity errors, retains the CLI diagnostics
and emits an Azure DevOps warning. The script succeeds so deployment continues.
A failed copy may leave partially updated destination files; there is no retry
or rollback.

Staging and production do not select this script by default. Target overrides
replace the complete comma-separated selection, so retain both
`deploy_databench_config` and `restore_app_secret_access` when adding other dev
preparation scripts. To disable only the DataBench copy for dev, select
`pre_deploy_scripts: "restore_app_secret_access"`. An empty string disables the
entire pre-deploy phase, including app repair.

## Compute Selection

Project initialization finishes configuration by asking for one compute choice
from the default YAML's Compute settings comments. It applies the choice to all
enabled jobs, including SERVICE, before validation and cleanup. The selected
choice is recorded as a comment in generated `databricks.yml`; this comment does
not switch compute during deployment. Later changes must update the actual
cluster or environment references in each enabled job.

## Local Cluster Bootstrap

The local classic configuration references
`${var.compute_classic_local_init_path}`, whose default is
`${var.bundle_root}/cluster/init.sh`. Bundle synchronization deploys the script
and adjacent requirements file. The script installs dependencies directly from
Nexus when the cluster starts. It needs no inline deployment script or separate
Volume copy. See the [Local Cluster Initialization](G101-init-project-guide.md#local-cluster-initialization).

DataBoot manages the separate central classic and serverless configurations.
Deploying a DataForge project does not publish or refresh those central assets.

## Related Guides

- [Init Project Guide](G101-init-project-guide.md): create project-specific `databricks.yml`.
- [Local Cluster Initialization](G101-init-project-guide.md#local-cluster-initialization): install local classic dependencies directly from Nexus.
- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand the deployed `DATAFLOW` job.
- [Curation Job Guide](G206-curation-job-guide.md): configure the optional,
  independently runnable `CURATION` job and its integration stage.
- [Service Job Guide](G202-service-job-guide.md): use the required `SERVICE` job.
- [Operation Job Guide](G204-operation-job-guide.md): configure the deployed
  fixed `OPERATION` job.
- [Release Guide](G111-release-guide.md): run release notebooks after bundle deployment.
