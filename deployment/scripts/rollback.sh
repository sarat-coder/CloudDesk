#!/usr/bin/env bash
# Roll back to a previous image tag by re-applying with the old tag.
# Usage: ./rollback.sh <cloud> <environment> <previous-image-tag>
set -euo pipefail

CLOUD="${1:?Usage: rollback.sh <cloud> <environment> <tag>}"
ENV="${2:?Usage: rollback.sh <cloud> <environment> <tag>}"
ROLLBACK_TAG="${3:?Usage: rollback.sh <cloud> <environment> <tag>}"

echo "Rolling back $CLOUD/$ENV to image tag: $ROLLBACK_TAG"
echo "This will re-deploy with the previous image. Press Ctrl+C within 5s to cancel."
sleep 5

export TF_VAR_image_tag="$ROLLBACK_TAG"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/deploy.sh" "$CLOUD" "$ENV"
