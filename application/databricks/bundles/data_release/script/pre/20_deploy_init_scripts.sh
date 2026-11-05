#!/bin/bash
# Purpose:
#   Azure DevOps pre-deploy hook that publishes Databricks cluster bootstrap
#   files from ./cluster to a target-specific Unity Catalog volume folder.
# Usage:
#   script/pre/20_deploy_init_scripts.sh [dev|stg|prd]
# Notes:
#   This script reads CLUSTER_INIT_PATH from cluster/env.sh, which is prepared
#   by 10_set_cluster_env.sh earlier in the deployment pipeline.
set -euo pipefail

# Read the target environment from the pipeline argument, defaulting to dev for local runs.
TARGET_ENV="${1:-dev}"

# Locate the local cluster folder and environment file used to drive deployment paths.
LOCAL_CLUSTER_DIR="./cluster"
ENV_SCRIPT="${LOCAL_CLUSTER_DIR}/env.sh"

# Stop quietly when the bundle does not include cluster environment settings.
if [ ! -f "${ENV_SCRIPT}" ]; then
  echo "env.sh not found at ${ENV_SCRIPT}, nothing to do."
  exit 0
fi

# Load target-specific cluster variables such as CLUSTER_INIT_PATH.
source "${ENV_SCRIPT}"

# Skip deployment when CLUSTER_INIT_PATH is unset because init scripts are disabled.
if [ -z "${CLUSTER_INIT_PATH:-}" ]; then
  echo "CLUSTER_INIT_PATH is not defined, nothing to copy."
  exit 0
fi

if [[ "${CLUSTER_INIT_PATH}" != /Volumes/* ]]; then
  echo "CLUSTER_INIT_PATH must be a Unity Catalog volume path under /Volumes/: ${CLUSTER_INIT_PATH}" >&2
  exit 1
fi

# Ensure the remote volume folder exists before copying cluster bootstrap files.
echo "Create cluster folder"
databricks fs mkdir "dbfs:${CLUSTER_INIT_PATH}" --target "${TARGET_ENV}"

# Copy each top-level file from ./cluster into the target-specific init folder.
echo "Copy cluster files to remote folder"
find "${LOCAL_CLUSTER_DIR}" -maxdepth 1 -type f | while IFS= read -r file; do
  name="$(basename "${file}")"
  echo "Copying ${file} -> ${CLUSTER_INIT_PATH}/${name}"
  databricks fs cp "${file}" \
    "dbfs:${CLUSTER_INIT_PATH}/${name}" \
    --overwrite \
    --target "${TARGET_ENV}"
done

# Publish the path using Databricks' native bundle-variable environment name.
echo "##vso[task.setvariable variable=BUNDLE_VAR_CLUSTER_INIT_PATH]$CLUSTER_INIT_PATH"

# Mark the pre-deploy hook as complete in the pipeline log.
echo "Done"
