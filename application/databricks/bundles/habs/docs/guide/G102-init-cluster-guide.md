# Cluster Init Guide

This guide explains how the template bundle deploys Databricks cluster init files, how the optional Nexus wheelhouse cache is populated, and how the cache is maintained at runtime.

## Key Files

- `cluster/env.sh`: Defines target-specific volume paths. The pre-deploy scripts update `TARGET_ENV`; developers enable `CLUSTER_INIT_PATH` for volume init scripts and `CLUSTER_WHEELHOUSE_PATH` for caching.
- `cluster/init.sh`: Runs on Databricks cluster startup. It sources `env.sh`, installs packages from Nexus or the wheelhouse cache, and refreshes the cache when it is stale.
- `cluster/requirements.txt`: Package list installed by `init.sh`.
- `script/pre/10_set_cluster_env.sh`: Azure DevOps pre-deploy hook that writes the selected bundle target into `cluster/env.sh`.
- `script/pre/20_deploy_init_scripts.sh`: Azure DevOps pre-deploy hook that deploys the `cluster` files to the configured Unity Catalog volume.
- `resources/common.yml`: Defines the shared job cluster and attaches `${var.CLUSTER_INIT_PATH}/init.sh` as either a workspace or volume init script.
- `tools/remove_wheelhouse.py`: Runtime maintenance notebook that removes the wheelhouse cache folder.

## During Development

The template defaults to the init script deployed with the bundle workspace files:

```yaml
CLUSTER_INIT_PATH:
  default: "${var.bundle_root}/cluster"
```

The default job cluster therefore uses a workspace init script:

```yaml
init_scripts:
  - workspace:
      destination: ${var.CLUSTER_INIT_PATH}/init.sh
```

Leave `CLUSTER_INIT_PATH` commented in `cluster/env.sh` for workspace mode. The bundle deploys `cluster/init.sh`, `cluster/env.sh`, and `cluster/requirements.txt` together, so no separate init-file copy is needed.

To deploy the cluster files to a Unity Catalog volume instead, provide a `CLUSTER_BASE_PATH` under `/Volumes/`, enable `CLUSTER_INIT_PATH`, and change the job cluster source from `workspace` to `volumes`:

```bash
export CLUSTER_INIT_PATH="${CLUSTER_BASE_PATH}/.init"
echo "CLUSTER_INIT_PATH=$CLUSTER_INIT_PATH"
```

```yaml
init_scripts:
  - volumes:
      destination: ${var.CLUSTER_INIT_PATH}/init.sh
```

`CLUSTER_INIT_PATH` is always the directory containing the cluster files. The `/init.sh` filename belongs only in the job cluster destination.

If the Nexus package cache is required, provide a volume `CLUSTER_BASE_PATH` and enable `CLUSTER_WHEELHOUSE_PATH` independently of the init script location:

```bash
export CLUSTER_WHEELHOUSE_PATH="${CLUSTER_BASE_PATH}/.wheelhouse"
echo "CLUSTER_WHEELHOUSE_PATH=$CLUSTER_WHEELHOUSE_PATH"
```

Use a Unity Catalog volume base path, for example:

```text
/Volumes/${TARGET_ENV}_financial_markets_cat/reference_db/vol_triton_config/<dataset>/cluster
```

Leave `CLUSTER_WHEELHOUSE_PATH` commented when dependencies should be installed directly from Nexus on each cluster startup. Workspace-file init scripts are not supported on standard access mode; select volume mode for those clusters.

## During Deployment

The Azure DevOps pipeline works against a local checkout of the source code.

1. The pipeline downloads the source code and runs the pre-deploy hooks from the bundle root.
2. The pipeline runs `script/pre/10_set_cluster_env.sh <target>`. This updates the `TARGET_ENV` export in `cluster/env.sh` so target-specific volume paths point to the selected environment.
3. The pipeline runs `script/pre/20_deploy_init_scripts.sh <target>`. This script sources `cluster/env.sh` first, then reads `CLUSTER_INIT_PATH`.
4. In workspace mode, `CLUSTER_INIT_PATH` is not exported by `cluster/env.sh`, so the script skips the optional volume copy. The bundle deploys the `cluster` directory to workspace files and retains the default bundle variable.
5. In volume mode, the script requires `CLUSTER_INIT_PATH` to start with `/Volumes/`, creates the remote folder, and copies each top-level file from `./cluster`.
6. After the copy, the script publishes `CLUSTER_INIT_PATH` to Azure DevOps as `BUNDLE_CLUSTER_INIT_PATH`.
7. The shared pipeline exports `BUNDLE_` variables into the Databricks bundle deployment. `BUNDLE_CLUSTER_INIT_PATH` overrides the bundle variable `CLUSTER_INIT_PATH`.
8. The deployed job cluster uses the `volumes` source selected during `/init-cluster`:

```yaml
init_scripts:
  - volumes:
      destination: ${var.CLUSTER_INIT_PATH}/init.sh
```

In both modes, the bundle variable `CLUSTER_INIT_PATH` is the directory, and Databricks runs `init.sh` from that directory when the job cluster starts.

## During Cluster Init

When the Databricks job cluster starts, Databricks runs the deployed `init.sh`.

The script resolves paths relative to itself:

- `requirements.txt` must exist beside `init.sh`.
- `env.sh` must exist beside `init.sh`.

The script then sources `env.sh`, which exports values such as `TARGET_ENV`, `CLUSTER_BASE_PATH`, and optionally `CLUSTER_WHEELHOUSE_PATH`.

Package installation follows this flow:

1. Configure Databricks cluster Python pip to trust the internal Nexus host.
2. If `CLUSTER_WHEELHOUSE_PATH` is not set, install `cluster/requirements.txt` directly from Nexus.
3. If `CLUSTER_WHEELHOUSE_PATH` is set, use `${CLUSTER_WHEELHOUSE_PATH}/.requirements.sha256` as the wheelhouse checksum file.
4. Treat the wheelhouse as stale when the wheelhouse folder is missing, the checksum file is missing, the checksum file is empty, or the checksum does not match the current `requirements.txt`.
5. When stale, recreate the wheelhouse folder, download binary packages from Nexus into it, and write the current requirements checksum.
6. Install packages from the wheelhouse with `--no-index --find-links`.
7. If the wheelhouse build or install fails, fall back to installing directly from Nexus.
8. If both wheelhouse and Nexus installation fail, exit with an error so the cluster startup failure is visible.

The current implementation uses checksum-based staleness, not a time-based expiry window. To force repopulation, remove the wheelhouse folder or change `cluster/requirements.txt` so the checksum changes.

## During Runtime

`CLUSTER_WHEELHOUSE_PATH` is the runtime contract for wheelhouse maintenance. The maintenance notebook `tools/remove_wheelhouse.py` reads it from the environment:

```python
cluster_wheelhouse_path = os.environ.get("CLUSTER_WHEELHOUSE_PATH")
```

To remove the cache, run the service job with:

```text
task: tools/remove_wheelhouse
mode: sys
```

The notebook deletes the folder recursively with `dbutils.fs.rm(cluster_wheelhouse_path, True)`. The next cluster startup will see the wheelhouse folder as missing and repopulate it from Nexus.

If dependencies were already installed before the cache was removed, restart or recreate the cluster to run `init.sh` again and reload packages from the refreshed wheelhouse.

## Common Scenarios

To use the default workspace init script without wheelhouse caching:

1. Leave `CLUSTER_INIT_PATH` commented in `cluster/env.sh`.
2. Leave `CLUSTER_WHEELHOUSE_PATH` commented.
3. Keep `workspace` as the init script source in `resources/common.yml`.
4. Deploy the bundle. The cluster will run the workspace `init.sh` and install packages directly from Nexus.

To use the workspace init script with Nexus wheelhouse caching:

1. Leave `CLUSTER_INIT_PATH` commented in `cluster/env.sh`.
2. Provide `CLUSTER_BASE_PATH` and enable `CLUSTER_WHEELHOUSE_PATH`.
3. Deploy the bundle. The first cluster startup will populate the wheelhouse; later starts reuse it until `requirements.txt` changes or the cache is removed.

To deploy the cluster files to a volume:

1. Provide a `CLUSTER_BASE_PATH` under `/Volumes/`.
2. Enable `CLUSTER_INIT_PATH` in `cluster/env.sh`.
3. Change the init script source in `resources/common.yml` to `volumes`.
4. Enable or disable `CLUSTER_WHEELHOUSE_PATH` independently.
5. Deploy the bundle. The pre-deploy hook copies the cluster files and overrides the bundle init directory.

To refresh the wheelhouse cache:

1. Run `tools/remove_wheelhouse.py`, or update `cluster/requirements.txt`.
2. Restart or recreate the cluster so `init.sh` runs again.

## Troubleshooting

- If a workspace init script is not found, confirm the job uses `workspace` and `CLUSTER_INIT_PATH` resolves to the deployed bundle `cluster` directory.
- If a volume init script is not copied, confirm `CLUSTER_INIT_PATH` is exported in `cluster/env.sh` and starts with `/Volumes/`.
- If the bundle points to the wrong init location, confirm the job source matches the selected location and check the pipeline log for `BUNDLE_CLUSTER_INIT_PATH` in volume mode.
- If the wheelhouse is not used, confirm `CLUSTER_WHEELHOUSE_PATH` is exported in the deployed `env.sh`.
- If package installation fails, check the cluster init logs for the Nexus install and wheelhouse fallback messages.
- If `tools/remove_wheelhouse.py` fails with `CLUSTER_WHEELHOUSE_PATH is not defined`, confirm the runtime environment exposes the same wheelhouse path that `init.sh` uses.
