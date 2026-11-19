#!/bin/bash
# Purpose:
#   Azure DevOps pre-deploy hook that writes the selected Databricks bundle
#   target into cluster/env.sh before the cluster bootstrap assets are deployed.
# Usage:
#   script/pre/10_set_cluster_env.sh [dev|stg|prd]
# Notes:
#   The deployment pipeline passes the target environment as the first argument.
set -euo pipefail

# Read the target environment from the pipeline argument, defaulting to dev for local runs.
TARGET_ENV="${1:-dev}"

# Resolve the local cluster environment file updated by this hook.
LOCAL_CLUSTER_DIR="./cluster"
ENV_FILE="${LOCAL_CLUSTER_DIR}/env.sh"

# Replace only the TARGET_ENV export so the remaining cluster settings stay unchanged.
sed -i.bak 's|^[[:space:]]*export[[:space:]]\+TARGET_ENV=".*"$|export TARGET_ENV="'"${TARGET_ENV}"'"|' "${ENV_FILE}"

# Remove the backup file produced by sed -i.bak to keep the workspace clean.
rm -f "${ENV_FILE}.bak"

# Emit a concise pipeline log message after the environment file has been updated.
echo "Updated ${ENV_FILE}"
