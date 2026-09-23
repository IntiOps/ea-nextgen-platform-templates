#!/usr/bin/env bash
set -euo pipefail
: "${TF_STATE_RESOURCE_GROUP:?}" "${TF_STATE_STORAGE_ACCOUNT:?}" "${TF_STATE_CONTAINER:?}" "${TF_VAR_instance:?}" "${TF_VAR_owner_id:?}"
terraform init -input=false -lockfile=readonly \
  -backend-config="use_oidc=true" \
  -backend-config="use_azuread_auth=true" \
  -backend-config="resource_group_name=${TF_STATE_RESOURCE_GROUP}" \
  -backend-config="storage_account_name=${TF_STATE_STORAGE_ACCOUNT}" \
  -backend-config="container_name=${TF_STATE_CONTAINER}" \
  -backend-config="key=ea-demo/${TF_VAR_owner_id}/${TF_VAR_instance}.tfstate"
