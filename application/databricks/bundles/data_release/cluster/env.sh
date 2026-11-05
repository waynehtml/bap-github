#!/bin/bash

# Set env variable
export TARGET_ENV="dev"
echo "TARGET_ENV=$TARGET_ENV"

# Set wheelhouse variables
export CLUSTER_BASE_PATH="/Volumes/${TARGET_ENV}_banking_and_payments_cat/reference_db/vol_bap_config/habs/cluster"
echo "CLUSTER_BASE_PATH=$CLUSTER_BASE_PATH"

# Set cluster init script path
# Remove or commment out the following environment variable to diable init script deployment
export CLUSTER_INIT_PATH="${CLUSTER_BASE_PATH}/.init"
echo "CLUSTER_INIT_PATH=$CLUSTER_INIT_PATH"

# Set cluster wheelhouse path
# Remove or commment out the following environment variable to diable wheelhouse
export CLUSTER_WHEELHOUSE_PATH="${CLUSTER_BASE_PATH}/.wheelhouse"
echo "CLUSTER_WHEELHOUSE_PATH=$CLUSTER_WHEELHOUSE_PATH"
