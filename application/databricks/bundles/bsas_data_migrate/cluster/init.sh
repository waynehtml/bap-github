#!/bin/bash
set -euo pipefail

# Get the directory where this init script is located.
# requirements.txt and env.sh are expected to live beside this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
ENV_FILE="${SCRIPT_DIR}/env.sh"

# Use the Databricks cluster Python pip explicitly.
PIP_BIN="/databricks/python/bin/pip"

# Corporate Nexus PyPI proxy.
NEXUS_URL="https://fcp4lnexuap01.bocad.bank-banque-canada.ca/nexus/repository/pypi-all/simple"
NEXUS_HOST="fcp4lnexuap01.bocad.bank-banque-canada.ca"

retry() {
  local max_retries=2
  local attempt=1

  while [ "${attempt}" -le "${max_retries}" ]; do
    if "$@"; then
      return 0
    fi

    echo "Command failed on attempt ${attempt}/${max_retries}: $*"
    attempt=$((attempt + 1))

    if [ "${attempt}" -le "${max_retries}" ]; then
      sleep 3
    fi
  done

  return 1
}

get_requirements_checksum() {
  sha256sum "${REQ_FILE}" | awk '{print $1}'
}

write_requirements_checksum() {
  local checksum="$1"
  echo "${checksum}" > "${WHEELHOUSE_CHECKSUM_FILE}"
}

clean_wheelhouse() {
  if [ -z "${CLUSTER_WHEELHOUSE_PATH:-}" ]; then
    echo "CLUSTER_WHEELHOUSE_PATH is empty"
    return 1
  fi

  echo "Recreating wheelhouse: ${CLUSTER_WHEELHOUSE_PATH}"
  rm -rf "${CLUSTER_WHEELHOUSE_PATH}"
  mkdir -p "${CLUSTER_WHEELHOUSE_PATH}"
}

install_from_nexus() {
  echo "Installing from Nexus"
  retry "${PIP_BIN}" install \
    --index-url "${NEXUS_URL}" \
    --retries 2 \
    --timeout 60 \
    -r "${REQ_FILE}"
}

build_wheelhouse() {
  local req_checksum

  req_checksum="$(get_requirements_checksum)"

  echo "Building wheelhouse at ${CLUSTER_WHEELHOUSE_PATH}"
  clean_wheelhouse

  if ! retry "${PIP_BIN}" download \
    --dest "${CLUSTER_WHEELHOUSE_PATH}" \
    --only-binary=:all: \
    --index-url "${NEXUS_URL}" \
    --retries 2 \
    --timeout 60 \
    -r "${REQ_FILE}"; then
    return 1
  fi

  write_requirements_checksum "${req_checksum}"
  echo "Wheelhouse build completed"
}

install_from_wheelhouse() {
  echo "Installing from wheelhouse: ${CLUSTER_WHEELHOUSE_PATH}"
  retry "${PIP_BIN}" install \
    --no-index \
    --find-links "${CLUSTER_WHEELHOUSE_PATH}" \
    -r "${REQ_FILE}"
}

is_wheelhouse_stale() {
  local current_checksum
  local saved_checksum

  if [ ! -d "${CLUSTER_WHEELHOUSE_PATH}" ]; then
    echo "Wheelhouse folder does not exist"
    return 0
  fi

  if [ ! -f "${WHEELHOUSE_CHECKSUM_FILE}" ]; then
    echo "Wheelhouse checksum file does not exist"
    return 0
  fi

  current_checksum="$(get_requirements_checksum)"
  saved_checksum="$(tr -d '[:space:]' < "${WHEELHOUSE_CHECKSUM_FILE}")"

  if [ -z "${saved_checksum}" ]; then
    echo "Wheelhouse checksum file is empty"
    return 0
  fi

  if [ "${current_checksum}" != "${saved_checksum}" ]; then
    echo "requirements.txt has changed"
    return 0
  fi

  echo "requirements.txt has not changed"
  return 1
}

if [ ! -f "${REQ_FILE}" ]; then
  echo "requirements.txt not found: ${REQ_FILE}"
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "env.sh not found: ${ENV_FILE}"
  exit 1
fi

# Load environment variables from env.sh.
# shellcheck disable=SC1090
source "${ENV_FILE}"

# Trust the internal Nexus host.
"${PIP_BIN}" config set global.trusted-host "${NEXUS_HOST}"

# If wheelhouse path is not defined, go straight to Nexus.
if [ -z "${CLUSTER_WHEELHOUSE_PATH:-}" ]; then
  echo "CLUSTER_WHEELHOUSE_PATH is not defined, skipping wheelhouse"
  if install_from_nexus; then
    echo "Installed from Nexus"
    exit 0
  fi

  echo "Package installation failed"
  exit 1
fi

echo "CLUSTER_WHEELHOUSE_PATH=${CLUSTER_WHEELHOUSE_PATH}"

WHEELHOUSE_CHECKSUM_FILE="${CLUSTER_WHEELHOUSE_PATH}/.requirements.sha256"

# Rebuild wheelhouse if missing or requirements.txt changed.
if is_wheelhouse_stale; then
  if ! build_wheelhouse; then
    echo "Wheelhouse build failed, falling back to Nexus"
    if install_from_nexus; then
      echo "Installed from Nexus"
      exit 0
    fi

    echo "Package installation failed"
    exit 1
  fi
fi

# Try wheelhouse first.
if install_from_wheelhouse; then
  echo "Installed from wheelhouse"
  exit 0
fi

# Fallback to Nexus if wheelhouse install fails.
echo "Wheelhouse install failed, falling back to Nexus"
if install_from_nexus; then
  echo "Installed from Nexus"
  exit 0
fi

echo "Package installation failed"
exit 1