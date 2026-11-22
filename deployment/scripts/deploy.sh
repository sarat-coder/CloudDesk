#!/usr/bin/env bash
# Deploy CloudDesk to a cloud environment via Terraform.
# Usage: ./deploy.sh <cloud> <environment> [--auto-approve]
# --auto-approve is REFUSED for staging and prod by this script.
set -euo pipefail

CLOUD="${1:?Usage: deploy.sh <cloud> <environment> [--auto-approve]}"
ENV="${2:?Usage: deploy.sh <cloud> <environment> [--auto-approve]}"
AUTO_APPROVE="${3:-}"

if [[ "$ENV" =~ ^(staging|prod)$ && "$AUTO_APPROVE" == "--auto-approve" ]]; then
  echo "ERROR: --auto-approve is not allowed for $ENV. A human must review the plan." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deployment/$CLOUD"
TFVARS="$TF_DIR/environments/$ENV/terraform.tfvars"
BACKEND_HCL="$REPO_ROOT/deployment/$CLOUD/backend.hcl"  # git-ignored

if [[ ! -f "$TFVARS" ]]; then
  echo "ERROR: var-file not found: $TFVARS" >&2; exit 1
fi

IMAGE_TAG="${TF_VAR_image_tag:-$(git -C "$REPO_ROOT" rev-parse --short HEAD)}"
export TF_VAR_image_tag="$IMAGE_TAG"

cd "$TF_DIR"

if [[ -f "$BACKEND_HCL" ]]; then
  terraform init -backend-config="$BACKEND_HCL" -reconfigure
else
  terraform init
fi

terraform plan -var-file="$TFVARS" -out=tfplan

if [[ "$AUTO_APPROVE" == "--auto-approve" ]]; then
  terraform apply tfplan
else
  echo ""
  echo "Plan saved to tfplan. Review above, then run:"
  echo "  cd $TF_DIR && terraform apply tfplan"
fi
