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

Use the `oeds-dbk-dab-deploy-v3.yaml` wrapper in the consuming project's
`pipelines/` folder. It extends
`pipelines/templates/oeds-dbk-dab-deploy-v3-template.yaml` from the `main` branch
of `lake-devops/lake-devops`. The wrapper owns variable-file selection and the
agent pool; the shared template owns authentication and Databricks CLI execution.

## Pipeline Parameters

Developers choose these values when manually running the wrapper:

| Parameter | Values | Meaning |
| --- | --- | --- |
| `bundle_path` | string | Repository-relative folder containing the active `databricks.yml`, such as `application/databricks/bundles/my_project`. The wrapper default is the parent `application/databricks/bundles/`; select the actual project folder. |
| `target_wks` | `UC01`, `DMZ` | Selects the environment's workspace host. Defaults to `UC01`. DataForge apps deploy to **UC01 only**. |
| `target_env` | `dev`, `stg`, `prd` | Selects the environment variable file and bundle target, including target overrides and permissions. Defaults to `dev`. |
| `debug` | `true`, `false` | Enables Databricks CLI debug logging. Defaults to `false`. |
| `migrate_before_deploy` | `true`, `false` | Migrates existing Terraform bundle state to the direct deployment engine before deployment. Defaults to `false`; enable only for that migration. |

Example manual run values:

```text
bundle_path: application/databricks/bundles/my_project
target_wks: UC01
target_env: dev
debug: false
migrate_before_deploy: false
```

Configure these project-owned files before registering or running the wrapper:

| Variable file | Settings |
| --- | --- |
| `pipelines/variables/common.yaml` | `agent_pool_name`, `agent_image`, `databricks_resource_id`, and `databricks_nexus_url`. The supplied Nexus URL uses `databricks_cli_version` from the same file. |
| `pipelines/variables/dev.yaml`, `stg.yaml`, or `prd.yaml` | The selected environment's `service_connection`, `databricks-UC01-host`, and `databricks-DMZ-host`. |

The wrapper loads `common.yaml` and exactly one environment file. It selects the
pool through `agent_pool_name` and the image through the `ImageOverride` demand
using `agent_image`. Service connections must exist and be authorized separately;
the wrapper does not derive them from a DevOps project name.

The wrapper passes `bundle_path`, `target_env`, `debug`,
`migrate_before_deploy`, `databricks_resource_id`, `databricks_nexus_url`,
`service_connection`, and `databricks_host` to the shared template.
`target_wks` selects the host in the wrapper; it is not a shared-template
parameter. Pool settings also remain in the wrapper.
`databricks_resource_id` is the Azure Databricks authentication resource used to
request an Entra token, not an individual Azure workspace resource ID.

## Deployment Flow

A normal deployment follows this sequence:

1. A developer starts a manual pipeline run with the project bundle path,
   environment, and workspace. Select `UC01` for DataForge apps.
2. Azure DevOps resolves the shared template and project variable files, selects
   the agent pool/image, and checks out the consuming repository with
   `checkout: self`. The shared template repository is not separately checked out.
3. The shared template selects Python 3.x, installs the Databricks CLI from
   Nexus, validates the workspace host, and configures optional debug output.
4. The selected Azure service connection requests an Entra access token for
   `databricks_resource_id`. Later commands receive the host and masked token
   through their environment and use the direct bundle deployment engine.
5. From `bundle_path`, the pipeline validates the bundle to discover
   `scripts.pre_deploy` and runs that hook if defined. A failure stops deployment.
6. The pipeline runs the explicit bundle validation step for `target_env`.
7. If `migrate_before_deploy` is enabled, it runs `bundle deployment migrate`.
   Migration failure stops deployment; successful migration is followed by
   deployment in the same checkout with the same target and settings.
8. `bundle deploy` creates or updates included resources and synchronizes source
   files. When App Setup is enabled, the app resource and source are deployed
   within this bundle. Otherwise, app resources remain omitted and their source
   remains excluded from synchronization.
9. After successful deployment, the pipeline validates the bundle to discover
   `scripts.post_deploy` and runs it if defined. Enabled app setup selects
   `start_app`, which runs the configured apps. Post-deploy failure fails the
   pipeline without undoing the completed bundle deployment.
10. When Job Setup is enabled, operators or release owners can separately run
    release notebooks through SERVICE for schema, data, permission, or one-time
    operational changes.

Job Setup is optional; app-only and general-only initialization are valid.
When Job Setup is enabled, initialization reads each job resource's leading
purpose and required metadata, includes every required job, and allows any number
of optional jobs, including none. SERVICE is required in that case. A job deploys
only when its file is explicitly included in `databricks.yml`.
DATAFLOW, CURATION, and OPERATION each include separate paused schedule examples
for `dev`, `stg`, and `prd` in their job YAML's `targets` section. Each example is
10 a.m. Monday-Friday, including holidays, in `${var.timezone}` (default
`America/Toronto`, following daylight-saving changes). Edit each target's cron,
timezone, and pause status independently; set `pause_status: UNPAUSED` and
deploy that target to enable its schedule. Excluding a job file also excludes
its target schedules. SERVICE has no schedule. OPERATION's initial notebook
returns a successful `not_configured` result until replaced.

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
validates the selected bundle and runs a start/restart for every configured
app in alphabetical resource-key order using `databricks bundle run`. It uses
resource keys, not deployed app names. No configured apps is a successful no-op.
Validation, JSON parsing, or a start command failure stops execution and fails
the post-deploy hook; earlier requests are not rolled back or retried.

The script waits for each CLI command to complete. The CLI waits for app
startup when needed and for the app deployment to complete, propagating startup
or deployment failures to the script. Success confirms completion of those CLI
operations; no separate application-level smoke test is performed. The script
uses inherited authentication and target configuration; use target settings or
inherited `BUNDLE_VAR_*`
overrides because outer `--var` arguments are not forwarded. The v3 pipeline
invokes this hook after successful deployment. A plain `bundle deploy` does not.
App inclusion and source synchronization must still be enabled explicitly.

## DataBench Configuration Deployment

The dev target override in `default.databricks.yml` selects
`deploy_databench_config` before bundle deployment.
It recursively copies all contents of
[`conf/oeds/config/databench/`](../../conf/oeds/config/databench/),
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
