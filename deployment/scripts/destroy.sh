#!/usr/bin/env bash
# Destroy all Terraform-managed resources in an environment.
# --auto-approve is refused for staging and prod.
set -euo pipefail

CLOUD="${1:?Usage: destroy.sh <cloud> <environment> [--auto-approve]}"
ENV="${2:?Usage: destroy.sh <cloud> <environment> [--auto-approve]}"
AUTO_APPROVE="${3:-}"

if [[ "$ENV" =~ ^(staging|prod)$ && "$AUTO_APPROVE" == "--auto-approve" ]]; then
  echo "ERROR: --auto-approve is not allowed for $ENV destroy." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deployment/$CLOUD"
TFVARS="$TF_DIR/environments/$ENV/terraform.tfvars"

echo "WARNING: This will DESTROY all $CLOUD/$ENV resources. Press Ctrl+C within 10s to cancel."
sleep 10

cd "$TF_DIR"
if [[ "$AUTO_APPROVE" == "--auto-approve" ]]; then
  terraform destroy -var-file="$TFVARS" -auto-approve
else
  terraform destroy -var-file="$TFVARS"
fi
