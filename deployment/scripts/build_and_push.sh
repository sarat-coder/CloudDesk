#!/usr/bin/env bash
# Build backend and frontend images and push to the cloud registry.
# Usage: ./build_and_push.sh <cloud> <environment>
# Cloud: aws | azure | gcp
# Image tag = git SHA (never use :latest in production)
set -euo pipefail

CLOUD="${1:?Usage: build_and_push.sh <cloud> <environment>}"
ENV="${2:?Usage: build_and_push.sh <cloud> <environment>}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"

echo "Building images for cloud=$CLOUD env=$ENV tag=$IMAGE_TAG"

case "$CLOUD" in
  aws)
    REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION:-us-east-1}.amazonaws.com"
    aws ecr get-login-password --region "${AWS_REGION:-us-east-1}" | \
      docker login --username AWS --password-stdin "$REGISTRY"
    ;;
  azure)
    REGISTRY="${AZURE_ACR_NAME}.azurecr.io"
    az acr login --name "$AZURE_ACR_NAME"
    ;;
  gcp)
    REGISTRY="${GCP_REGION:-us-central1}-docker.pkg.dev/${GCP_PROJECT_ID}/clouddesk"
    gcloud auth configure-docker "${GCP_REGION:-us-central1}-docker.pkg.dev" --quiet
    ;;
  *)
    echo "Unknown cloud: $CLOUD (must be aws|azure|gcp)" >&2; exit 1
    ;;
esac

BACKEND_IMAGE="$REGISTRY/clouddesk-backend:$IMAGE_TAG"
FRONTEND_IMAGE="$REGISTRY/clouddesk-frontend:$IMAGE_TAG"

# Build from repo root so the full context is available
docker build -f "$REPO_ROOT/backend/Dockerfile"  -t "$BACKEND_IMAGE"  "$REPO_ROOT"
docker build -f "$REPO_ROOT/frontend/Dockerfile" -t "$FRONTEND_IMAGE" "$REPO_ROOT"

docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"

echo "Pushed:"
echo "  $BACKEND_IMAGE"
echo "  $FRONTEND_IMAGE"
echo "IMAGE_TAG=$IMAGE_TAG" >> "$GITHUB_OUTPUT" 2>/dev/null || echo "IMAGE_TAG=$IMAGE_TAG"
