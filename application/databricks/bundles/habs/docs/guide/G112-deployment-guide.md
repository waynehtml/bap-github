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
- a domain target-override file such as [FMD.databricks.yml](../../FMD.databricks.yml), [CUR.databricks.yml](../../CUR.databricks.yml), [BAP.databricks.yml](../../BAP.databricks.yml), or [SUP.databricks.yml](../../SUP.databricks.yml).
- project-specific values collected during initialization.

Use [Init Project Guide](G101-init-project-guide.md) before deployment if the copied project does not yet have `databricks.yml`.

## Azure DevOps Pipeline

Use the project-level [.azuredevops/pipelines/deploy.yaml](../../.azuredevops/pipelines/deploy.yaml)
to deploy the project through Azure DevOps.

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
6. If the hook-enabled shared deployment template is used, scripts in `script/pre` run before bundle deployment.
7. The shared deployment template validates and deploys the Databricks Asset Bundle for `target_env`.
8. Databricks creates or updates the included jobs, their permissions, and
   synced job files. App source and resource templates are excluded from this
   bundle and deploy separately.
9. If the hook-enabled shared deployment template is used, scripts in `script/post` run after bundle deployment.
10. When `SERVICE` is selected, operators or release owners can run release
    notebooks through it for schema, data, permission, or one-time operational
    changes.

Project initialization reads each job resource's leading purpose and required
metadata, automatically deploys every required job, and allows any number of
optional jobs, including none. A job deploys only when its file is explicitly
included in `databricks.yml`. DATAFLOW, CURATION, SERVICE, and OPERATION are
currently all optional, so a valid deployment may contain no jobs. When
selected, OPERATION has no schedule until the generated project
explicitly adds one, and its initial notebook returns a successful
`not_configured` result until replaced.

The exact Databricks CLI commands live in the shared `lake-devops` template. From this project, the important contract is that the local pipeline passes `target_env`, `dbk_host`, `bundle_path`, `service_connection`, `azure_resource_id`, `pool_name`, `agent_name`, and `debug`.

## Pre-Deploy And Post-Deploy Hooks

The template supports custom deployment scripts under:

```text
script/pre
script/post
```

Pre-deploy scripts run before the Databricks bundle deployment. Use them for work that must exist before `databricks bundle deploy`, such as publishing cluster init files or preparing deployment-time variables.

Post-deploy scripts run after the Databricks bundle deployment. Use them for work that depends on deployed Databricks resources, such as starting Databricks Apps after app resources are created.

## Hook Script Conventions

Follow these conventions for custom scripts:

- Name scripts with numeric prefixes such as `10_`, `20_`, and `30_` so execution order is clear.
- Keep scripts idempotent. A rerun should update or skip existing resources cleanly.
- Accept the target environment as the first argument: `TARGET_ENV="${1:-dev}"`.
- Assume scripts run from the bundle root and use paths relative to that root.
- Use `set -euo pipefail` so real failures stop the deployment.
- Do not print secrets, tokens, service principal secrets, or sensitive payloads.
- Log the major action and target path so pipeline failures are easy to diagnose.
- Prefer deployment preparation here. When `SERVICE` is enabled, use release notebooks through it for schema changes, data migrations, and one-time data operations.

The folder in this template is named `script`, not `scripts`.

## Existing Pre-Deploy Scripts

The template includes two pre-deploy scripts for cluster init support.

### `script/pre/10_set_cluster_env.sh`

This script updates the selected deployment target in [cluster/env.sh](../../cluster/env.sh):

```bash
script/pre/10_set_cluster_env.sh dev
```

It replaces only the `TARGET_ENV` export:

```bash
export TARGET_ENV="dev"
```

This keeps target-specific cluster paths aligned with the environment selected in the Azure DevOps run.

### `script/pre/20_deploy_init_scripts.sh`

This script optionally deploys top-level files from [cluster](../../cluster) to a configured Unity Catalog volume. The default workspace init script is deployed with the bundle and does not use this copy step.

The script:

1. sources `cluster/env.sh`;
2. reads `CLUSTER_INIT_PATH`;
3. exits successfully when `CLUSTER_INIT_PATH` is not defined, which is the default workspace mode;
4. rejects a configured path that is not under `/Volumes/`;
5. creates the remote folder with `databricks fs mkdir "dbfs:${CLUSTER_INIT_PATH}" --target "${TARGET_ENV}"`;
6. copies each top-level file from `cluster` to `dbfs:${CLUSTER_INIT_PATH}`;
7. sets the Azure DevOps variable `BUNDLE_CLUSTER_INIT_PATH`.

By default, [resources/common.yml](../../resources/common.yml) attaches the init script from the bundle workspace files:

```yaml
init_scripts:
  - workspace:
      destination: ${var.CLUSTER_INIT_PATH}/init.sh
```

When `/init-cluster` selects volume mode, it enables the volume path in `cluster/env.sh` and changes the job cluster source:

```yaml
init_scripts:
  - volumes:
      destination: ${var.CLUSTER_INIT_PATH}/init.sh
```

The shared pipeline then maps `BUNDLE_CLUSTER_INIT_PATH` into the bundle variable `CLUSTER_INIT_PATH`. Enable the variable only for volume mode. See [Init Cluster Guide](G102-init-cluster-guide.md) for the full workspace, volume, and wheelhouse behavior.

## Existing Post-Deploy Script

The template includes [script/post/10_start_app.sh.sample](../../script/post/10_start_app.sh.sample) as a sample for a separate app-specific deployment pipeline.

Rename or copy it to a `.sh` script when the project deploys Databricks Apps and the app should be started after deployment.

The sample script:

1. runs `databricks bundle summary --target "$TARGET_ENV" --output json`;
2. reads app resource names from `.resources.apps` with `jq`;
3. exits successfully when no app resources exist;
4. starts each app with `databricks bundle run --target "$TARGET_ENV" "$app"`.

Do not enable this hook in the standard job bundle. Use it only from a separate
app deployment configuration that deploys the app resource and source code.

## Adding A Custom Hook

To add a pre-deploy step:

1. Create a shell script under `script/pre`.
2. Give it the next numeric prefix, for example `30_prepare_workspace_folder.sh`.
3. Read `TARGET_ENV` from the first argument.
4. Make the script safe to rerun.
5. Validate it locally from the bundle root when possible:

```bash
bash script/pre/30_prepare_workspace_folder.sh dev
```

To add a post-deploy step:

1. Create a shell script under `script/post`.
2. Give it the next numeric prefix, for example `20_start_app.sh`.
3. Use Databricks CLI commands with `--target "$TARGET_ENV"`.
4. Skip cleanly when the target resource is not enabled in the bundle.
5. Keep long-running operational work out of the hook unless it is part of deployment itself.


## Related Guides

- [Init Project Guide](G101-init-project-guide.md): create project-specific `databricks.yml`.
- [Init Cluster Guide](G102-init-cluster-guide.md): configure cluster init scripts and wheelhouse caching.
- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand the deployed `DATAFLOW` job.
- [Curation Job Guide](G206-curation-job-guide.md): configure the optional,
  independently runnable `CURATION` job and its integration stage.
- [Service Job Guide](G202-service-job-guide.md): select and use the optional `SERVICE` job.
- [Operation Job Guide](G204-operation-job-guide.md): configure the deployed
  fixed `OPERATION` job.
- [Release Guide](G111-release-guide.md): run release notebooks after bundle deployment.
