#!/bin/bash
# Purpose:
#   TEMPORARY Azure DevOps pre-deploy hook. Binds the existing swift-file-upload
#   app into the bundle's Terraform state so dbk-dab-deploy stops trying to
#   create it. Runs as the DEV deployment service principal with the pipeline
#   CLI (0.266.1), before Validate bundle and Deploy bundle.
# Usage:
#   script/pre/10_bind_swift_app_dev.sh [dev|stg|prd]
# Notes:
#   DEV only; other targets exit 0 without changes. Fails the pipeline step if
#   bind or summary fails, or if the resolved IDs are not the expected ones.
#   Remove this file after one successful DEV deployment confirms both bindings.
set -euo pipefail

TARGET_ENV="${1:-}"
APP_KEY="swift-file-upload"
APP_NAME="swift-file-upload"
JOB_KEY="dvr_swift_pipeline"
EXPECTED_JOB_ID="114611886916255"

if [ "${TARGET_ENV}" != "dev" ]; then
  echo "10_bind_swift_app_dev: target '${TARGET_ENV}' is not dev; skipping."
  exit 0
fi

# Print "<job_id> <app_id>" from bundle summary JSON; empty values become '-'.
resolve_ids() {
  databricks bundle summary --target "${TARGET_ENV}" --output json \
    | python3 -c '
import json, sys
r = json.load(sys.stdin).get("resources", {})
job = r.get("jobs", {}).get(sys.argv[1], {}).get("id") or "-"
app = r.get("apps", {}).get(sys.argv[2], {}).get("id") or "-"
print(job, app)
' "${JOB_KEY}" "${APP_KEY}"
}

databricks -v
read -r JOB_ID APP_ID < <(resolve_ids)
echo "Before bind: ${JOB_KEY}=${JOB_ID}, ${APP_KEY}=${APP_ID}"

if [ "${JOB_ID}" != "${EXPECTED_JOB_ID}" ]; then
  echo "##vso[task.logissue type=error]${JOB_KEY} is bound to ${JOB_ID}, expected ${EXPECTED_JOB_ID}"
  exit 1
fi

if [ "${APP_ID}" = "${APP_NAME}" ]; then
  echo "${APP_KEY} already bound; skipping bind."
else
  echo "Binding ${APP_KEY} to existing app ${APP_NAME}..."
  databricks bundle deployment bind "${APP_KEY}" "${APP_NAME}" \
    --target "${TARGET_ENV}" --auto-approve
fi

databricks bundle summary --target "${TARGET_ENV}"
read -r JOB_ID APP_ID < <(resolve_ids)
echo "After bind: ${JOB_KEY}=${JOB_ID}, ${APP_KEY}=${APP_ID}"

if [ "${JOB_ID}" != "${EXPECTED_JOB_ID}" ] || [ "${APP_ID}" != "${APP_NAME}" ]; then
  echo "##vso[task.logissue type=error]Binding verification failed; stopping before deploy."
  exit 1
fi
echo "Binding verified."
