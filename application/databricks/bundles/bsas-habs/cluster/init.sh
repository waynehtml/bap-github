#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
PIP_BIN="/databricks/python/bin/pip"
NEXUS_URL="https://fcp4lnexuap01.bocad.bank-banque-canada.ca/nexus/repository/pypi-all/simple"
NEXUS_HOST="fcp4lnexuap01.bocad.bank-banque-canada.ca"

if [ ! -f "${REQ_FILE}" ]; then
  echo "requirements.txt not found: ${REQ_FILE}" >&2
  exit 1
fi

if [ ! -x "${PIP_BIN}" ]; then
  echo "Databricks pip is missing or not executable: ${PIP_BIN}" >&2
  exit 1
fi

echo "Installing packages from Nexus"
for attempt in 1 2; do
  if "${PIP_BIN}" install \
    --index-url "${NEXUS_URL}" \
    --trusted-host "${NEXUS_HOST}" \
    --retries 2 \
    --timeout 60 \
    -r "${REQ_FILE}"; then
    echo "Installed packages from Nexus"
    exit 0
  fi

  echo "Nexus installation attempt ${attempt} failed" >&2
  if [ "${attempt}" -lt 2 ]; then
    sleep 3
  fi
done

echo "Package installation failed after 2 attempts" >&2
exit 1
