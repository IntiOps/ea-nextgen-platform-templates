#!/usr/bin/env bash
# Initialise Terraform against the environment's state backend (see operations/state_backend.py).
# The backend block is generated, never committed; credentials come from the runner identity.
set -euo pipefail
: "${TF_VAR_instance:?}" "${TF_VAR_owner_id:?}"
identity=$(python3 "$(dirname "$0")/state_backend.py" write --directory .)
case "$identity" in
  azurerm:*) export ARM_USE_OIDC="${ARM_USE_OIDC:-true}" ;;
  remote:*)  : "${TF_TOKEN_app_terraform_io:?HCP Terraform needs TF_TOKEN_app_terraform_io from a runner secret}" ;;
esac
terraform init -input=false -lockfile=readonly
